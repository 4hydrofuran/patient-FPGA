// B01 真实第一层权重的电脑回放；输入激活由固定seed生成，不是模型真实激活。
#include "../../src/w4a8_linear_v1.hpp"
#include "../../tb/golden_w4a8.hpp"
#include "../../reference/quantization.hpp"
#include "../../host/linear_validation.hpp"
#include <fstream>
#include <iostream>
#include <limits>
#include <string>

// 文件大小必须精确匹配固定模型张量，避免错误切片仍被接受。
std::vector<float> read_weights(const std::string& path, std::size_t count) {
    std::ifstream file(path,std::ios::binary);
    std::vector<float> values(count);
    if(!file.read(reinterpret_cast<char*>(values.data()),count*sizeof(float)) || file.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("raw tensor length: "+path);
    return values;
}

// 输出保存实际字节，不把seed当作文件hash的替代品。
template<typename T> void save(const std::string& path, const std::vector<T>& values) {
    std::ofstream file(path,std::ios::binary);
    file.write(reinterpret_cast<const char*>(values.data()),values.size()*sizeof(T));
    if(!file) throw std::runtime_error("cannot save: "+path);
}

// 随机算法与seed固定，生成普通合成FP32输入后逐行量化。
std::uint32_t advance(std::uint32_t& state) {
    state^=state<<13U;state^=state>>17U;state^=state<<5U;return state;
}

int main() {
    try {
        static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559,"IEEE FP32 required");
        std::uint64_t partial_checks=0,output_checks=0;
        for(unsigned shape=0;shape<2;++shape) {
            const std::uint32_t n=shape==0 ? 3584U : 1024U;
            const std::uint32_t k=shape==0 ? 1024U : 3584U;
            const std::uint32_t groups=k/128U;
            const std::string kind=shape==0 ? "gate_proj" : "down_proj";
            const auto raw_weights=read_weights("vectors/model_source/"+kind+".fp32.bin",static_cast<std::size_t>(n)*k);
            std::vector<std::int8_t> dense_w;
            std::vector<float> dense_sw;
            reference_b::quantize_weights(raw_weights,n,k,dense_w,dense_sw);
            // 物理打包遍历与golden行主序计算分离，不共享核地址函数。
            std::vector<std::uint8_t> packed;packed.reserve(static_cast<std::size_t>(n)*k/2U);
            std::vector<float> sw;
            for(unsigned block=0;block<n/32U;++block) {
                for(unsigned group=0;group<groups;++group) {
                    for(unsigned lane=0;lane<32;++lane) sw.push_back(dense_sw[static_cast<std::size_t>(block*32U+lane)*groups+group]);
                    for(unsigned j=0;j<128;++j) {
                        for(unsigned pair=0;pair<16;++pair) {
                            const unsigned row=block*32U+pair*2U;
                            const unsigned col=group*128U+j;
                            const std::uint8_t lo=static_cast<std::uint8_t>(dense_w[static_cast<std::size_t>(row)*k+col])&15U;
                            const std::uint8_t hi=static_cast<std::uint8_t>(dense_w[static_cast<std::size_t>(row+1U)*k+col])&15U;
                            packed.push_back(lo|(hi<<4U));
                        }
                    }
                }
            }
            for(unsigned t:{1U,8U}) {
                const std::uint32_t seed=0x20261002U+shape*256U+t;
                auto state=seed;
                std::vector<float> raw_x(static_cast<std::size_t>(t)*k);
                for(auto& value:raw_x) value=static_cast<float>(static_cast<int>(advance(state)%2001U)-1000)/1000.0F;
                std::vector<std::int8_t> x;
                std::vector<float> sx;
                reference_b::quantize_inputs(raw_x,t,k,x,sx);
                const auto expected=golden_dense(t,n,k,n,k,dense_w,dense_sw,x,sx);
                std::vector<float> y(expected.y.size()+1U,-1234.5F);
                const host_b::Request request{t,n,k,packed.data(),sw.data(),x.data(),sx.data(),y.data(),packed.size(),sw.size()*4U,x.size(),sx.size()*4U,expected.y.size()*4U,seed};
                if(host_b::validate(request)!=SP_OK) throw std::runtime_error("real-weight public validation");
                const std::string prefix="vectors/b01_real/"+kind+"_t"+std::to_string(t);
                // 在调用核之前保存独立数学输入与expected，失败仍有完整复现载荷。
                save(prefix+".w_packed.bin",packed);save(prefix+".sw.bin",sw);save(prefix+".xq.bin",x);save(prefix+".sx.bin",sx);
                save(prefix+".dense_w.bin",dense_w);save(prefix+".dense_sw.bin",dense_sw);save(prefix+".expected_y.bin",expected.y);save(prefix+".expected_partials.bin",expected.partials);
                w4a8_b2::KernelMeta meta{};
                w4a8_linear_v1(packed.data(),sw.data(),x.data(),sx.data(),y.data(),&meta,t,n,k,packed.size(),sw.size()*4U,x.size(),sx.size()*4U,expected.y.size()*4U,40,seed,1);
                if(meta.status!=0 || meta.done!=1 || meta.job_id!=seed || meta.kernel_build_id!=0xB3010001U || meta.hw_completed_count!=1 || y.back()!=-1234.5F) throw std::runtime_error("real tensor meta/guard");
                for(unsigned token=0;token<t;++token) {
                    for(unsigned block=0;block<n/32U;++block) {
                        for(unsigned group=0;group<groups;++group) {
                            std::int32_t observed[32];
                            w4a8_tile_group_sums(packed.data()+(static_cast<std::size_t>(block)*groups+group)*2048U,x.data()+static_cast<std::size_t>(token)*k+group*128U,observed);
                            for(unsigned lane=0;lane<32;++lane) {
                                if(observed[lane]!=expected.partials[(static_cast<std::size_t>(token)*n+block*32U+lane)*groups+group]) throw std::runtime_error("real tensor INT32 partial");
                                ++partial_checks;
                            }
                        }
                    }
                }
                double square_error=0,square_reference=0;
                float max_error=0;
                for(std::size_t i=0;i<expected.y.size();++i) {
                    if(!std::isfinite(y[i]) || std::fabs(y[i]-expected.y[i])>1.0e-4F+1.0e-5F*std::fabs(expected.y[i])) throw std::runtime_error("real tensor FP32 output");
                    const double delta=static_cast<double>(y[i])-expected.y[i];
                    square_error+=delta*delta;square_reference+=static_cast<double>(expected.y[i])*expected.y[i];
                    max_error=std::max(max_error,std::fabs(y[i]-expected.y[i]));++output_checks;
                }
                const double nrmse=square_reference==0 ? (square_error==0 ? 0 : std::numeric_limits<double>::infinity()) : std::sqrt(square_error/square_reference);
                save(prefix+".observed_y.bin",std::vector<float>(y.begin(),y.end()-1));
                std::ofstream description(prefix+".json");
                description << "{\"weight_source\":\"real_Qwen3.5_layer0_" << kind << "\",\"activation_source\":\"synthetic\",\"revision\":\"2fc06364715b967f1860aea9cf38778875588b17\",\"T\":" << t << ",\"N\":" << n << ",\"K\":" << k << ",\"seed\":" << seed << ",\"max_abs\":" << max_error << ",\"nrmse\":" << nrmse << "}\n";
                if(!description) throw std::runtime_error("real tensor case metadata");
                std::cout << "PASS real_weight=" << kind << " T=" << t << " seed=" << seed << " max_abs=" << max_error << " nrmse=" << nrmse << " activation=synthetic domain=PC_NATIVE\n";
            }
        }
        std::cout << "B01 real-tensor PASS cases=4 int32_partial_checks=" << partial_checks << " fp32_output_checks=" << output_checks << '\n';
        return 0;
    } catch(const std::exception& error) {
        std::cerr << "B01 real-tensor FAIL " << error.what() << '\n';return 1;
    }
}
