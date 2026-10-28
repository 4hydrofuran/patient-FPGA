"""The port handover must fail before acquiring another hardware window."""
import importlib.util
from pathlib import Path
import socket,unittest
path=Path(__file__).resolve().parents[3]/'platform/qwen35/web/frontend_start_board.py'
spec=importlib.util.spec_from_file_location('start_board_port_test',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class PortTest(unittest.TestCase):
    def test_free_port(self):module.require_available_http_port(port=0)
    def test_existing_listener(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            with self.assertRaisesRegex(RuntimeError,'no new Owner started'):
                module.require_available_http_port(port=listener.getsockname()[1])

if __name__=='__main__':unittest.main()
