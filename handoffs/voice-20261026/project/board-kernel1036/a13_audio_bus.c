// SPDX-License-Identifier: GPL-2.0-only
/* A13's private dynamic container. No registers, clocks or reset operations. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>

static int audio_bus_probe(struct platform_device *pdev)
{
	int ret = of_platform_populate(pdev->dev.of_node, NULL, NULL, &pdev->dev);
	if (ret)
		of_platform_depopulate(&pdev->dev);
	return ret;
}

static void audio_bus_remove(struct platform_device *pdev)
{
	of_platform_depopulate(&pdev->dev);
}

static const struct of_device_id audio_bus_of[] = {
	{ .compatible = "patientqwen,a13-audio-bus" }, {}
};
MODULE_DEVICE_TABLE(of, audio_bus_of);

static struct platform_driver audio_bus_driver = {
	.probe = audio_bus_probe,
	.remove_new = audio_bus_remove,
	.driver = { .name = "a13-audio-bus", .of_match_table = audio_bus_of,
		.suppress_bind_attrs = true },
};
module_platform_driver(audio_bus_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A13 explicit audio child population; no hardware accesses");
