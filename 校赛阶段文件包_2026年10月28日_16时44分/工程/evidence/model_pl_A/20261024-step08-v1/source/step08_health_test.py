"""Full live reserve/temp/boot gates plus lossless content-addressed kernel logs."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from common import sha,save
from step08_common import OUT
import step08_health as health

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);row=health.compact_kernel_record(root,dict(raw_log='raw\r\nkernel\n',allowed=True))
        p=root/row['raw_log_file'];assert p.read_bytes()==b'raw\r\nkernel\n' and sha(p)==row['raw_log_sha256']
        again=health.compact_kernel_record(root,dict(raw_log='raw\r\nkernel\n'));assert again['raw_log_file']==row['raw_log_file']
        p.write_bytes(b'corrupted')
        try:health.compact_kernel_record(root,dict(raw_log='raw\r\nkernel\n'))
        except RuntimeError:pass
        else:raise AssertionError('bad kernel snapshot reused')
    class FakePath:
        temp=30000;available=2000000;cma=200000;boot='correct'
        def __init__(self,path):self.path=str(path)
        def read_text(self):
            if self.path.endswith('boot_id'):return self.boot
            if self.path.endswith('meminfo'):return f'MemAvailable: {self.available} kB\nCmaFree: {self.cma} kB\nCmaTotal: 819200 kB\n'
            return str(self.temp)
        def glob(self,pattern):return [FakePath('/temp')]
    cases=0
    with patch.object(health,'Path',FakePath):
        assert health.live_snapshot('correct',full_resident=True)['actual_reserve']['allowed'];cases+=1
        for key,value in [('temp',55000),('temp',0),('available',1114111),('cma',98303),('boot','foreign')]:
            prior=getattr(FakePath,key);setattr(FakePath,key,value)
            try:health.live_snapshot('correct',full_resident=True)
            except RuntimeError:cases+=1
            else:raise AssertionError('health violation accepted')
            setattr(FakePath,key,prior)
    save(OUT/'HEALTH_PC.json',dict(status='PASS_PC_FRESH_HEALTH_AND_LOSSLESS_KERNEL_DEDUP',health_cases=cases,
       kernel_content_and_collision_checks=3,BOARD='NOT_TESTED',full_FD_VMA_scans='Still required at all lifecycle boundaries'))
    print('PASS_FRESH_LIVE_HEALTH_AND_LOSSLESS_KERNEL_LOG_STORAGE')
