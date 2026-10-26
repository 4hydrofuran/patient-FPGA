// SPDX-License-Identifier: GPL-2.0-only
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <sound/soc.h>

struct muted_card {
	struct snd_soc_card card;
	struct snd_soc_dai_link link;
	struct snd_soc_dai_link_component cpu, codec, platform;
};
static void put_nodes(void *data)
{
	struct muted_card *a = data;
	of_node_put(a->cpu.of_node);
	of_node_put(a->codec.of_node);
	of_node_put(a->platform.of_node);
}
static int card_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct muted_card *a;
	int ret;
	a = devm_kzalloc(dev, sizeof(*a), GFP_KERNEL);
	if (!a)
		return -ENOMEM;
	ret = devm_add_action_or_reset(dev, put_nodes, a);
	if (ret)
		return ret;
	a->cpu.of_node = of_parse_phandle(dev->of_node, "audio-cpu", 0);
	a->platform.of_node = of_parse_phandle(dev->of_node, "audio-cpu", 0);
	a->codec.of_node = of_parse_phandle(dev->of_node, "audio-codec", 0);
	if (!a->cpu.of_node || !a->platform.of_node || !a->codec.of_node)
		return -EINVAL;
	a->cpu.dai_name = "a13-muted-serial";
	a->codec.dai_name = "a13-muted-wm8960";
	a->link.name = "WM8960 zero-only muted diagnostic";
	a->link.stream_name = a->link.name;
	a->link.cpus = &a->cpu; a->link.num_cpus = 1;
	a->link.codecs = &a->codec; a->link.num_codecs = 1;
	a->link.platforms = &a->platform; a->link.num_platforms = 1;
	a->link.dai_fmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBP_CFP;
	/* DEFAULT START: link -> DMA component -> CPU DAI. STOP reverses it. */
	a->link.trigger_start = SND_SOC_TRIGGER_ORDER_DEFAULT;
	a->link.trigger_stop = SND_SOC_TRIGGER_ORDER_DEFAULT;
	a->card.owner = THIS_MODULE;
	a->card.dev = dev;
	a->card.name = "KV260-WM8960-MUTED";
	a->card.dai_link = &a->link;
	a->card.num_links = 1;
	return devm_snd_soc_register_card(dev, &a->card);
}
static const struct of_device_id card_match[] = {
	{ .compatible = "patientqwen,a13-muted-card" }, {}
};
MODULE_DEVICE_TABLE(of, card_match);
static struct platform_driver card_driver = {
	.probe = card_probe,
	.driver = { .name = "a13-muted-card", .of_match_table = card_match },
};
module_platform_driver(card_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A13 WM8960 permanently muted diagnostic sound card");
