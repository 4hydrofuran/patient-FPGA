from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
HERE=Path(__file__).parent
ROOT=HERE.parents[2]
FILES={'/preflight.py':HERE/'preflight.py','/start.py':HERE/'start.py','/start2.py':HERE/'start2.py',
 '/binding.py':ROOT/'platform/qwen35/a12/resource_probe_binding.py','/collect.py':HERE/'collect.py'}
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.client_address[0]!='192.168.2.2' or self.path not in FILES:self.send_error(404);return
  p=FILES[self.path];self.send_response(200);self.send_header('Content-Length',str(p.stat().st_size));self.end_headers()
  with p.open('rb') as f:
   while True:
    b=f.read(65536)
    if not b:break
    self.wfile.write(b)
 def do_POST(self):
  if self.client_address[0]!='192.168.2.2' or self.path!='/receipt.zip':self.send_error(404);return
  n=int(self.headers.get('Content-Length','0'))
  if not 0<n<=16777216:self.send_error(413);return
  with (HERE/'board-receipt.zip').open('xb') as f:
   left=n
   while left:
    b=self.rfile.read(min(left,65536))
    if not b:raise EOFError('incomplete receipt')
    f.write(b);left-=len(b)
  self.send_response(200);self.end_headers();self.wfile.write(b'RECEIVED')
server=HTTPServer(('192.168.2.1',8765),Handler)
print('AUTHFIX_SOURCE_SERVER_READY',flush=True)
server.serve_forever()
