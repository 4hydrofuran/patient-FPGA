"""Serve only the hash-locked public driver, once, on the direct Ethernet IPv6 link."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import socket
import sys

EXPECTED = '545df42c8b66396dd847ccd6a280f19d9a0051d36e2e75c1ec84437caca328a9'


if __name__ == '__main__':
    payload = Path(sys.argv[1]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != EXPECTED:
        raise SystemExit('Wrong driver hash')

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.client_address[0].split('%')[0].lower() != 'fe80::20a:35ff:fe0f:2d70':
                self.send_error(403)
                return
            if self.path != '/zocl.ko':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    class IPv6Server(HTTPServer):
        address_family = socket.AF_INET6

    with IPv6Server(('fe80::3403:86e9:d1f9:d400', 18081, 0, 15), Handler) as server:
        server.timeout = 40
        print('READY_DIRECT_LINK_ONE_REQUEST_NO_DIRECTORY_LISTING', flush=True)
        server.handle_request()
    print('SERVER_CLOSED', flush=True)
