"""Bounded, ordered event journal. Slow/disconnected consumers recover by snapshot."""

from collections import deque
from copy import deepcopy
import threading
import uuid


class EventJournal:
    def __init__(self, capacity: int = 256):
        self.instance_id = uuid.uuid4().hex
        self.capacity = capacity
        self.sequence = 0
        self.events = deque(maxlen=capacity)
        self.lock = threading.Lock()

    def emit(self, event: str, session_id=None, request_id=None, epoch=0, **data):
        with self.lock:
            self.sequence += 1
            item = {
                "schema_version": "ui.v1", "instance_id": self.instance_id,
                "seq": self.sequence, "event": event, "session_id": session_id,
                "request_id": request_id, "epoch": epoch, "data": deepcopy(data),
            }
            self.events.append(item)
            return deepcopy(item)

    def read(self, after: int, session_id=None):
        with self.lock:
            gap = bool(self.events and after < self.events[0]["seq"] - 1)
            items = [deepcopy(e) for e in self.events if e["seq"] > after
                     and (session_id is None or e["session_id"] in (None, session_id))]
            return items, gap, self.sequence

