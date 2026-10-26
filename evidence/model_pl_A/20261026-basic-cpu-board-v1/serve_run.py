from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
FILE=Path(__file__).parent/'basic_cpu_run_bound.py'
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0]!='192.168.2.2' or self.path!='/basic_cpu_run.py':self.send_error(404);return
        data=FILE.read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
server=HTTPServer(('192.168.2.1',8765),Handler);server.timeout=150
print('CPU_RUN_SOURCE_SERVER_READY',flush=True);server.handle_request();server.server_close()
