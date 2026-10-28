// A04 independent math on decoded original RTL data. No B kernel/golden linked.
#include "w4a8.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
namespace fs=std::filesystem;
using Bytes=std::vector<uint8_t>;
void need(bool b,const char*m){if(!b)throw std::runtime_error(m);}
Bytes read(fs::path p){std::ifstream f(p,std::ios::binary);need(bool(f),"missing input");return Bytes(std::istreambuf_iterator<char>(f),{});}
template<class T> std::vector<T> values(const Bytes&b,size_t n){need(b.size()>=n*sizeof(T),"short buffer");std::vector<T> v(n);std::memcpy(v.data(),b.data(),n*sizeof(T));return v;}
struct Meta{uint32_t magic,build;uint64_t job;uint32_t status,done;uint64_t count,bytes;};
static_assert(sizeof(Meta)==40);
int main(int argc,char**argv){try{
 need(argc==2,"usage: replay directory");a04::environment();fs::path p=argv[1];
 uint64_t t,n,k,abi,wb,swb,xb,sxb,yb,mb,job;
 std::ifstream req(p/"request.txt");need(bool(req>>t>>n>>k>>abi>>wb>>swb>>xb>>sxb>>yb>>mb>>job),"bad request");
 auto w=read(p/"w.bin"),sb=read(p/"sw.bin"),xx=read(p/"x.bin"),ss=read(p/"sx.bin");
 auto before=read(p/"y_before.bin"),actual=read(p/"y_actual.bin"),prior=read(p/"meta_before.bin"),ma=read(p/"meta_actual.bin");
 need(prior.size()==40&&ma.size()==40&&before.size()==actual.size(),"meta/Y length");
 Meta prev;std::memcpy(&prev,prior.data(),40);Meta expected{0x57344138,0xB3030002,job,0,1,prev.count,0};
 uint64_t np=0,kp=0,g=0,compared=0;double maxerr=0;bool success=false;
 if(mb<40)expected=prev;
 else if(abi!=1)expected.status=1;
 else if(!t||t>8||!n||n>4864||!k||k>4864)expected.status=2;
 else{
  np=(n+31)/32*32;kp=(k+127)/128*128;g=kp/128;expected.bytes=np*kp/2;
  if(wb<expected.bytes||swb<np*g*4||xb<t*kp||sxb<t*4||yb<t*np*4)expected.status=3;
  else{
   need(w.size()>=expected.bytes,"short W");
   for(size_t r=0;r<n;++r)for(size_t c=0;c<k;++c){size_t i=((r/32*g+c/128)*128+c%128)*16+r%32/2;if(((w[i]>>(r%2*4))&15)==8)expected.status=5;}
   success=expected.status==0;
  }
 }
 if(success){
  a04::Shape shape(n,k,t);w.resize(expected.bytes);auto sw=values<float>(sb,np*g),sx=values<float>(ss,t);auto x=values<int8_t>(xx,t*kp);
  // Private boundary probes may deliberately poison padding. Canonicalize only
  // ineffective cells to express the mathematical valid N/K region in A04.
  for(size_t r=0;r<np;++r)for(size_t c=0;c<kp;++c)if(r>=n||c>=k){size_t i=((r/32*g+c/128)*128+c%128)*16+r%32/2;w[i]&=uint8_t(~(15<<(r%2*4)));}
  for(size_t r=n;r<np;++r)for(size_t j=0;j<g;++j)sw[(r/32*g+j)*32+r%32]=1;
  for(size_t row=0;row<t;++row)for(size_t c=k;c<kp;++c)x[row*kp+c]=0;
  std::vector<float> ref(t*np);std::vector<int32_t>sums(t*np*g);
  a04::scalar(shape,w.data(),sw.data(),x.data(),sx.data(),ref.data(),sums.data());
  auto y=values<float>(actual,t*np);double atol,rtol;std::ifstream tol(p/"tolerance.txt");need(bool(tol>>atol>>rtol),"tolerance missing");
  need(atol<=1e-4&&rtol<=1e-5,"loosened tolerance");
  for(size_t i=0;i<ref.size();++i){double err=std::abs(double(y[i])-ref[i]);need(std::isfinite(y[i])&&err<=atol+rtol*std::abs(ref[i]),"A04 RTL Y mismatch");maxerr=std::max(maxerr,err);if(i%np>=n)need(y[i]==0,"nonzero N tail");}
  need(std::equal(before.begin()+ref.size()*4,before.end(),actual.begin()+ref.size()*4),"write outside Y");
  auto partials=read(p/"expected_partials.bin");need(partials.size()==sums.size()*4,"partials length");need(!std::memcmp(partials.data(),sums.data(),partials.size()),"A04 versus B independent partials mismatch");compared=sums.size();++expected.count;
 }else need(before==actual,"error modified Y");
 need(!std::memcmp(&expected,ma.data(),40),"A04 RTL metadata mismatch");
 std::cout<<"{\"status\":\"PASS\",\"kernel_status\":"<<expected.status<<",\"T\":"<<t<<",\"N\":"<<n<<",\"K\":"<<k<<",\"reference_int32_compared\":"<<compared<<",\"max_abs_error\":"<<maxerr<<",\"rtl_internal_partials_observed\":false}"<<std::endl;
 return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
