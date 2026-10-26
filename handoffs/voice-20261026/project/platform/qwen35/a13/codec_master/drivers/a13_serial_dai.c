// SPDX-License-Identifier: GPL-2.0-only
/* A-owned fixed-profile CPU DAI/PCM candidate. Permanently stream-locked.
 * Independent of old AMD I2S/Audio Formatter; not installed by this package.
 */
#include <linux/clk.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <sound/dmaengine_pcm.h>
#include <sound/pcm_params.h>
#include <sound/soc.h>

#define A13_CONTROL 0x00
#define A13_OUTPUT_TRI 0x04
#define A13_STATUS 0x08
#define A13_INPUT_TRI 0x0c
#define A13_SIGNATURE 0xa13c
#define A13_ERRORS GENMASK(4, 0)

struct a13_serial {
	void __iomem *regs;
	struct clk *clock;
	struct snd_dmaengine_dai_dma_data tx, rx;
};

static int a13_startup(struct snd_pcm_substream *s, struct snd_soc_dai *dai)
{
	/* No DT property, mixer control or module option can override this. */
	return -EPERM;
}

static int a13_params(struct snd_pcm_substream *s,
		struct snd_pcm_hw_params *p, struct snd_soc_dai *dai)
{
	if (params_rate(p) != 48000 || params_channels(p) != 2 ||
	    params_format(p) != SNDRV_PCM_FORMAT_S16_LE ||
	    params_period_bytes(p) != 1024 || params_buffer_bytes(p) % 1024)
		return -EINVAL;
	/* Keep the independent params entry locked, even if startup is bypassed. */
	return -EPERM;
}

static int a13_trigger(struct snd_pcm_substream *s, int cmd,
		struct snd_soc_dai *dai)
{
	struct a13_serial *a = snd_soc_dai_get_drvdata(dai);
	/* STOP is idempotent. START/RESUME/PAUSE_RELEASE never start hardware. */
	if (cmd == SNDRV_PCM_TRIGGER_STOP || cmd == SNDRV_PCM_TRIGGER_SUSPEND) {
		writel(0, a->regs + A13_CONTROL);
		return 0;
	}
	return -EPERM;
}

static int a13_set_fmt(struct snd_soc_dai *dai, unsigned int fmt)
{
	unsigned int wanted = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF |
		SND_SOC_DAIFMT_CBC_CFC;
	/* soc-core flips the codec-centric link format before calling CPU DAI. */
	return fmt == wanted ? 0 : -EINVAL;
}

static int a13_dai_probe(struct snd_soc_dai *dai)
{
	struct a13_serial *a = dev_get_drvdata(dai->dev);
	snd_soc_dai_set_drvdata(dai, a);
	snd_soc_dai_init_dma_data(dai, &a->tx, &a->rx);
	return 0;
}

static irqreturn_t a13_fault_irq(int irq, void *data)
{
	struct a13_serial *a = data;
	u32 status = readl(a->regs + A13_STATUS);
	if (!(status & A13_ERRORS))
		return IRQ_NONE;
	/* This locked candidate has no live streams: quarantine, do not clear. */
	writel(0, a->regs + A13_CONTROL);
	disable_irq_nosync(irq);
	return IRQ_HANDLED;
}

static const struct snd_soc_dai_ops a13_dai_ops = {
	.probe = a13_dai_probe,
	.startup = a13_startup, .hw_params = a13_params, .trigger = a13_trigger,
	.set_fmt = a13_set_fmt,
};
static struct snd_soc_dai_driver a13_dai = {
	.name = "a13-oversampled-i2s",
	.playback = { .stream_name = "Locked playback", .channels_min = 2,
		.channels_max = 2, .rates = SNDRV_PCM_RATE_48000,
		.formats = SNDRV_PCM_FMTBIT_S16_LE },
	.capture = { .stream_name = "Locked capture", .channels_min = 2,
		.channels_max = 2, .rates = SNDRV_PCM_RATE_48000,
		.formats = SNDRV_PCM_FMTBIT_S16_LE },
	.ops = &a13_dai_ops, .symmetric_rate = 1, .symmetric_channels = 1,
	.symmetric_sample_bits = 1,
};
static const struct snd_soc_component_driver a13_component = {
	.name = "a13-oversampled-i2s",
};
static const struct snd_pcm_hardware a13_pcm_hardware = {
	.info = SNDRV_PCM_INFO_INTERLEAVED | SNDRV_PCM_INFO_MMAP |
		SNDRV_PCM_INFO_MMAP_VALID | SNDRV_PCM_INFO_BATCH,
	.formats = SNDRV_PCM_FMTBIT_S16_LE, .rates = SNDRV_PCM_RATE_48000,
	.rate_min = 48000, .rate_max = 48000, .channels_min = 2, .channels_max = 2,
	.buffer_bytes_max = 65536, .period_bytes_min = 1024, .period_bytes_max = 1024,
	.periods_min = 2, .periods_max = 64,
};
static const struct snd_dmaengine_pcm_config a13_pcm_config = {
	.pcm_hardware = &a13_pcm_hardware,
	.prepare_slave_config = snd_dmaengine_pcm_prepare_slave_config,
	.prealloc_buffer_size = 65536,
};

static void a13_clock_disable(void *data)
{
	clk_disable_unprepare(data);
}

static int a13_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct a13_serial *a;
	int irq, ret;
	a = devm_kzalloc(dev, sizeof(*a), GFP_KERNEL);
	if (!a)
		return -ENOMEM;
	a->clock = devm_clk_get(dev, "s_axi_aclk");
	if (IS_ERR(a->clock))
		return PTR_ERR(a->clock);
	ret = clk_prepare_enable(a->clock);
	if (ret)
		return ret;
	ret = devm_add_action_or_reset(dev, a13_clock_disable, a->clock);
	if (ret)
		return ret;
	a->regs = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(a->regs))
		return PTR_ERR(a->regs);
	/* No write to an old bitstream's unrelated register map. */
	if (readl(a->regs + A13_STATUS) >> 16 != A13_SIGNATURE)
		return -ENODEV;
	writel(0, a->regs + A13_CONTROL);
	writel(0, a->regs + A13_OUTPUT_TRI);
	writel(~0U, a->regs + A13_INPUT_TRI);
	a->tx.addr_width = a->rx.addr_width = DMA_SLAVE_BUSWIDTH_4_BYTES;
	a->tx.maxburst = a->rx.maxburst = 1;
	platform_set_drvdata(pdev, a);
	irq = platform_get_irq(pdev, 0);
	if (irq < 0)
		return irq;
	ret = devm_request_irq(dev, irq, a13_fault_irq, 0, dev_name(dev), a);
	if (ret)
		return ret;
	ret = devm_snd_soc_register_component(dev, &a13_component, &a13_dai, 1);
	if (ret)
		return ret;
	return devm_snd_dmaengine_pcm_register(dev, &a13_pcm_config, 0);
}

static const struct of_device_id a13_match[] = {
	{ .compatible = "patientqwen,a13-oversampled-i2s-locked" }, {}
};
MODULE_DEVICE_TABLE(of, a13_match);
static struct platform_driver a13_driver = {
	.probe = a13_probe,
	.driver = { .name = "a13-oversampled-i2s-locked", .of_match_table = a13_match },
};
module_platform_driver(a13_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A13 oversampled codec-master DAI and DMAengine PCM, permanently locked");
