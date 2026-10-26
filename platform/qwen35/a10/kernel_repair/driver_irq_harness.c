/* Exact-function PC stub. It models API ordering, not hardware concurrency. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
typedef int irqreturn_t;
typedef irqreturn_t (*irq_handler_t)(int, void *);
typedef struct { int held; } spinlock_t;
struct mutex { int held; };
struct platform_device { void *data; };
struct zocl_ert_intc_handler {
    struct platform_device *zeih_pdev;
    spinlock_t zeih_lock;
    u32 zeih_irq;
    irq_handler_t zeih_cb;
    void *zeih_arg;
    bool zeih_enabled;
};
struct zocl_irq_intc {
    struct platform_device *zei_pdev;
#ifdef ORIGINAL
    spinlock_t zei_lock;
#else
    struct mutex zei_lock;
#endif
    int zei_num_irqs;
    struct zocl_ert_intc_handler zei_handler[2];
};
static int checks, irq_depth, atomic_api, errors, callbacks, request_calls, free_calls;
static int warns, request_failure, enable_calls, disable_calls;
static struct { irq_handler_t isr; void *arg; int depth; } slots[2];
#define CHECK(c) do { ++checks; assert(c); } while (0)
#define IRQ_HANDLED 1
#define IRQF_NO_AUTOEN 0x80000
#define ZINTC_DRV_NAME "test"
#define platform_get_drvdata(p) ((p)->data)
#define zintc_err(z, ...) do { (void)(z); ++errors; } while (0)
#define zintc_info(z, ...) do { (void)(z); } while (0)
#define WARN_ON_ONCE(c) ((c) ? (++warns, 1) : 0)
#define BUG_ON(c) CHECK(!(c))
#define spin_lock_irqsave(l, f) do { (f)=irq_depth; CHECK(!(l)->held); (l)->held=1; ++irq_depth; } while (0)
#define spin_unlock_irqrestore(l, f) do { CHECK((l)->held); (l)->held=0; irq_depth=(int)(f); } while (0)
static void sleepable(void) { if (irq_depth) ++atomic_api; }
#ifndef ORIGINAL
static void mutex_lock(struct mutex *m) { sleepable(); CHECK(!m->held); m->held=1; }
static void mutex_unlock(struct mutex *m) { CHECK(m->held); m->held=0; }
#endif
static void dispatch(unsigned id) {
    int saved=irq_depth;
    if (!slots[id].isr || slots[id].depth) return;
    /* Model a second CPU delivering an interrupt at the dangerous boundary. */
    irq_depth=0;
    slots[id].isr((int)id, slots[id].arg);
    irq_depth=saved;
}
static int request_irq(unsigned id, irq_handler_t isr, unsigned flags, const char *name, void *arg) {
    (void)name; sleepable(); ++request_calls; CHECK(id<2); CHECK(!slots[id].isr);
    if (request_failure) return -EIO;
    slots[id].isr=isr; slots[id].arg=arg; slots[id].depth=(flags & IRQF_NO_AUTOEN) ? 1:0;
    dispatch(id);
    return 0;
}
static void free_irq(unsigned id, void *arg) {
    sleepable(); ++free_calls; CHECK(slots[id].isr); CHECK(slots[id].arg==arg);
    /* A callback already in flight must still see live callback state. */
    dispatch(id);
    memset(&slots[id],0,sizeof(slots[id]));
}
static void enable_irq(unsigned id) { sleepable(); ++enable_calls; CHECK(slots[id].isr); CHECK(slots[id].depth>0); --slots[id].depth; dispatch(id); }
static void disable_irq(unsigned id) { sleepable(); ++disable_calls; CHECK(slots[id].isr); ++slots[id].depth; }
#include "irq_functions.inc"
static irqreturn_t callback(int irq, void *arg) { CHECK(irq>=0 && irq<2); CHECK(arg==&callbacks); ++callbacks; return IRQ_HANDLED; }
static void init(struct zocl_irq_intc *z, struct platform_device *p) {
    memset(z,0,sizeof(*z)); memset(slots,0,sizeof(slots));
    p->data=z; z->zei_pdev=p; z->zei_num_irqs=2;
    for (int i=0;i<2;i++) { z->zei_handler[i].zeih_pdev=p; z->zei_handler[i].zeih_irq=(unsigned)i; }
}
int main(void) {
    struct zocl_irq_intc z;
    struct platform_device p;
    init(&z,&p);
    CHECK(zocl_irq_intc_add(&p,0,callback,&callbacks)==0);
    int before=request_calls;
    CHECK(zocl_irq_intc_add(&p,0,callback,&callbacks)==-EINVAL);
    CHECK(request_calls==before);
    CHECK(zocl_irq_intc_add(&p,2,callback,&callbacks)==-EINVAL);
    zocl_irq_intc_config(&p,0,false);
    zocl_irq_intc_config(&p,0,true);
    zocl_irq_intc_remove(&p,0);
    CHECK(!z.zei_handler[0].zeih_cb && !slots[0].isr);
    request_failure=1;
    before=enable_calls;
    CHECK(zocl_irq_intc_add(&p,1,callback,&callbacks)==-EIO);
    CHECK(enable_calls==before && !z.zei_handler[1].zeih_cb && !slots[1].isr);
    request_failure=0;
#ifdef ORIGINAL
    CHECK(warns==0);
    CHECK(atomic_api>=4); CHECK(errors>=3);
    CHECK(zintc_remove(&p)==0);
    printf("BASELINE_REPRO checks=%d atomic_api=%d diagnostic_events=%d\n",checks,atomic_api,errors);
#else
    before=free_calls;
    zocl_irq_intc_remove(&p,0);
    zocl_irq_intc_config(&p,0,true);
    CHECK(free_calls==before);
    CHECK(zocl_irq_intc_add(&p,1,NULL,&callbacks)==-EINVAL);
    CHECK(zocl_irq_intc_add(&p,0,callback,&callbacks)==0);
    CHECK(zocl_irq_intc_add(&p,1,callback,&callbacks)==0);
    CHECK(zintc_remove(&p)==0);
    CHECK(!slots[0].isr && !slots[1].isr);
    CHECK(!z.zei_handler[0].zeih_cb && !z.zei_handler[1].zeih_cb);
    zocl_irq_intc_remove(&p,2); zocl_irq_intc_config(&p,2,false);
    CHECK(warns==2); CHECK(atomic_api==0); CHECK(errors==1); /* injected request failure */
    CHECK(irq_depth==0 && z.zei_lock.held==0);
    CHECK(callbacks>=6);
    printf("CANDIDATE_PASS checks=%d atomic_api=%d callback_boundaries=%d\n",checks,atomic_api,callbacks);
#endif
    return 0;
}
