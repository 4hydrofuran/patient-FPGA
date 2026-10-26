"""Stable public failures without exposing model paths or internal exceptions."""


class GatewayError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable


class OperationCancelled(Exception):
    """An invalidated operation must not publish an answer or enter history."""

