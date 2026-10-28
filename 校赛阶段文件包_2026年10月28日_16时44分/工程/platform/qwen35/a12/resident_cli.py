"""Bounded JSON-lines transport for the PC-only resident software test service."""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
from typing import Any


MAX_LINE_BYTES = 8192
MAX_INPUT_LINES = 64


class InputError(ValueError):
    """A transport rejection with a fixed, non-sensitive message."""


class TransportError(RuntimeError):
    """A failed output or unexpected service response."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, "resident_cli: invalid command-line arguments\n")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise InputError("non-finite JSON number")


def parse_request(line: bytes) -> dict[str, Any]:
    """Reject unexpected operations/fields before entering the service."""
    try:
        request = json.loads(
            line.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_nonfinite,
        )
    except InputError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise InputError("invalid UTF-8 JSON object") from None
    if type(request) is not dict:
        raise InputError("input must be a JSON object")
    op = request.get("op")
    if type(op) is not str:
        raise InputError("missing or invalid operation")
    fields = {
        "open_session": {"op", "case_id", "mode"},
        "submit": {"op", "transcript", "timeout_s"},
        "cancel": {"op"},
        "close": {"op"},
    }
    if op not in fields:
        raise InputError("unsupported operation")
    if set(request) - fields[op]:
        raise InputError("unexpected request key")
    if op == "open_session":
        if type(request.get("case_id")) is not str or not request["case_id"]:
            raise InputError("case_id must be a nonempty string")
        mode = request.setdefault("mode", "training")
        if type(mode) is not str or mode not in ("training", "exam"):
            raise InputError("mode must be training or exam")
    elif op == "submit":
        if type(request.get("transcript")) is not dict:
            raise InputError("transcript must be an object")
        timeout = request.setdefault("timeout_s", 30)
        if type(timeout) not in (int, float):
            raise InputError("timeout_s must be a positive finite number")
        try:
            valid_timeout = math.isfinite(timeout) and timeout > 0
        except OverflowError:
            valid_timeout = False
        if not valid_timeout:
            raise InputError("timeout_s must be a positive finite number")
    return request


def _emit(response: dict[str, Any]) -> None:
    if type(response) is not dict or type(response.get("type")) is not str:
        raise TransportError("unexpected service response")
    try:
        packet = json.dumps(response, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n"
    except (TypeError, ValueError, RecursionError):
        raise TransportError("service response cannot be encoded") from None
    if sys.stdout.write(packet) != len(packet):
        raise TransportError("incomplete output write")
    sys.stdout.flush()


def _error(code: str, message: str) -> dict[str, Any]:
    return {"type": "error", "code": code, "message": message,
            "tts_ready": False, "software_test_only": True, "audio_played": False}


def _cancel_safely(service: Any) -> None:
    if service is not None:
        try:
            service.cancel()
        except BaseException:
            # Cancellation failure cannot authorize close, reset, or release.
            pass


def _stderr_failure(message: str) -> None:
    try:
        sys.stderr.write("resident_cli: " + message + "\n")
        sys.stderr.flush()
    except (OSError, ValueError):
        pass


def _dispatch(service: Any, request: dict[str, Any]) -> dict[str, Any]:
    op = request["op"]
    if op == "open_session":
        return service.open_session(request["case_id"], mode=request["mode"])
    if op == "submit":
        return service.submit(request["transcript"], timeout_s=request["timeout_s"])
    if op == "cancel":
        return service.cancel()
    return service.close()


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description="PC Linux x86_64 JSON-lines software_test transport only.")
    parser.add_argument("--build", required=True, help="existing PC software-test build JSON")
    parser.add_argument("--directory", required=True, help="service run directory")
    parser.add_argument("--cap", type=int, choices=(1, 72), default=72)
    parser.add_argument("--ack-printed-text", action="store_true",
                        help="opt in to host-only PC_TEXT_TEST_ACK after stdout flush; no audio")
    args = parser.parse_args(argv)
    service = None
    try:
        if os.name != "posix" or sys.platform != "linux" or platform.machine() != "x86_64":
            _emit(_error("unsupported_host", "PC Linux x86_64 software_test host required"))
            return 2
        from resident_service import ResidentService

        service = ResidentService(args.build, args.directory, cap=args.cap)
        ready = service.start()
        if type(ready) is not dict or ready.get("type") != "ready":
            _emit(ready)
            _cancel_safely(service)
            return 1
        _emit(ready)
        for _ in range(MAX_INPUT_LINES):
            line = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
            if not line:
                _cancel_safely(service)
                _stderr_failure("input ended without an acknowledged close; cancellation requested")
                return 1
            if len(line) > MAX_LINE_BYTES:
                _emit(_error("input_limit", "input line exceeds 8192 bytes"))
                _cancel_safely(service)
                return 1
            try:
                request = parse_request(line)
            except InputError as exc:
                _emit(_error("invalid_input", str(exc)))
                continue
            response = _dispatch(service, request)
            _emit(response)
            if response["type"] == "error":
                _cancel_safely(service)
                return 1
            if request["op"] == "close":
                if response["type"] != "closed":
                    raise TransportError("close was not acknowledged")
                return 0
            if (args.ack_printed_text and request["op"] == "submit"
                    and response["type"] == "validated_answer" and response.get("tts_ready") is True):
                # This point is reached only after _emit completed write + flush.
                request_id, epoch = response.get("request_id"), response.get("epoch")
                if type(request_id) is not str or not request_id or type(epoch) is not int:
                    raise TransportError("answer lacks acknowledgement identity")
                acknowledgement = service.acknowledge(request_id, epoch)
                if (type(acknowledgement) is not dict
                        or acknowledgement.get("type") != "delivery_ack"
                        or acknowledgement.get("kind") != "PC_TEXT_TEST_ACK"
                        or acknowledgement.get("request_id") != request_id
                        or acknowledgement.get("epoch") != epoch
                        or acknowledgement.get("audio_played") is not False
                        or acknowledgement.get("software_test_only") is not True):
                    raise TransportError("host text acknowledgement failed")
                _emit(acknowledgement)
        _emit(_error("input_limit", "transport input-line limit reached"))
        _cancel_safely(service)
        return 1
    except KeyboardInterrupt:
        _cancel_safely(service)
        _stderr_failure("interrupted; cancellation requested; no normal close performed")
        return 130
    except BrokenPipeError:
        _cancel_safely(service)
        _stderr_failure("output pipe failed; cancellation requested; no normal close performed")
        # Prevent a second failing stdout flush during interpreter shutdown.
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        except OSError:
            pass
        return 1
    except Exception:
        _cancel_safely(service)
        _stderr_failure("service or transport failed; cancellation requested; no automatic recovery performed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
