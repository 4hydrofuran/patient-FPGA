from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
FILE=Path(__file__).parent/'start2.py'
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0]!='192.168.2.2' or self.path!='/start2.py':self.send_error(404);return
        b=FILE.read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
s=HTTPServer(('192.168.2.1',8765),Handler);s.timeout=90;print('BOUND_ENTRY_READY',flush=True);s.handle_request();s.server_close()
