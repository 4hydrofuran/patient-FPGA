import json,subprocess
from pathlib import Path
assert Path('/sys/class/net/eth0/address').read_text().strip()=='00:0a:35:0f:2d:70'
subprocess.run(['ip','address','add','192.168.2.2/24','dev','eth0'],check=True,timeout=5)
r=json.loads(subprocess.check_output(['ip','-j','address','show','dev','eth0']))
print('__PL_BEGIN__');print(json.dumps(dict(temporary_address_added='192.168.2.2/24',existing_configuration_preserved=True,interface=r)));print('__PL_END__')
