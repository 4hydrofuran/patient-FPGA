from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
FILE=Path(__file__).parent/'a12-resident-board-candidate-20261026-v1.tar.gz'
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0]!='192.168.2.2' or self.path!='/'+FILE.name:
            self.send_error(404);return
        self.send_response(200);self.send_header('Content-Length',str(FILE.stat().st_size));self.end_headers()
        sent=0
        with FILE.open('rb') as f:
            while True:
                b=f.read(65536)
                if not b:break
                self.wfile.write(b);sent+=len(b)
        print('TRANSFER_STREAM_SENT',sent,flush=True)
server=HTTPServer(('192.168.2.1',8765),Handler);server.timeout=50
print('ONE_FILE_SERVER_READY',flush=True)
server.handle_request();server.server_close()
