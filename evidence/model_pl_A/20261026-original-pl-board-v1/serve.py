from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
FILES={'/preflight.py':HERE/'preflight.py','/bundle.zip':ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip','/start.py':HERE/'start.py'}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0]!='192.168.2.2' or self.path not in FILES:self.send_error(404);return
        p=FILES[self.path];self.send_response(200);self.send_header('Content-Length',str(p.stat().st_size));self.end_headers()
        with p.open('rb') as f:
            while True:
                b=f.read(65536)
                if not b:break
                self.wfile.write(b)
server=HTTPServer(('192.168.2.1',8765),Handler);server.timeout=600
print('ORIGINAL_FLOW_SOURCE_SERVER_READY',flush=True)
for _ in range(3):server.handle_request()
server.server_close()
