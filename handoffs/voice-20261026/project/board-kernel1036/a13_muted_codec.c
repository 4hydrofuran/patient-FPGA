// SPDX-License-Identifier: GPL-2.0-only
/* Fixed diagnostic-only WM8960 clock/DAI. No mixer, capture or audible route.
 * Register packing and PLL factors checked against matching wm8960.c and the
 * Cirrus WM8960 Rev4.4 datasheet. Cached values are NOT physical readbacks.
 */
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <sound/pcm_params.h>
#include <sound/soc.h>
#include "muted_policy.h"

struct muted_codec {
	struct i2c_client *client;
	struct mutex mutex;
	u16 cache[56];
	u64 writes;
	int fault;
	bool configured;
};

static int codec_write(struct muted_codec *c, unsigned int reg, unsigned int val)
{
	u8 wire[2];
	int ret;
	if (!a13_codec_value(reg, &val))
		return -EPERM;
	wire[0] = (reg << 1) | (val >> 8);
	wire[1] = val & 0xff;
	ret = i2c_master_send(c->client, wire, 2);
	if (ret != 2) {
		c->fault = ret < 0 ? ret : -EIO;
		c->configured = false;
		dev_err(&c->client->dev, "A13_MUTED_IIC_FAILURE reg=%02x rc=%d\n", reg, ret);
		return c->fault;
	}
	c->cache[reg] = val;
	c->writes++;
	return 0;
}

static int codec_stop(struct muted_codec *c)
{
	int first = 0, ret;
	const u16 sequence[][2] = {
		{0x05, 8}, {0x31, 0}, {0x07, 2}, /* slave: stop driving clocks */
		{0x04, 4}, {0x1a, 0}, {0x2f, 0}, {0x19, 0}
	};
	unsigned int i;
	/* Attempt every safe write even after one IIC failure. Keep first error. */
	for (i = 0; i < ARRAY_SIZE(sequence); i++) {
		ret = codec_write(c, sequence[i][0], sequence[i][1]);
		if (ret && !first)
			first = ret;
	}
	c->configured = false;
	return first;
}

static int codec_fmt(struct snd_soc_dai *dai, unsigned int fmt)
{
	return fmt == (SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF |
		SND_SOC_DAIFMT_CBP_CFP) ? 0 : -EINVAL;
}

static int codec_params(struct snd_pcm_substream *s,
	struct snd_pcm_hw_params *p, struct snd_soc_dai *dai)
{
	struct muted_codec *c = dev_get_drvdata(dai->dev);
	unsigned int i;
	int ret = 0;
	const u16 sequence[][2] = {
		{0x05, 8}, {0x31, 0}, {0x1a, 0}, {0x2f, 0}, {0x07, 2},
		{0x02, 0x100}, {0x03, 0x100}, {0x28, 0x100}, {0x29, 0x100},
		{0x0a, 0x100}, {0x0b, 0x100}, {0x19, 0x140},
		{0x09, 0x40}, {0x18, 4}, {0x30, 0}, /* shared DACLRC, ALRC GPIO */
		{0x04, 4}, {0x08, 0x1c7}, /* SYSCLK /2, BCLK /8, class-D clock /16 */
		{0x35, 0x31}, {0x36, 0x26}, {0x37, 0xe9}, {0x34, 0x38},
		{0x1a, 0x181} /* 24MHz -> PLL24.576MHz; DACs+PLL, no output stages */
	};
	if (s->stream != SNDRV_PCM_STREAM_PLAYBACK ||
	    params_format(p) != SNDRV_PCM_FORMAT_S16_LE ||
	    !a13_profile_ok(params_rate(p), params_channels(p), params_width(p),
		params_period_bytes(p), params_buffer_bytes(p)))
		return -EINVAL;
	mutex_lock(&c->mutex);
	if (c->fault) {
		ret = c->fault;
		goto out;
	}
	for (i = 0; i < ARRAY_SIZE(sequence); i++) {
		ret = codec_write(c, sequence[i][0], sequence[i][1]);
		if (ret)
			goto failed;
	}
	msleep(250); /* same conservative PLL settling interval as matched driver */
	ret = codec_write(c, 0x04, 5); /* select PLL; SYSCLK 12.288MHz */
	if (!ret)
		ret = codec_write(c, 0x07, 0x42); /* enable master I2S16 only last */
	if (ret)
		goto failed;
	c->configured = true;
	goto out;
failed:
	codec_stop(c);
out:
	mutex_unlock(&c->mutex);
	return ret;
}

static int codec_free(struct snd_pcm_substream *s, struct snd_soc_dai *dai)
{
	struct muted_codec *c = dev_get_drvdata(dai->dev);
	int ret;
	mutex_lock(&c->mutex);
	ret = codec_stop(c);
	mutex_unlock(&c->mutex);
	return ret;
}

static int codec_mute(struct snd_soc_dai *dai, int mute, int direction)
{
	/* Neither ASoC nor any control can physically clear the mute bit. */
	return 0;
}

static ssize_t muted_state_show(struct device *dev,
	struct device_attribute *attr, char *buf)
{
	struct muted_codec *c = dev_get_drvdata(dev);
	ssize_t n;
	mutex_lock(&c->mutex);
	n = sysfs_emit(buf, "configured=%u fault=%d writes=%llu cache_not_readback=1 dacctl1=%03x power1=%03x power2=%03x power3=%03x classd1=%03x iface1=%03x clock1=%03x clock2=%03x pll1=%03x pll2=%03x pll3=%03x pll4=%03x\n",
		c->configured, c->fault, c->writes, c->cache[5], c->cache[0x19],
		c->cache[0x1a], c->cache[0x2f], c->cache[0x31], c->cache[7],
		c->cache[4], c->cache[8], c->cache[0x34], c->cache[0x35],
		c->cache[0x36], c->cache[0x37]);
	mutex_unlock(&c->mutex);
	return n;
}
static DEVICE_ATTR_RO(muted_state);
static struct attribute *muted_attrs[] = { &dev_attr_muted_state.attr, NULL };
ATTRIBUTE_GROUPS(muted);

static const struct snd_soc_dai_ops codec_ops = {
	.set_fmt = codec_fmt, .hw_params = codec_params, .hw_free = codec_free,
	.mute_stream = codec_mute, .no_capture_mute = 1,
};
static struct snd_soc_dai_driver codec_dai = {
	.name = "a13-muted-wm8960",
	.playback = { .stream_name = "Muted clock diagnostic", .channels_min = 2,
		.channels_max = 2, .rates = SNDRV_PCM_RATE_48000,
		.formats = SNDRV_PCM_FMTBIT_S16_LE },
	.ops = &codec_ops,
};
static const struct snd_soc_component_driver codec_component = {
	.name = "a13-muted-wm8960",
};

static int muted_probe(struct i2c_client *client)
{
	struct muted_codec *c;
	struct clk *mclk;
	int ret;
	mclk = devm_clk_get(&client->dev, "mclk");
	if (IS_ERR(mclk))
		return PTR_ERR(mclk);
	if (clk_get_rate(mclk) != 24000000 || client->addr != 0x1a)
		return -EINVAL;
	c = devm_kzalloc(&client->dev, sizeof(*c), GFP_KERNEL);
	if (!c)
		return -ENOMEM;
	c->client = client;
	mutex_init(&c->mutex);
	i2c_set_clientdata(client, c);
	ret = codec_write(c, 0x0f, 0); /* reset starts with output power disabled */
	if (!ret)
		ret = codec_stop(c);
	if (ret)
		return ret;
	return devm_snd_soc_register_component(&client->dev, &codec_component,
		&codec_dai, 1);
}

static void muted_remove(struct i2c_client *client)
{
	struct muted_codec *c = i2c_get_clientdata(client);
	mutex_lock(&c->mutex);
	codec_stop(c);
	mutex_unlock(&c->mutex);
}
static const struct of_device_id muted_of[] = {
	{ .compatible = "patientqwen,wm8960-muted-diagnostic" }, {}
};
MODULE_DEVICE_TABLE(of, muted_of);
static struct i2c_driver muted_driver = {
	.driver = { .name = "a13-muted-wm8960", .of_match_table = muted_of,
		.dev_groups = muted_groups },
	.probe = muted_probe, .remove = muted_remove,
};
module_i2c_driver(muted_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A13 permanently muted WM8960 fixed-clock board diagnostic");
