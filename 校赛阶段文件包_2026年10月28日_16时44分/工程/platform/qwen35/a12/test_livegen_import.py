"""Import-only original gate isolation, with hardware/command access prohibited."""
import ctypes as c
import argparse
import os
from pathlib import Path
import sys
import resource_probe_policy
from livegen_platform import import_original_verified,load_original,BoardPorts
from livegen_import import PACKAGE
from livegen_evidence import OUT,read,save,sha,pin,ROOT
from plm_journal import need

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);parser.add_argument('--revision',required=True,type=int);args=parser.parse_args();assert args.tag.isalnum()
    before=resource_probe_policy;path=list(sys.path);env=os.environ.get('SP_TT10_CONFIG');attempts=[]
    def audit(event,args):
        if event in ('subprocess.Popen','os.system','socket.connect','socket.bind'):
            attempts.append(event);raise RuntimeError('forbidden command/network during gate import')
        if event in ('open','os.listdir','os.scandir') and args and isinstance(args[0],(str,bytes)):
            p=os.fsdecode(args[0])
            if p.startswith(('/proc/','/sys/','/dev/dri','/dev/zocl','/etc/machine-id')):
                attempts.append(p);raise RuntimeError('forbidden live hardware/source access during import')
    sys.addaudithook(audit);module=import_original_verified()
    need(sys.modules['resource_probe_policy'] is before and sys.path==path and os.environ.get('SP_TT10_CONFIG')==env,'global import/environment was changed')
    loaded=[]
    for name,m in sorted(sys.modules.items()):
        if name.startswith(PACKAGE+'.'):
            p=Path(m.__file__);need(sha(p)==m.__frozen_source_sha256__,'frozen module bytes differ')
            loaded.append(dict(module=name,file=pin(p),import_qualifications=m.__frozen_import_edits__))
    need(len(loaded)>10 and not attempts,'original gate namespace not fully isolated')
    charge=(140591104+1023)//1024
    need(module.admission(dict(MemAvailable=1114112+charge,CmaFree=98304+charge),140591104)['allowed'],'original pending BO boundary differs')
    need(not module.admission(dict(MemAvailable=1114112+charge,CmaFree=98304+charge-1),140591104)['allowed'],'original pending BO reserve waived')
    need(module.admission(dict(MemAvailable=1114112,CmaFree=98304),140591104,already_charged_bo_bytes=140591104)['allowed'],
        'resident BO incorrectly charged twice')
    for operation in (load_original,lambda:BoardPorts(None,None)):
        try:operation()
        except RuntimeError as e:need('root ARM64' in str(e),'unexpected factory refusal')
        else:raise RuntimeError('PC positive Board factory unexpectedly available')
    # x86 manager ABI cannot create a Board-domain slot, even under WSL root.
    b=read(OUT/f'BUILD-v{args.revision}.json');lib=c.CDLL(b['generation_writer']);fn=lib.a12_livegen_board_open_v1
    fn.argtypes=[c.c_int,c.c_char_p,c.c_char_p];fn.restype=c.c_void_p
    need(not fn(-1,b'1'*64,b'2'*64),'PC manager exposed positive Board issuer')
    save(OUT/('IMPORT_REVIEW-'+args.tag+'.json'),dict(status='PASS_PRIVATE_FROZEN_GATE_IMPORT_NO_BOARD_OBJECTS_OR_IO',modules=loaded,
        original_functions_changed=False,only_local_import_names_qualified=True,AST_inverse_checked=True,global_root_modules_preserved=True,
        sys_path_environment_preserved=True,forbidden_command_hardware_attempts=attempts,PC_Board_issuer_refused=True,BOARD='NOT_TESTED'))
    print('PASS_PRIVATE_FROZEN_GATE_IMPORT_NO_BOARD_OBJECTS_OR_IO',len(loaded))
if __name__=='__main__':main()
