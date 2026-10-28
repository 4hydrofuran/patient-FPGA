"""Native RO descriptor mode/seal/owner binding checks; no writer API in reader."""
import ctypes as c
import os
from pathlib import Path
import tempfile
from plmode_evidence import OUT,read,save
from plm_page import Page
from livegen_binding import ReadOnlyPage
from plm_manager import ticks

def main():
    b=read(OUT/'BUILD-v2.json');page=Page(b['writer_library'],b['writer_sha256']);observer=ReadOnlyPage(page,b['observer_library'],b['observer_sha256'])
    q=observer();assert q['manager_pid']==os.getpid() and q['manager_start_ticks']==ticks(os.getpid()) and q['manager_epoch']==page.epoch
    fn=observer.fn;out=c.create_string_buffer(4096);assert fn(page.fd,out,4096)!=0 # RW alias cannot pose as an RO observer
    fd=os.memfd_create('PC_UNSEALED_NOT_AUTHORITY',os.MFD_CLOEXEC);os.ftruncate(fd,4096)
    ro=os.open('/proc/self/fd/'+str(fd),os.O_RDONLY|os.O_CLOEXEC)
    try:assert fn(ro,out,4096)!=0
    finally:os.close(ro);os.close(fd)
    page.revoke();assert observer()['revoked'];page.close();assert observer()['revoked'] # actual independent RO hold survives writer disposal
    observer.close()
    save(OUT/'OBSERVER_TEST.json',dict(status='PASS_RO_MODE_SEALS_OWNER_EPOCH_AND_INDEPENDENT_HOLD',
        RW_descriptor_rejected=True,unsealed_fake_page_rejected=True,actual_owner_epoch_verified=True,writer_mutation_exports=False,BOARD='NOT_TESTED'))
    print('PASS_RO_MODE_SEALS_OWNER_EPOCH_AND_INDEPENDENT_HOLD')
if __name__=='__main__':main()
