/* PC-only controlled dependency stubs. functions.inc contains exact extracted
 * kernel function bodies, not a rewritten Python model. No MMIO or device I/O.
 * This does not model interrupt concurrency or prove board recovery safety. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
typedef uint32_t __be32;
struct device_node { int refs; void *data; };
struct of_phandle_args { struct device_node *np; u32 args[8]; int args_count; };
struct irq_domain { unsigned int mapcount; unsigned char mapped[32]; };
struct xintc_irq_chip { void *base; struct irq_domain *root_domain; u32 nr_irq; int irq; };
static struct device_node parent;
static struct irq_domain domain;
static int extended, raw_error, mapping_error, parse_error;
static int of_irq_workarounds, parent_disposed, domain_removed, freed, unmapped;
static unsigned int checks;
#define EINVAL 22
#define OF_IMAP_OLDWORLD_MAC 1
#define IER 8
#define IAR 12
#define MER 28
#define pr_debug(...) ((void)0)
#define VERIFY(expr) do { checks++; if (!(expr)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#expr); exit(1); } } while (0)
static void of_node_put(struct device_node *n) { if (n) { assert(n->refs>0); n->refs--; } }
static int of_irq_parse_oldworld(struct device_node *d,int i,struct of_phandle_args *a)
{ (void)d;(void)i;(void)a;return -EINVAL; }
static const __be32 *of_get_property(struct device_node *d,const char *s,void *l)
{ static __be32 addr; (void)d;(void)s;(void)l;return &addr; }
static int of_parse_phandle_with_args(struct device_node *d,const char *s,const char *c,int i,struct of_phandle_args *a)
{ (void)d;(void)s;(void)c;(void)i;if (!extended || parse_error)return -EINVAL;
  parent.refs++;a->np=&parent;a->args_count=2;return 0; }
static struct device_node *of_irq_find_parent(struct device_node *d)
{ (void)d;if(parse_error)return NULL;parent.refs++;return &parent; }
static int of_property_read_u32(struct device_node *d,const char *s,u32 *v)
{ (void)d;(void)s;*v=2;return 0; }
static int of_property_read_u32_index(struct device_node *d,const char *s,int i,u32 *v)
{ (void)d;(void)s;*v=(u32)i;return 0; }
static int of_irq_parse_raw(const __be32 *addr,struct of_phandle_args *a)
{ (void)addr;a->np->refs++; if(raw_error) { of_node_put(a->np);return -EINVAL;}return 0; }
static unsigned int irq_create_of_mapping(struct of_phandle_args *a)
{ (void)a;return mapping_error?0:77; }
static void irq_set_chained_handler_and_data(int irq,void *handler,void *data)
{ (void)irq;(void)handler;(void)data; }
static unsigned int irq_find_mapping(struct irq_domain *d,unsigned int i)
{ assert(i<32);return d->mapped[i]?i+1:0; }
static void irq_dispose_mapping(unsigned int irq)
{ if(irq==100){parent_disposed++;return;} assert(irq>0 && irq<=32);
  assert(domain.mapped[irq-1]);domain.mapped[irq-1]=0;domain.mapcount--; }
static void irq_domain_remove(struct irq_domain *d) { (void)d;domain_removed++; }
static void xintc_write(struct xintc_irq_chip *c,int reg,u32 val) { (void)c;(void)reg;(void)val; }
static void iounmap(void *p) { (void)p;unmapped++; }
static void kfree(void *p) { (void)p;freed++; }
#include "functions.inc"

static void reset_refs(int ext,int fail,int mapfail)
{ memset(&parent,0,sizeof(parent));parent.refs=1;extended=ext;raw_error=fail;
  mapping_error=mapfail;parse_error=0; }
static void test_refs(void)
{
 struct device_node device={0};struct of_phandle_args args;
 for(int ext=0;ext<2;ext++) for(int fail=0;fail<2;fail++) {
  reset_refs(ext,fail,0);int result=of_irq_parse_one(&device,0,&args);
  VERIFY(result==(fail?-EINVAL:0));if(!result)of_node_put(args.np);
  VERIFY(parent.refs==(FIXED?1:1+ext));
 }
 for(int ext=0;ext<2;ext++) for(int fail=0;fail<2;fail++) {
  reset_refs(ext,0,fail);unsigned int result=irq_of_parse_and_map(&device,0);
  VERIFY(result==(fail?0:77));VERIFY(parent.refs==(FIXED?1:2+ext));
 }
 reset_refs(1,0,0);parse_error=1;
 VERIFY(irq_of_parse_and_map(&device,0)==0);VERIFY(parent.refs==1);
 reset_refs(1,0,0);
 for(int pass=0;pass<2;pass++)for(int i=0;i<32;i++) {
  VERIFY(of_irq_parse_one(&device,i,&args)==0);of_node_put(args.np);
 }
 VERIFY(parent.refs==(FIXED?1:65));
}
static void test_remove(void)
{
 const uint32_t masks[]={0,1,0x80000000u,0x80000001u,0xffffffffu};
 const unsigned int original_left[]={0,0,1,1,16};
 for(unsigned int t=0;t<sizeof(masks)/sizeof(masks[0]);t++) {
  memset(&domain,0,sizeof(domain));parent_disposed=domain_removed=freed=unmapped=0;
  for(unsigned int i=0;i<32;i++)if(masks[t]&(1u<<i)){domain.mapped[i]=1;domain.mapcount++;}
  struct xintc_irq_chip chip={.root_domain=&domain,.nr_irq=32,.irq=100};
  struct device_node intc={.data=&chip};
  VERIFY(xilinx_intc_of_remove(&intc,&parent)==0);
  VERIFY(domain.mapcount==(FIXED?0:original_left[t]));
  VERIFY(parent_disposed==1 && domain_removed==1 && freed==1 && unmapped==1);
 }
 struct device_node intc={0};int old=freed;
 VERIFY(xilinx_intc_of_remove(&intc,NULL)==0);VERIFY(freed==old);
}
int main(void)
{test_refs();test_remove();printf("PC_STUBBED_EXACT_FUNCTIONS fixed=%d checks=%u PASS; no IRQ concurrency/BOARD proof\n",FIXED,checks);return 0;}
