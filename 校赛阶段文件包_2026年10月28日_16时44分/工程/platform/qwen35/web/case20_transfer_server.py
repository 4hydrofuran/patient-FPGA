"""Serve only the reviewed board package over the existing private Ethernet link."""
import argparse
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True)
p.add_argument('--archive',default='case20-random-t4.zip');a=p.parse_args()
directory=a.directory.resolve()
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(directory),**kwargs)
    def do_GET(self):
        if self.path!='/'+a.archive:self.send_error(404);return
        super().do_GET()
server=ThreadingHTTPServer(('192.168.2.1',18894),Handler);server.timeout=.25
print('READY_PRIVATE_CASE20_TRANSFER',flush=True)
try:
    while not (directory/'HTTP_STOP.json').exists():server.handle_request()
finally:server.server_close()
