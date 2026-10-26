// SPDX-License-Identifier: GPL-2.0-only
/* A-owned maintenance-only playback DAI. DMAengine starts before serial START;
 * reverse STOP disables serial before terminate_async; generic sync_stop joins
 * DMA callbacks before hw_free/close. No mmap/pause/resume or capture interface.
 */
#include <linux/capability.h>
#include <linux/clk.h>
#include <linux/dma-mapping.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/workqueue.h>
#include <sound/dmaengine_pcm.h>
#include <sound/pcm_params.h>
#include <sound/soc.h>
#include "muted_policy.h"

#define CONTROL 0x00
#define OUTPUT_TRI 0x04
#define STATUS 0x08
#define INPUT_TRI 0x0c
#define ERRORS 0x1f

struct muted_serial {
	void __iomem *regs;
	struct clk *clock;
	struct snd_dmaengine_dai_dma_data tx;
	spinlock_t lock;
	struct snd_pcm_substream *stream;
	struct work_struct fault_work;
	int irq;
	bool fatal, running, prepared, irq_masked;
	u32 last_fault;
	u64 starts, stops, faults;
};

static void fault_work(struct work_struct *work)
{
	struct muted_serial *a = container_of(work, struct muted_serial, fault_work);
	struct snd_pcm_substream *s;
	unsigned long flags;
	spin_lock_irqsave(&a->lock, flags);
	s = a->stream;
	spin_unlock_irqrestore(&a->lock, flags);
	if (s)
		snd_pcm_stop_xrun(s);
}

static irqreturn_t fault_irq(int irq, void *data)
{
	struct muted_serial *a = data;
	unsigned long flags;
	u32 status = readl(a->regs + STATUS);
	if (!(status & ERRORS))
		return IRQ_NONE;
	spin_lock_irqsave(&a->lock, flags);
	writel(0, a->regs + CONTROL);
	readl(a->regs + CONTROL); /* flush posted STOP */
	a->fatal = true;
	a->running = a->prepared = false;
	a->last_fault = status;
	a->faults++;
	if (!a->irq_masked) {
		a->irq_masked = true;
		disable_irq_nosync(irq);
	}
	spin_unlock_irqrestore(&a->lock, flags);
	schedule_work(&a->fault_work);
	return IRQ_HANDLED;
}

static int serial_startup(struct snd_pcm_substream *s, struct snd_soc_dai *dai)
{
	struct muted_serial *a = snd_soc_dai_get_drvdata(dai);
	unsigned long flags;
	int ret = 0;
	if (!capable(CAP_SYS_ADMIN) || s->stream != SNDRV_PCM_STREAM_PLAYBACK)
		return -EPERM;
	spin_lock_irqsave(&a->lock, flags);
	if (a->fatal || a->stream)
		ret = -EBUSY;
	else
		a->stream = s;
	spin_unlock_irqrestore(&a->lock, flags);
	return ret;
}

static void serial_shutdown(struct snd_pcm_substream *s, struct snd_soc_dai *dai)
{
	struct muted_serial *a = snd_soc_dai_get_drvdata(dai);
	unsigned long flags;
	writel(0, a->regs + CONTROL);
	readl(a->regs + CONTROL);
	synchronize_irq(a->irq);
	cancel_work_sync(&a->fault_work);
	spin_lock_irqsave(&a->lock, flags);
	a->stream = NULL;
	a->running = a->prepared = false;
	spin_unlock_irqrestore(&a->lock, flags);
}

static int serial_params(struct snd_pcm_substream *s,
	struct snd_pcm_hw_params *p, struct snd_soc_dai *dai)
{
	if (params_format(p) != SNDRV_PCM_FORMAT_S16_LE ||
	    !a13_profile_ok(params_rate(p), params_channels(p), params_width(p),
		params_period_bytes(p), params_buffer_bytes(p)))
		return -EINVAL;
	return 0;
}

static int serial_prepare(struct snd_pcm_substream *s, struct snd_soc_dai *dai)
{
	struct muted_serial *a = snd_soc_dai_get_drvdata(dai);
	u32 status;
	int ret;
	unsigned long flags;
	if (READ_ONCE(a->fatal) || !a13_dma_ok(s->runtime->dma_addr, s->runtime->dma_bytes))
		return -EPERM;
	/* Normal prepare only; never clear an observed runtime failure latch. */
	writel(0, a->regs + CONTROL);
	memset(s->runtime->dma_area, 0, s->runtime->dma_bytes);
	writel(4, a->regs + CONTROL);
	ret = readl_poll_timeout(a->regs + STATUS, status, !(status & ERRORS), 1, 2000);
	writel(0, a->regs + CONTROL);
	if (ret || status >> 16 != 0xa13c)
		return -EIO;
	spin_lock_irqsave(&a->lock, flags);
	if (a->fatal)
		ret = -EIO;
	else
		a->prepared = true;
	spin_unlock_irqrestore(&a->lock, flags);
	return ret;
}

static int serial_trigger(struct snd_pcm_substream *s, int cmd,
	struct snd_soc_dai *dai)
{
	struct muted_serial *a = snd_soc_dai_get_drvdata(dai);
	unsigned long flags;
	int ret = 0;
	spin_lock_irqsave(&a->lock, flags);
	switch (cmd) {
	case SNDRV_PCM_TRIGGER_START:
		if (a->fatal || !a->prepared || a->running) {
			ret = -EPERM;
			break;
		}
		a->running = true;
		a->starts++;
		writel(1, a->regs + CONTROL);
		break;
	case SNDRV_PCM_TRIGGER_STOP:
	case SNDRV_PCM_TRIGGER_SUSPEND:
		writel(0, a->regs + CONTROL);
		readl(a->regs + CONTROL);
		a->running = a->prepared = false;
		a->stops++;
		break;
	default:
		ret = -EINVAL;
	}
	spin_unlock_irqrestore(&a->lock, flags);
	return ret;
}

static int serial_fmt(struct snd_soc_dai *dai, unsigned int fmt)
{
	/* soc-core flips the codec-centric link format for the CPU DAI. */
	return fmt == (SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF |
		SND_SOC_DAIFMT_CBC_CFC) ? 0 : -EINVAL;
}

static int serial_dai_probe(struct snd_soc_dai *dai)
{
	struct muted_serial *a = dev_get_drvdata(dai->dev);
	snd_soc_dai_set_drvdata(dai, a);
	snd_soc_dai_init_dma_data(dai, &a->tx, NULL);
	return 0;
}

static int zero_process(struct snd_pcm_substream *s, int channel,
	unsigned long offset, unsigned long bytes)
{
	if (s->stream != SNDRV_PCM_STREAM_PLAYBACK ||
	    offset > s->runtime->dma_bytes || bytes > s->runtime->dma_bytes - offset)
		return -EINVAL;
	memset(s->runtime->dma_area + offset, 0, bytes);
	return 0;
}

static ssize_t muted_status_show(struct device *dev,
	struct device_attribute *attr, char *buf)
{
	struct muted_serial *a = dev_get_drvdata(dev);
	unsigned long flags;
	ssize_t n;
	spin_lock_irqsave(&a->lock, flags);
	n = sysfs_emit(buf, "status=%08x control=%08x fatal=%u running=%u prepared=%u open=%u starts=%llu stops=%llu faults=%llu last_fault=%08x\n",
		readl(a->regs + STATUS), readl(a->regs + CONTROL), a->fatal, a->running,
		a->prepared, !!a->stream, a->starts, a->stops, a->faults, a->last_fault);
	spin_unlock_irqrestore(&a->lock, flags);
	return n;
}
static DEVICE_ATTR_RO(muted_status);
static struct attribute *serial_attrs[] = { &dev_attr_muted_status.attr, NULL };
ATTRIBUTE_GROUPS(serial);

static const struct snd_soc_dai_ops serial_ops = {
	.probe = serial_dai_probe, .startup = serial_startup, .shutdown = serial_shutdown,
	.hw_params = serial_params, .prepare = serial_prepare,
	.trigger = serial_trigger, .set_fmt = serial_fmt,
};
static struct snd_soc_dai_driver serial_dai = {
	.name = "a13-muted-serial",
	.playback = { .stream_name = "Zero-only maintenance playback", .channels_min = 2,
		.channels_max = 2, .rates = SNDRV_PCM_RATE_48000,
		.formats = SNDRV_PCM_FMTBIT_S16_LE },
	.ops = &serial_ops,
};
static const struct snd_soc_component_driver serial_component = {
	.name = "a13-muted-serial",
};
static const struct snd_pcm_hardware pcm_hardware = {
	.info = SNDRV_PCM_INFO_INTERLEAVED | SNDRV_PCM_INFO_BATCH,
	.formats = SNDRV_PCM_FMTBIT_S16_LE, .rates = SNDRV_PCM_RATE_48000,
	.rate_min = 48000, .rate_max = 48000, .channels_min = 2, .channels_max = 2,
	.buffer_bytes_max = 65536, .period_bytes_min = 1024, .period_bytes_max = 1024,
	.periods_min = 2, .periods_max = 64,
};
static const struct snd_dmaengine_pcm_config pcm_config = {
	.pcm_hardware = &pcm_hardware, .process = zero_process,
	.prepare_slave_config = snd_dmaengine_pcm_prepare_slave_config,
	.prealloc_buffer_size = 65536,
};

static void disable_clock(void *data) { clk_disable_unprepare(data); }

static int serial_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct muted_serial *a;
	struct resource *resource;
	int ret;
	a = devm_kzalloc(dev, sizeof(*a), GFP_KERNEL);
	if (!a)
		return -ENOMEM;
	spin_lock_init(&a->lock);
	INIT_WORK(&a->fault_work, fault_work);
	resource = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!resource || resource->start != 0xa1000000 || resource_size(resource) != 65536)
		return -EINVAL;
	a->clock = devm_clk_get(dev, "s_axi_aclk");
	if (IS_ERR(a->clock))
		return PTR_ERR(a->clock);
	if (clk_get_rate(a->clock) < 99000000 || clk_get_rate(a->clock) > 101000000)
		return -EINVAL;
	ret = clk_prepare_enable(a->clock);
	if (ret)
		return ret;
	ret = devm_add_action_or_reset(dev, disable_clock, a->clock);
	if (ret)
		return ret;
	a->regs = devm_ioremap_resource(dev, resource);
	if (IS_ERR(a->regs))
		return PTR_ERR(a->regs);
	if (readl(a->regs + STATUS) >> 16 != 0xa13c)
		return -ENODEV;
	writel(0, a->regs + CONTROL);
	writel(0, a->regs + OUTPUT_TRI);
	writel(~0U, a->regs + INPUT_TRI);
	a->tx.addr_width = DMA_SLAVE_BUSWIDTH_4_BYTES;
	a->tx.maxburst = 1;
	platform_set_drvdata(pdev, a);
	a->irq = platform_get_irq(pdev, 0);
	if (a->irq < 0)
		return a->irq;
	ret = devm_request_irq(dev, a->irq, fault_irq, 0, dev_name(dev), a);
	if (ret)
		return ret;
	ret = devm_snd_soc_register_component(dev, &serial_component, &serial_dai, 1);
	if (ret)
		return ret;
	return devm_snd_dmaengine_pcm_register(dev, &pcm_config, 0);
}

static void serial_remove(struct platform_device *pdev)
{
	struct muted_serial *a = platform_get_drvdata(pdev);
	writel(0, a->regs + CONTROL);
	readl(a->regs + CONTROL);
	synchronize_irq(a->irq);
	cancel_work_sync(&a->fault_work);
}
static const struct of_device_id serial_match[] = {
	{ .compatible = "patientqwen,a13-muted-serial" }, {}
};
MODULE_DEVICE_TABLE(of, serial_match);
static struct platform_driver serial_driver = {
	.probe = serial_probe, .remove_new = serial_remove,
	.driver = { .name = "a13-muted-serial", .of_match_table = serial_match,
		.dev_groups = serial_groups },
};
module_platform_driver(serial_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A13 zero-only PCM, fixed codec-paced DMA diagnostic");
