from pathlib import Path
here=Path(__file__).parent
text=(here.parent/'20261026-pl-authfix-board-v1/boot_once.ps1').read_text(encoding='utf-8-sig')
text=text.replace('while($timer.Elapsed.TotalSeconds -lt 100)','while($timer.Elapsed.TotalSeconds -lt 300)')
old='test ! -e /var/lock/kv260-a1/active; test ! -L /var/lock/kv260-a1/active;'
new="test ! -L /var/lock/kv260-a1/active; if test -d /var/lock/kv260-a1/active; then sudo -n /usr/bin/python3 -c \"import json; r=json.load(open(''/var/lock/kv260-a1/active/lease.json'')); assert r[''window'']==''a12-pl-authfix-20261026-v1'' and r[''identity''].endswith('':0978088a-8d10-45b2-8f43-726d00209313'')\"; fi;"
assert text.count(old)==1;text=text.replace(old,new)
(here/'boot_default_once.ps1').write_text(text,encoding='utf-8')
