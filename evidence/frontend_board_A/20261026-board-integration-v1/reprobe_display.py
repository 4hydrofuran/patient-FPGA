import json,time
from pathlib import Path
p=Path('/sys/class/drm/card0-DP-1')
r={'before_modes':(p/'modes').read_text()}
(p/'status').write_text('detect\n')
time.sleep(2)
b=(p/'edid').read_bytes()
r.update(status=(p/'status').read_text(),modes=(p/'modes').read_text(),edid_len=len(b),
    checksums=[sum(b[i:i+128])%256 for i in range(0,len(b),128)])
if len(b)>=128:
    r['edid_header']=b[:16].hex()
    r['name']=[b[i+5:i+18].decode('ascii',errors='replace').strip() for i in range(54,126,18) if b[i:i+5]==b'\x00\x00\x00\xfc\x00']
    d=b[54:72]
    r['preferred_timing']={'pixel_clock_khz':int.from_bytes(d[:2],'little')*10,'width':d[2]+((d[4]>>4)<<8),'height':d[5]+((d[7]>>4)<<8)}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
