// A-owned intake testbench. B source is compiled unchanged; expected values
// come from the already frozen A04 scalar reference, never from the DUT.
#include "w4a8_linear_v1.hpp"
#include "w4a8.hpp"
#include "linear_validation.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
using w4a8_b2::KernelMeta;
static_assert(sizeof(KernelMeta)==40 && offsetof(KernelMeta,job_id)==8 &&
 offsetof(KernelMeta,status)==16 && offsetof(KernelMeta,done)==20 &&
 offsetof(KernelMeta,hw_completed_count)==24 && offsetof(KernelMeta,algorithm_weight_bytes)==32,
 "private metadata offsets changed");
static unsigned checks=0, cases=0;
void need(bool ok,const char *message){++checks;if(!ok)throw std::runtime_error(message);}
template<class T> std::vector<T> read(const std::string&p,size_t count){
 std::vector<T> out(count);std::ifstream f(p,std::ios::binary);
 need(bool(f.read(reinterpret_cast<char*>(out.data()),count*sizeof(T))),"input file short/missing");
 need(f.peek()==EOF,"input file long");return out;
}
struct Data{
 a04::Shape s;std::vector<uint8_t>w;std::vector<float>sw,sx,y;
 std::vector<int8_t>x;KernelMeta meta{};
 Data(int n,int k,int t):s(n,k,t),w(size_t(s.np)*s.kp/2),sw(s.np*s.g,1),sx(t),y(t*s.np,-777),x(t*s.kp){
  meta.hw_completed_count=41;
  for(int row=0;row<n;++row)for(int col=0;col<k;++col){
   int q=(row*13+col*7+col/128*3)%15-7;
   w[((row/32*s.g+col/128)*128+col%128)*16+(row%32)/2]|=uint8_t((q&15)<<(4*(row%2)));
  }
  for(int row=0;row<n;++row)for(int g=0;g<s.g;++g)
   sw[(row/32*s.g+g)*32+row%32]=float(1+(row+g*3)%13)/37.0f;
  for(int token=0;token<t;++token){sx[token]=float(token+1)/127.0f;
   for(int col=0;col<k;++col)x[token*s.kp+col]=int8_t((col*19+token*31)%255-127);
  }
 }
 host_b::Request request(){return {uint32_t(s.t),uint32_t(s.n),uint32_t(s.k),w.data(),sw.data(),x.data(),sx.data(),y.data(),
  w.size(),sw.size()*4,x.size(),sx.size()*4,y.size()*4,0x1234567887654321ULL};}
 void call(host_b::Request r,uint64_t mb=40,uint32_t abi=1,KernelMeta*m=nullptr){
  w4a8_linear_v1(r.w,r.sw,r.x,r.sx,r.y,m?m:&meta,r.t,r.n,r.k,r.wb,r.swb,r.xb,r.sxb,r.yb,mb,r.job,abi);
 }
};
void valid(Data&d,const std::string&name){
 const auto&a=d.s;std::cout<<"BEGIN "<<name<<" N="<<a.n<<" K="<<a.k<<" T="<<a.t<<std::endl;
 a04::validate(a,d.w,d.sw,d.x,d.sx);
 std::vector<float>expected(a.t*a.np);std::vector<int32_t>sums(a.t*a.np*a.g);
 a04::scalar(a,d.w.data(),d.sw.data(),d.x.data(),d.sx.data(),expected.data(),sums.data());
 // Observe the actual MAC helper called by both B decode and prefill paths.
 // This is C/Csim helper evidence, NOT a probe of internal RTL signals.
 uint64_t sum_count=0;
 for(int token=0;token<a.t;++token)for(int tile=0;tile<a.np/32;++tile)for(int g=0;g<a.g;++g){
  int32_t actual[32];w4a8_tile_group_sums(d.w.data()+(tile*a.g+g)*2048,d.x.data()+token*a.kp+g*128,actual);
  for(int lane=0;lane<32;++lane){need(actual[lane]==sums[(token*a.np+tile*32+lane)*a.g+g],"INT32 group mismatch");++sum_count;}
 }
 auto r=d.request();need(host_b::validate(r)==SP_OK,"host rejected valid data");
 auto before=d.meta.hw_completed_count;d.call(r);
 need(d.meta.abi_magic==w4a8_b2::kAbiMagic && d.meta.kernel_build_id==w4a8_b2::kKernelBuildId &&
  d.meta.job_id==r.job && d.meta.status==0 && d.meta.done==1 && d.meta.hw_completed_count==before+1 &&
  d.meta.algorithm_weight_bytes==d.w.size(),"success metadata mismatch");
 double maxerr=0;uint64_t bitdiff=0;
 for(size_t i=0;i<expected.size();++i){
  double err=std::abs(double(d.y[i])-expected[i]);maxerr=std::max(maxerr,err);
  need(std::isfinite(d.y[i])&&err<=1e-4+1e-5*std::abs(expected[i]),"FP32 mismatch");
  bitdiff+=std::memcmp(&d.y[i],&expected[i],4)!=0;
  if(i%a.np>=size_t(a.n))need(d.y[i]==0,"N tail not zero");
 }
 ++cases;std::cout<<"RESULT {\"case\":\""<<name<<"\",\"N\":"<<a.n<<",\"K\":"<<a.k<<",\"T\":"<<a.t
  <<",\"status\":\"PASS\",\"int32_compared\":"<<sum_count<<",\"max_abs_error\":"<<maxerr
  <<",\"fp32_bit_differences\":"<<bitdiff<<"}"<<std::endl;
}
void errors(){
 for(int mode=0;mode<18;++mode){Data d(33,129,1);auto r=d.request();uint32_t expected=0,abi=1;uint64_t mb=40;
  if(mode<6){if(mode==0)r.t=0;if(mode==1)r.t=9;if(mode==2)r.n=0;if(mode==3)r.k=0;
   if(mode==4)r.n=0xffffffffU;if(mode==5)r.k=4865;expected=2;}
  if(mode>=6&&mode<=10){if(mode==6)--r.wb;if(mode==7)--r.swb;if(mode==8)--r.xb;if(mode==9)--r.sxb;if(mode==10)--r.yb;expected=3;}
  if(mode==11){abi=99;expected=1;}
  if(mode==12){r.w=nullptr;expected=4;}
  if(mode==13){d.w[0]=(d.w[0]&0xf0)|8;expected=5;}
  if(mode==14){d.w[0]=(d.w[0]&0x0f)|0x80;expected=5;}
  if(mode==15){mb=39;d.meta.status=777;expected=777;}
  if(mode==16){r.x=nullptr;expected=4;}
  if(mode==17){r.sw=nullptr;expected=4;}
  d.call(r,mb,abi);need(d.meta.status==expected,"private error status");
  need(d.meta.hw_completed_count==41,"error incremented count");
  for(float y:d.y)need(y==-777,"error wrote Y");
  if(mode!=15)need(d.meta.done==1 && d.meta.job_id==r.job,"error metadata");
  ++cases;std::cout<<"RESULT {\"case\":\"kernel_error_"<<mode<<"\",\"status\":\"PASS\",\"y_consumed\":false}"<<std::endl;
 }
 // Public invalid numeric content is explicitly a host responsibility in B's
 // private ABI. Do not demand nonexistent private status codes or feed it DMA.
 for(int mode=0;mode<10;++mode){Data d(33,129,1);auto r=d.request();
  if(mode==0)d.x[0]=-128;if(mode==1)d.sw[0]=std::numeric_limits<float>::quiet_NaN();
  if(mode==2)d.sx[0]=std::numeric_limits<float>::infinity();if(mode==3)d.sx[0]=0;
  if(mode==4)d.sw[0]=-1;if(mode==5)d.x[129]=1;
  if(mode==6)d.w[(1*2+0)*2048]|=0x10; // padded output lane 33
  if(mode==7)d.sw[(1*2)*32+1]=2;
  if(mode==8)r.job=0;if(mode==9)r.wb=0;
  need(host_b::validate(r)!=SP_OK,"host accepted invalid public input");
  need(d.meta.hw_completed_count==41,"rejected host request launched");
  for(float y:d.y)need(y==-777,"host error wrote Y");
  ++cases;std::cout<<"RESULT {\"case\":\"host_reject_"<<mode<<"\",\"status\":\"PASS\",\"kernel_launched\":false}"<<std::endl;
 }
}
int main(int argc,char**argv){try{
 need(argc==3,"usage: test fixture-dir sidecar-dir");a04::environment();
 Data hand(2,2,1);std::string f=argv[1];
 hand.w=read<uint8_t>(f+"/w_packed.bin",2048);hand.sw=read<float>(f+"/sw.bin",32);
 hand.x=read<int8_t>(f+"/xq.bin",128);hand.sx=read<float>(f+"/sx.bin",1);
 need(hand.w[0]==0x97 && hand.w[16]==0x2f,"hand bytes");valid(hand,"hand");
 need(hand.y[0]==890 && hand.y[1]==-891,"manual expected");valid(hand,"repeat_call");
 for(int t=1;t<=8;++t){Data tail(33,129,t);valid(tail,"tail_cross_scale");}
 for(int t=1;t<=8;++t)for(int shape=0;shape<2;++shape){Data d(shape?1024:3584,shape?3584:1024,t);valid(d,shape?"down_synthetic":"gate_synthetic");}
 Data zero(33,129,8);std::fill(zero.w.begin(),zero.w.end(),0);valid(zero,"zero_group");
 Data extreme(32,128,1);std::fill(extreme.w.begin(),extreme.w.end(),0x77);std::fill(extreme.x.begin(),extreme.x.end(),127);valid(extreme,"int32_bound_113792");
 Data order(1,384,1);std::fill(order.w.begin(),order.w.end(),0);std::fill(order.x.begin(),order.x.end(),0);
 order.w[0]=1;order.w[2048]=1;order.w[4096]=15;order.x[0]=order.x[128]=order.x[256]=1;
 order.sw[0]=16777216;order.sw[32]=1;order.sw[64]=16777216;order.sx[0]=1;
 valid(order,"fp32_group_order");need(order.y[0]==0,"FP32 order expected zero");
 for(int shape=0;shape<2;++shape)for(int t:{1,8}){Data d(shape?1024:3584,shape?3584:1024,t);
  std::string prefix=std::string(argv[2])+(shape?"/l00_down":"/l00_gate");
  d.w=read<uint8_t>(prefix+".w.bin",d.w.size());d.sw=read<float>(prefix+".sw.bin",d.sw.size());
  valid(d,shape?"real_weight_down_synthetic_activation":"real_weight_gate_synthetic_activation");
 }
 errors();std::cout<<"SUMMARY {\"status\":\"PASS\",\"cases\":"<<cases<<",\"checks\":"<<checks
  <<",\"build_id\":"<<w4a8_b2::kKernelBuildId<<",\"board\":\"NOT_TESTED\"}"<<std::endl;return 0;
}catch(const std::exception&e){std::cerr<<"FAIL minimal reproduction: last BEGIN/RESULT, deterministic A06 acceptance.cpp: "<<e.what()<<std::endl;return 1;}}
