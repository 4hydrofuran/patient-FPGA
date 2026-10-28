# A07 platform and deployment boundary

## Fixed offline build identity

- AMD Vivado/Vitis 2026.1, build 6511674; HLS build 6493734.
- Official kv260_base 2026.1_0608_1339, xck26-sfvc784-2LV-c.
- Exact XPFM SHA256: `563308140b285caf10ee9fd5294fc401b14390fd99267855cabd11e1c6b0f6aa`.
- Exact hardware XSA SHA256: `97daf86957a2839965cac39a0a6dc36a4619c96c127ad8fb98b9ca5e960c0630`.
- Fixed B double XO SHA256: `96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23`; build_id 0xB3030002, meta 40 bytes, allocated meta BO at least 64 bytes.
- Link uses the reviewed platform default clock, approximately 149.9985 MHz (6.667 ns), not a lowered clock to hide timing failures. Implemented timing must be independently reviewed.
- SDK environment: `environment-setup-cortexa72-cortexa53-amd-linux`, actual compilation appends `-mcpu=cortex-a53`; native/dotprod/i8mm/SVE are not forced. Runtime dependencies are hashed in the collected ARM report, including XRT 2.23.0. Libraries are externally provided, not copied from another operating system.

## Still blocked before deployment (not offline-link blockers)

1. The Common Image / SDK dependency match is a userspace compatibility observation, not proof of KV260 bootability. The Common/PetaLinux exception and Kria EDF WIC/UEFI route remain separate candidates. No arbitrary combination of boot firmware, kernel and DT is selected here.
2. The platform README PS DDR Size=2GB, physical module memory, Linux MemTotal, device-tree reservations and actual XRT/BO reachable windows are distinct quantities. Linux and PL usable bytes, CMA, alignment, device identity, and verified BO budget remain null until actual board collection. The generated xclbin topology is a logical build artifact, not a measured allocation budget.
3. A generated bitstream/XSA/overlay is an offline artifact. It is not an SD/QSPI image, not permission to flash, and not proof that a particular base DT accepts it.
4. All candidate configs retain `allow_device_access=false` and DEPLOYMENT_PENDING_BOARD. BOARD_VERIFIED requires actual identity, boot chain, memory checks and a separately authorized board session.
5. POISONED retains all DMA ownership and the exclusive lock. Driver state/sync calls have no measured hard worst-case latency here. No automatic abort, reset, unload, kill or rollback is claimed safe.

## Ownership and future evidence

W/Sw are copied into handle-owned BOs once at load; no second complete CPU copy is retained by this library. X/Sx/Y/meta are pooled context-owned buffers. Logical IO data = 194656 bytes before board-verified charge alignment; this is a calculation, not measured DDR use. The 72-matrix W/Sw payload remains 140378112 bytes; mapped file pages and model pages must be accounted separately at A12.

A11 must record actual BO allocation/sync/execution/readback, device and image identity, stale/error handling and authorized recovery. A12 must demonstrate real model consumption of PL results. This A07 does neither. B04 joint candidate signoff is separate and cannot be signed for B.

Existing platform sources: `platform/a1/preboard_readiness.json`, `platform/a1/offline_link_inputs.json`, `platform/a1/kria_2026_1_image_candidate.json`, `platform/ra02/status.json`; these are retained historical investigations, not overwritten as board-verified.
