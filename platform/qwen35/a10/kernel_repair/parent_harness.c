/* PC devres ownership model around exact original/candidate probe/remove C.
 * No interrupts, device binding or hardware. Device-core cleanup is stubbed. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define EINVAL 22
#define ENOMEM 12
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define DOMAIN_BUS_ANY 0
struct device_node { int refs; };
struct device { struct device_node *of_node; };
struct platform_device { struct device dev; void *data; };
typedef int (*of_irq_init_cb_t)(struct device_node *, struct device_node *);
typedef int (*of_irq_remove_cb_t)(struct device_node *, struct device_node *);
struct platform_irqchip_instance { of_irq_init_cb_t irq_init_cb; of_irq_remove_cb_t irq_remove_cb; struct device_node *parent_node; };
struct irqc_init_remove_funps { of_irq_init_cb_t irqchip_initp; of_irq_remove_cb_t irqchip_removep; };
static struct platform_irqchip_instance storage;
static struct device_node node, parent;
static int parent_mode, allocation_fail, action_fail, missing_callback, deferred, init_fail;
static void (*cleanup)(void *);
static void *cleanup_data;
static unsigned checks;
#define VERIFY(expr) do {checks++; if(!(expr)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#expr);exit(1);}}while(0)
#if FIXED
static void of_node_put(struct device_node *p) {if(p){assert(p->refs>0);p->refs--;}}
#endif
static struct device_node *of_irq_find_parent(struct device_node *p)
{if(parent_mode==0)return NULL;struct device_node *q=parent_mode==1?&parent:p;q->refs++;return q;}
static void *devm_kzalloc(struct device *d,size_t n,int f)
{(void)d;(void)n;(void)f;return allocation_fail?NULL:&storage;}
static void platform_set_drvdata(struct platform_device *p,void *d){p->data=d;}
static void *platform_get_drvdata(struct platform_device *p){return p->data;}
static int callback_init(struct device_node *n,struct device_node *p)
{(void)n; if(parent_mode==1)VERIFY(p==&parent && p->refs==2);return init_fail?-EINVAL:0;}
static int callback_remove(struct device_node *n,struct device_node *p)
{(void)n;if(parent_mode==1)VERIFY(p==&parent && p->refs==2);return 0;}
static const void *of_device_get_match_data(struct device *d)
{static struct irqc_init_remove_funps f;(void)d;f.irqchip_initp=missing_callback?NULL:callback_init;
 f.irqchip_removep=callback_remove;return &f;}
static void *irq_find_matching_host(struct device_node *n,int b)
{(void)n;(void)b;return deferred?NULL:&storage;}
#if FIXED
static int devm_add_action_or_reset(struct device *d,void (*f)(void *),void *data)
{(void)d;if(action_fail){f(data);return -ENOMEM;}cleanup=f;cleanup_data=data;return 0;}
#endif
#include "parent_functions.inc"
int main(void)
{
 for(parent_mode=0;parent_mode<3;parent_mode++)
 for(allocation_fail=0;allocation_fail<2;allocation_fail++)
 for(action_fail=0;action_fail<2;action_fail++)
 for(missing_callback=0;missing_callback<2;missing_callback++)
 for(deferred=0;deferred<2;deferred++)
 for(init_fail=0;init_fail<2;init_fail++) {
  node.refs=parent.refs=1;memset(&storage,0,sizeof(storage));cleanup=NULL;cleanup_data=NULL;
  struct platform_device p={.dev={.of_node=&node}};
  int result=platform_irqchip_probe(&p);
  if(result==0)VERIFY(platform_irqchip_remove(&p)==0);
  /* Kernel devres release on both probe failure and driver detach. */
  if(cleanup)cleanup(cleanup_data);
  VERIFY(node.refs==(FIXED?1:(parent_mode==2?2:1)));
  VERIFY(parent.refs==(FIXED?1:(parent_mode==1?2:1)));
 }
 printf("PC_STUBBED_PARENT_OWNERSHIP fixed=%d checks=%u PASS; no device-core/IRQ concurrency proof\n",FIXED,checks);
 return 0;
}
