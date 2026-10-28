# A07 → B04 public runtime and offline build delivery

Read `a_delivery.json` for the actual completion status and `reports/implementation/REVIEW.json` for routed timing, checks and scope. Neither a file name nor a successful packaging command establishes A07/B04 acceptance. BOARD, ARM execution, BO bandwidth, memory budget and device recovery remain NOT_TESTED/null. B's own joint signoff is not claimed.

## Contents and identity

The only selected compute kernel is B double, build_id `0xB3030002`, XO SHA256 `96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23`. Public contract bundle hash remains `83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6`; its SP_LINEAR_V1 header file hash is `d97e544444b8566a32d0bd25e67e2e548f71678ac6e63ac63e96aa415b1a76f9`. These are different hash scopes, not different APIs. A owns the six-function XRT library, not a second HLS kernel. Exact binary hashes, source inventory, tool commands and exit codes accompany the delivery.

`artifacts/` contains the real Cortex-A53 shared library/independent host, linked xclbin and same-run bit/HWH. These are not a bootable SD image or a verified DT overlay. `model_arm64/` preserves the previously validated S1 CPU model and dependencies; it does NOT route model graph operations to FPGA (A12). No model/voice weights, SDK, operating-system image, licenses or credentials are included.

## Rebuild on a compatible Linux host

Install/provide Linux g++, Python3, PC OpenSSL development headers/library, and the matched AMD 2026.1 Common AArch64 SDK. nlohmann/json is included with its original MIT notice. Tool/SDK dependencies are externally obtained under their own terms. Do not use PC headers as ARM sysroot headers.

In an empty build directory, replace the paths below with your actual delivery and SDK:

```bash
bash /delivery/platform/qwen35/a07/b04/build_portable.sh /delivery \
 /delivery/third_party/nlohmann /sdk/environment-setup-cortexa72-cortexa53-amd-linux
```

This builds the unchanged host-rule/meta tests and the production ARM64 library/host. A separate empty directory can execute the visibly labeled control tests:

```bash
bash /delivery/platform/qwen35/a07/control/build_control_portable.sh /delivery /usr
```

`/usr` is the PC OpenSSL prefix, not the ARM SDK. A's original PC dependency recovery used privately extracted Ubuntu libssl-dev/libssl3 3.0.2-0ubuntu1.30 rather than upgrading system packages; its commands/hashes are recorded. Control tests define SP_LINEAR_CONTROL_TEST; production builds MUST NOT define it or include stubs. Tests output null execution_kind and cannot enter public performance metrics.

For hardware linking, source the installed 2026.1 Vitis environment and use the delivered `link_offline.py --root /delivery --platform <kv260_base.xpfm> --xo <exact-B.xo>` from another empty directory. It checks the accepted source, embedded XML, tool build and official platform hashes before invoking v++ with target hw. The XO is supplied separately in B's frozen package; do not invent a substitute. Use a single shared build queue/lock and separate work directories. Do not run on the board.

## Runtime and memory safety

Keep `config.pending.json` disabled. A physical profile must come from A11 board observations, not xclbin topology alone. No app automatically falls back to CPU in fpga_required mode. The default app's deliberate CPU configuration is distinct from this disabled hardware candidate.

Load takes ownership by copying W/Sw to BOs. Handles retain BOs until safe unload; context owns persistent device/kernel/run and pooled X/Sx/Y/meta. Only a successful run permits consuming Y. Meta is synchronized and verified before Y. POISONED retains buffers/lock and refuses further work, including close. Do not dlclose/kill and call that recovery. Driver blocking and physical recovery require board tests.

Logical pooled data is 194656 bytes before verified alignment. Model MLP W/Sw payload is 140378112 bytes, not twice that for a CPU shadow. Actual file-page overlap, CMA, address windows and resident budget remain board-dependent. See `platform/qwen35/a07/control/PLATFORM_RISKS.md`.

## Independent checks and provenance

`reports/control/` contains actual control-only JSONL outputs, failures from prior attempts, ASan/UBSan results, ARM ELF/dependency checks and original commands. Existing 970-rule/66-meta evidence is preserved separately. Csim61 with A04 independent mathematics is distinct from transport mocks and from B's 65 native RTL passes + one recovered historical postcheck. Do not combine these into invented additional unique tests.

Run B's unchanged `tools/b04_a_preflight.py` under the received B04 subdirectory to check inventory/hash/ELF; that tool does not sign joint G1–G6 or replace xclbin/implementation review. No source code or evidence should rely solely on a C: hyperlink available only to A.
