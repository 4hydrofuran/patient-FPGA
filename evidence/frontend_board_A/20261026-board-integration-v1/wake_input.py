import os,fcntl,struct,time,json
from pathlib import Path
fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
try:
    fcntl.ioctl(fd,0x40045564,0)
    fcntl.ioctl(fd,0x40045564,1)
    for key in range(1,128):fcntl.ioctl(fd,0x40045565,key)
    descriptor=struct.pack('80sHHHHi',b'KV260 temporary display wake',3,1,1,1,0)+bytes(1024)
    os.write(fd,descriptor);fcntl.ioctl(fd,0x5501)
    time.sleep(2)
    for value in (1,0):
        os.write(fd,struct.pack('llHHi',0,0,1,42,value))
        os.write(fd,struct.pack('llHHi',0,0,0,0,0))
        time.sleep(.1)
    time.sleep(1)
    r={'action':'one Shift press/release to wake display; no text or login submitted',
       'dpms':Path('/sys/class/drm/card0-DP-1/dpms').read_text(),
       'state':Path('/sys/kernel/debug/dri/0/state').read_text()[-1000:]}
finally:
    fcntl.ioctl(fd,0x5502);os.close(fd)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
