/* A-owned process-context IRQ lifecycle candidate; ISR never takes zei_lock. */
static int zocl_irq_intc_add(struct platform_device *pdev, u32 id, irq_handler_t cb, void *arg)
{
	unsigned long irqflags;
	struct zocl_irq_intc *zintc = platform_get_drvdata(pdev);
	struct zocl_ert_intc_handler *h;
	int ret;

	if (id >= zintc->zei_num_irqs || !cb)
		return -EINVAL;
	h = &zintc->zei_handler[id];
	mutex_lock(&zintc->zei_lock);
	if (h->zeih_cb) {
		ret = -EINVAL;
		goto out;
	}

	/* Install while masked: callback state must precede the first IRQ. */
	ret = request_irq(h->zeih_irq, zintc_isr, IRQF_NO_AUTOEN, ZINTC_DRV_NAME, h);
	if (ret) {
		zintc_err(zintc, "failed to add isr for IRQ: %d: %d", h->zeih_irq, ret);
		goto out;
	}
	spin_lock_irqsave(&h->zeih_lock, irqflags);
	h->zeih_cb = cb;
	h->zeih_arg = arg;
	h->zeih_enabled = true;
	spin_unlock_irqrestore(&h->zeih_lock, irqflags);
	enable_irq(h->zeih_irq);
	zintc_info(zintc, "managing IRQ %d", h->zeih_irq);
out:
	mutex_unlock(&zintc->zei_lock);
	return ret;
}

/* Caller owns zei_lock; free_irq drains handlers without any spinlock held. */
static void a10_irq_release_locked(struct zocl_ert_intc_handler *h)
{
	unsigned long irqflags;
	if (!h->zeih_cb)
		return;
	free_irq(h->zeih_irq, h);
	spin_lock_irqsave(&h->zeih_lock, irqflags);
	h->zeih_cb = NULL;
	h->zeih_arg = NULL;
	h->zeih_enabled = false;
	spin_unlock_irqrestore(&h->zeih_lock, irqflags);
}

static void zocl_irq_intc_remove(struct platform_device *pdev, u32 id)
{
	struct zocl_irq_intc *zintc = platform_get_drvdata(pdev);
	if (WARN_ON_ONCE(id >= zintc->zei_num_irqs))
		return;
	mutex_lock(&zintc->zei_lock);
	a10_irq_release_locked(&zintc->zei_handler[id]);
	mutex_unlock(&zintc->zei_lock);
}

static void zocl_irq_intc_config(struct platform_device *pdev, u32 id, bool enabled)
{
	struct zocl_irq_intc *zintc = platform_get_drvdata(pdev);
	struct zocl_ert_intc_handler *h;
	if (WARN_ON_ONCE(id >= zintc->zei_num_irqs))
		return;
	h = &zintc->zei_handler[id];
	mutex_lock(&zintc->zei_lock);
	if (!h->zeih_cb)
		goto out;
	/* Keep the existing enable-depth API: UCU ISR may mask the line itself. */
	if (enabled)
		enable_irq(h->zeih_irq);
	else
		disable_irq(h->zeih_irq);
out:
	mutex_unlock(&zintc->zei_lock);
}

static int zintc_remove(struct platform_device *pdev)
{
	struct zocl_irq_intc *zintc = platform_get_drvdata(pdev);
	int i;
	/* Normal, quiescent device removal only; not an active-DMA recovery API. */
	mutex_lock(&zintc->zei_lock);
	for (i = 0; i < zintc->zei_num_irqs; i++)
		a10_irq_release_locked(&zintc->zei_handler[i]);
	mutex_unlock(&zintc->zei_lock);
	zintc_info(zintc, "Removing %s", ZINTC_DRV_NAME);
	return 0;
}
