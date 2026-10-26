"""Derive fixed UART sudo transport for this boot's volatile address only."""
import argparse
import base64
import hashlib
import gzip
import json
import re
from common import ROOT,save
from step08_common import OUT

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--identity',required=True);args=p.parse_args()
    identity=json.loads((OUT/args.identity).read_text(encoding='utf-8-sig'))
    assert identity['status']=='READONLY_IDENTITY_COLLECTED'
    raw=identity['raw'];assert '6.8.12-a10irq2' in raw
    assert 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec' in raw
    boots=re.findall(r'(?m)^([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\r?$',raw);assert len(boots)==1
    source=(ROOT/'platform/qwen35/a12/step08_network_guard.py').read_bytes();pin=hashlib.sha256(source).hexdigest()
    payload=base64.b64encode(gzip.compress(source)).decode()
    command="sudo -n /usr/bin/python3 -B -I -c \"import base64,gzip,hashlib,sys; b=gzip.decompress(base64.b64decode('"+payload+"')); assert hashlib.sha256(b).hexdigest()=='"+pin+"'; sys.argv=['network_guard','"+boots[0]+"']; exec(compile(b,'step08_network_guard','exec'))\""
    template=(ROOT/'platform/qwen35/a10/uart_sudo_prepare_network.ps1').read_text(encoding='utf-8')
    tail=template[template.index('$receipt=[IO.File]::Open'):]
    prefix="param([string]$OutputPath,[switch]$AuthorizedTemporaryNetwork)\n$ErrorActionPreference='Stop'\nif(-not $AuthorizedTemporaryNetwork -or -not $OutputPath){throw 'Existing volatile network authority and exclusive receipt required'}\n$receiptPath=$OutputPath\n. \"$PSScriptRoot/../a10/inspect_boot_once.ps1\" -DefinitionsOnly\n$AuthorizedCandidateStage=$false;$deadline=30\n$plan=@{command='"+command.replace("'","''")+"'}\n"
    target=ROOT/'platform/qwen35/a12/step08_network_once.ps1'
    target.write_text(prefix+tail,encoding='utf-8',newline='\n')
    save(OUT/'NETWORK_SCRIPT_PINS.v4.json',dict(boot_id=boots[0],guard_sha256=pin,transport_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),persistent_changes=False))
    print('VOLATILE_NETWORK_ONLY_SOURCE_PREPARED')
