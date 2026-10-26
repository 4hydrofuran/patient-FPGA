// SPDX-License-Identifier: GPL-2.0-only
/* New single duplex link. Codec is bit/frame clock provider; no MCLK wire. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <sound/pcm_params.h>
#include <sound/soc.h>
#include "wm8960.h"

struct a13_card {
	struct snd_soc_card card;
	struct snd_soc_dai_link link;
	struct snd_soc_dai_link_component cpu, codec, platform;
};

static int a13_deny_start(struct snd_pcm_substream *substream)
{
	return -EPERM;
}

static int a13_deny_params(struct snd_pcm_substream *substream,
		struct snd_pcm_hw_params *params)
{
	return -EPERM;
}

static int a13_link_init(struct snd_soc_pcm_runtime *rtd)
{
	struct snd_soc_dai *codec = snd_soc_rtd_to_codec(rtd, 0);
	/* Describe the onboard reference only. No external MCLK or PLL enable. */
	return snd_soc_dai_set_sysclk(codec, WM8960_SYSCLK_AUTO, 24000000,
				    SND_SOC_CLOCK_IN);
}

static int a13_mute_outputs(struct snd_soc_card *card)
{
	struct snd_soc_pcm_runtime *rtd;
	const char * const names[] = {
		"SPK_LP", "SPK_LN", "SPK_RP", "SPK_RN", "HP_L", "HP_R", "OUT3"
	};
	int index, ret;
	for_each_card_rtds(card, rtd) {
		struct snd_soc_component *codec = snd_soc_rtd_to_codec(rtd, 0)->component;
		for (index = 0; index < ARRAY_SIZE(names); index++) {
			ret = snd_soc_dapm_nc_pin(snd_soc_component_get_dapm(codec), names[index]);
			if (ret)
				return ret;
		}
		ret = snd_soc_component_update_bits(codec, WM8960_DACCTL1, 8, 8);
		if (ret < 0)
			return ret;
		ret = snd_soc_component_write(codec, WM8960_CLASSD1, 0);
		if (ret < 0)
			return ret;
	}
	return 0;
}

static void a13_put_nodes(void *data)
{
	struct a13_card *a = data;
	of_node_put(a->cpu.of_node);
	of_node_put(a->codec.of_node);
	of_node_put(a->platform.of_node);
}

static const struct snd_soc_ops a13_ops = {
	.startup = a13_deny_start, .hw_params = a13_deny_params,
};

static int a13_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct a13_card *a;
	int ret;
	a = devm_kzalloc(dev, sizeof(*a), GFP_KERNEL);
	if (!a)
		return -ENOMEM;
	ret = devm_add_action_or_reset(dev, a13_put_nodes, a);
	if (ret)
		return ret;
	a->cpu.of_node = of_parse_phandle(dev->of_node, "audio-cpu", 0);
	a->platform.of_node = of_parse_phandle(dev->of_node, "audio-cpu", 0);
	a->codec.of_node = of_parse_phandle(dev->of_node, "audio-codec", 0);
	if (!a->cpu.of_node || !a->platform.of_node || !a->codec.of_node)
		return -EINVAL;
	a->cpu.dai_name = "a13-oversampled-i2s";
	a->codec.dai_name = "wm8960-hifi";
	a->link.name = "WM8960 codec-master locked duplex";
	a->link.stream_name = a->link.name;
	a->link.cpus = &a->cpu; a->link.num_cpus = 1;
	a->link.codecs = &a->codec; a->link.num_codecs = 1;
	a->link.platforms = &a->platform; a->link.num_platforms = 1;
	a->link.dai_fmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF |
		SND_SOC_DAIFMT_CBP_CFP;
	a->link.init = a13_link_init;
	a->link.ops = &a13_ops;
	a->card.owner = THIS_MODULE;
	a->card.dev = dev;
	a->card.name = "KV260-WM8960-MASTER-LOCKED";
	a->card.dai_link = &a->link;
	a->card.num_links = 1;
	a->card.late_probe = a13_mute_outputs;
	return devm_snd_soc_register_card(dev, &a->card);
}

static const struct of_device_id a13_match[] = {
	{ .compatible = "patientqwen,a13-codec-master-locked" }, {}
};
MODULE_DEVICE_TABLE(of, a13_match);
static struct platform_driver a13_driver = {
	.probe = a13_probe,
	.driver = { .name = "a13-codec-master-locked", .of_match_table = a13_match },
};
module_platform_driver(a13_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A13 WM8960 master clock card, permanently stream-locked");
