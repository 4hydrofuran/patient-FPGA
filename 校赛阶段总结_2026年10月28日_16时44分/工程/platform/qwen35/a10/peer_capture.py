"""Recover bounded captured files; never executes received code or contacts UART."""
import base64
import hashlib
import re


def payload(record, expected_size, expected_sha256, *, encoded):
    if record.get("exit_code") != 0 or record.get("completion_marker") is not True:
        raise ValueError("incomplete or failed read")
    raw = record["raw"].replace("\r\n", "\n")
    starts = list(re.finditer(r"(?m)^A10_([a-f0-9]{32})_BEGIN\n", raw))
    if len(starts) != 1:
        raise ValueError("ambiguous begin marker")
    begin = starts[0]
    end = "\nA10_" + begin[1] + "_END:0"
    if raw.count(end) != 1:
        raise ValueError("ambiguous end marker")
    finish = raw.index(end)
    if finish < begin.end():
        raise ValueError("reversed capture markers")
    body = raw[begin.end():finish]
    data = base64.b64decode(body.strip(), validate=True) if encoded else body.encode("utf-8")
    if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("recovered bytes do not match independent length/digest")
    return data
