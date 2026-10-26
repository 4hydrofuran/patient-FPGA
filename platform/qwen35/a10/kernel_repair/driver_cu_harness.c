/* Extracted CU probe/remove control flow with deterministic failure injection. */
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
static int checks, init_order, free_order, sysfs_order, active_irq, kds_entries;
static int alloc_count, fail_alloc, fail_core, fail_irq, logs;
static void *allocs[8];
#define CHECK(c) do { ++checks; assert(c); } while (0)
#define GFP_KERNEL 0
#define IORESOURCE_MEM 0
#define XCU_HLS 1
#define XCU_FA 2
#define CTRL_NONE 0
#define ERT_CU_INTC_DEV_NAME "intc"
struct xrt_cu_info { int num_res,model,protocol,intr_enable,intr_id,inst_idx; };
struct resource { int unused; };
struct device { int kobj; struct xrt_cu_info *pdata; };
struct platform_device { struct device dev; void *data; };
struct xrt_cu {
    struct device *dev;
    struct xrt_cu_info info;
    struct resource **res;
    int (*user_manage_irq)(struct xrt_cu *,bool);
    int (*configure_irq)(struct xrt_cu *,bool);
    int force_intr;
    bool core_alive;
};
struct zocl_cu { struct platform_device *pdev; struct xrt_cu base; char *irq_name; int attr_rwlock; };
struct drm_zocl_dev { int unused; };
struct xrt_cu_arg { int unused; };
static struct drm_zocl_dev zdev;
static struct resource res;
static struct platform_device intc;
static struct zocl_cu *current;
static int cu_attrgroup;
#define dev_get_platdata(d) ((d)->pdata)
#define platform_get_drvdata(p) ((p)->data)
#define platform_set_drvdata(p,d) ((p)->data=(d))
#define DRM_ERROR(...) do { ++logs; } while (0)
#define DRM_WARN(...) do { ++logs; } while (0)
#define zocl_err(d,...) do { (void)(d); ++logs; } while (0)
#define zocl_info(d,...) do { (void)(d); } while (0)
static void *allocate(size_t n) {
    ++alloc_count;
    if (alloc_count==fail_alloc) return NULL;
    void *p=calloc(1,n); CHECK(p);
    for (unsigned i=0;i<8;i++) if (!allocs[i]) { allocs[i]=p; return p; }
    abort();
}
static void *kzalloc(size_t n,int g) { (void)g; return allocate(n); }
static void *vzalloc(size_t n) { return allocate(n); }
static void kfree(void *p) {
    if (!p) return;
    for (unsigned i=0;i<8;i++) if (allocs[i]==p) { free(p); allocs[i]=NULL; return; }
    abort();
}
#define vfree kfree
static int live_allocs(void) { int n=0; for(unsigned i=0;i<8;i++) n+=allocs[i]!=NULL; return n; }
static struct resource *platform_get_resource(struct platform_device *p,int type,int i) { (void)p;(void)type;(void)i;return &res; }
static struct drm_zocl_dev *zocl_get_zdev(void) { return &zdev; }
static int zocl_kds_add_cu(struct drm_zocl_dev *d,struct xrt_cu *c) { (void)d;(void)c;++kds_entries;return 0; }
static int zocl_kds_del_cu(struct drm_zocl_dev *d,struct xrt_cu *c) { (void)d;(void)c;--kds_entries;return 0; }
static struct platform_device *zocl_find_pdev(const char *name) { return strcmp(name,"intc")==0?&intc:NULL; }
static int cu_isr(int irq,void *arg) { (void)irq;(void)arg;return 1; }
static int zocl_ert_intc_add(struct platform_device *p,int id,int(*cb)(int,void*),void *arg) {
    (void)p;(void)id;(void)cb; current=arg;
    if (!current->base.core_alive) ++init_order;
    if (fail_irq) return -EIO;
    active_irq=1; return 0;
}
static void zocl_ert_intc_remove(struct platform_device *p,int id) {
    (void)p;(void)id; CHECK(active_irq);
    if (!current->base.core_alive) ++free_order;
    active_irq=0;
}
static int xrt_cu_hls_init(struct xrt_cu *c) { if(fail_core)return -ENOMEM;c->core_alive=true;return 0; }
static int xrt_cu_fa_init(struct xrt_cu *c) { return xrt_cu_hls_init(c); }
static void xrt_cu_hls_fini(struct xrt_cu *c) { if(active_irq)++free_order;c->core_alive=false; }
static void xrt_cu_fa_fini(struct xrt_cu *c) { xrt_cu_hls_fini(c); }
static void rwlock_init(int *l) { *l=0; }
#ifdef ORIGINAL
static void write_lock(int *l) { CHECK(!*l); *l=1; }
static void write_unlock(int *l) { CHECK(*l); *l=0; }
#endif
static int sysfs_create_group(int *k,int *g) { (void)k;(void)g;return 0; }
static void sysfs_remove_group(int *k,int *g) {
    (void)k;(void)g;
    if(current->attr_rwlock || !current->base.core_alive) ++sysfs_order;
}
static int user_manage_irq(struct xrt_cu *c,bool b) { (void)c;(void)b;return 0; }
static int configure_irq(struct xrt_cu *c,bool b) { (void)c;(void)b;return 0; }
#include "cu_functions.inc"
static void reset_fixture(void) {
    for(unsigned i=0;i<8;i++) { free(allocs[i]); allocs[i]=NULL; }
    active_irq=kds_entries=alloc_count=fail_alloc=fail_core=fail_irq=0;
    current=NULL;
}
int main(void) {
    struct xrt_cu_info info={.num_res=1,.model=XCU_HLS,.protocol=1,.intr_enable=1,.intr_id=1};
    struct platform_device p={.dev={.pdata=&info}};
    CHECK(cu_probe(&p)==0); current=p.data;
    CHECK(active_irq==1 && kds_entries==1);
    CHECK(cu_remove(&p)==0); CHECK(!active_irq && !kds_entries && !live_allocs());
    reset_fixture(); fail_core=1;
    CHECK(cu_probe(&p)==-ENOMEM);
#ifdef ORIGINAL
    CHECK(active_irq==1); /* baseline registers callback then frees failed CU */
#else
    CHECK(!active_irq && !kds_entries && !live_allocs());
#endif
    reset_fixture(); fail_alloc=3;
    CHECK(cu_probe(&p)==-ENOMEM);
#ifdef ORIGINAL
    CHECK(kds_entries==1 && live_allocs()==2);
#else
    CHECK(!kds_entries && !live_allocs() && !active_irq);
#endif
    reset_fixture(); fail_irq=1;
    CHECK(cu_probe(&p)==0); current=p.data;
    CHECK(!current->base.info.intr_enable && !active_irq);
    CHECK(cu_remove(&p)==0); CHECK(!live_allocs() && !kds_entries);
    reset_fixture(); info.model=XCU_FA;
    CHECK(cu_probe(&p)==0); current=p.data;
    CHECK(cu_remove(&p)==0); CHECK(!live_allocs());
#ifdef ORIGINAL
    CHECK(init_order>0 && free_order>0 && sysfs_order>0);
    printf("BASELINE_CU_REPRO checks=%d init_order=%d free_order=%d sysfs_order=%d\n",checks,init_order,free_order,sysfs_order);
#else
    CHECK(init_order==0 && free_order==0 && sysfs_order==0);
    printf("CANDIDATE_CU_PASS checks=%d\n",checks);
#endif
    reset_fixture(); return 0;
}
