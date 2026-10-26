from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
HERE=Path(__file__).parent
FILES={'/overlay.zip':HERE/'overlay.zip','/setup.py':HERE/'setup.py','/collect.py':HERE/'collect.py'}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0]!='192.168.2.2' or self.path not in FILES:self.send_error(404);return
        data=FILES[self.path].read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if self.client_address[0]!='192.168.2.2' or self.path!='/receipt.zip':self.send_error(404);return
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<16777216:self.send_error(413);return
        data=self.rfile.read(size)
        if len(data)!=size:raise EOFError('Receipt incomplete')
        with (HERE/'board-receipt.zip').open('xb') as f:f.write(data)
        self.send_response(200);self.end_headers();self.wfile.write(b'RECEIVED')
server=HTTPServer(('192.168.2.1',8766),Handler)
print('WEB_SOURCE_SERVER_READY',flush=True)
server.serve_forever()
