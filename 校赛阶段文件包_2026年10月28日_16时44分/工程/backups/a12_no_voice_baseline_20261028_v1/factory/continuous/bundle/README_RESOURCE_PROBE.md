# A12 ordinary resource probe (unbound, no BOARD authorization)

Run only the local audit: python -B platform/qwen35/a12/resource_probe_entry.py --bundle . --plan-only

Exactly app_R0 -> warm_prefix -> app_hit, old frozen 107/70/37-token workload.
No heavy diagnostic exports, legacy comparison or diagnostic readback.
Original per-submit permissions/fsync, health thresholds, BO/meta validation remain.
Native ARM executable, libraries, XCLBIN and B-origin hardware bytes are unchanged.

The manager intentionally refuses direct execution. There is NO executable board
driver or compute authorization in this deliverable. A separate future reviewed
binding must verify fault recovery, safe release, current identity/boot/kernel,
fresh full preflight, unique lease/locks and explicit compute authorization.
It must pin a new manifest, review the exact manager changes and add the existing
independent/delayed release postchecks. Never activate using old v3 authorization.

Resource-probe results are exploratory. Full numerical/performance acceptance,
teacher review, CMA recovery and actual latency are NOT_TESTED/null here.
The frozen application's old prompt is intentional; no claim about the new short prompt.
