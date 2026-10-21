// 仅用于 Windows 控制测试：声明实际 OpenSSL 3 DLL 的公开摘要 ABI。
// 原型依据 https://docs.openssl.org/3.0/man3/EVP_DigestInit/；不实现或替换哈希算法。
#pragma once
#if !defined(_WIN32) || !defined(SP_LINEAR_CONTROL_TEST)
#error "This narrow header is restricted to Windows control tests"
#endif
#include <cstddef>
extern "C" {
typedef struct evp_md_ctx_st EVP_MD_CTX;
typedef struct evp_md_st EVP_MD;
typedef struct engine_st ENGINE;
EVP_MD_CTX* EVP_MD_CTX_new(void);
void EVP_MD_CTX_free(EVP_MD_CTX*);
const EVP_MD* EVP_sha256(void);
int EVP_DigestInit_ex(EVP_MD_CTX*, const EVP_MD*, ENGINE*);
int EVP_DigestUpdate(EVP_MD_CTX*, const void*, std::size_t);
int EVP_DigestFinal_ex(EVP_MD_CTX*, unsigned char*, unsigned int*);
}
