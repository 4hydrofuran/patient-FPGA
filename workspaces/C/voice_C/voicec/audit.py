"""Bounded metadata-only audit logs in a newly created, dedicated directory."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
from .spool import Spool

FIELDS = {'request_id', 'op', 'type', 'event', 'code', 'final', 'epoch', 'execution_kind'}


class AuditLog:
    def __init__(self, directory, max_bytes=65536, backups=3):
        if type(max_bytes) is not int or not 128 <= max_bytes <= 1048576:
            raise ValueError('Audit size must be 128..1048576 bytes')
        if type(backups) is not int or not 1 <= backups <= 8:
            raise ValueError('Audit backups must be 1..8')
        directory = Path(directory).absolute()
        if any(Spool.is_link(p) for p in (directory, *directory.parents)):
            raise ValueError('Audit directory must not traverse links/reparse points')
        # Refuse existing directories: rotation never takes ownership of caller logs.
        directory.mkdir(parents=True, exist_ok=False)
        self.handler = RotatingFileHandler(directory/'worker.audit.jsonl', maxBytes=max_bytes,
            backupCount=backups, encoding='utf-8', delay=False)
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.lock = threading.Lock()
        self.closed = False

    def write(self, message):
        metadata = {key:value for key,value in message.items() if key in FIELDS and
                    type(value) in (str, int, bool, type(None))}
        for key, value in list(metadata.items()):
            if isinstance(value, str):
                metadata[key] = value[:64].replace('\n', '').replace('\r', '')
        record = logging.LogRecord('voicec.audit', logging.INFO, '', 0,
            json.dumps(metadata, ensure_ascii=False, allow_nan=False), (), None)
        with self.lock:
            if self.closed:
                raise RuntimeError('Audit log is closed')
            self.handler.emit(record)

    def close(self):
        with self.lock:
            if not self.closed:
                self.handler.close()
                self.closed = True
