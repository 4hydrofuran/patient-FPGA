"""Versioned text publication receipts, distinct from rendering/read/audio acknowledgements."""

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def text_hash(text: str) -> str:
    """Hash exact UTF-8 bytes without normalization, quoting, or added newlines."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DeliveryReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["text-delivery.v1", "text-delivery.v2"] = "text-delivery.v1"
    delivery_kind: Literal["WEB_TEXT_PUBLISHED"] = "WEB_TEXT_PUBLISHED"
    instance_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    epoch: int = Field(ge=0)
    case_id: str = Field(min_length=1)
    case_version: str = Field(min_length=1)
    case_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    answer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    answer_source: Literal["MODEL", "MODEL_CACHE", "DEMO_RULE", "TEMPLATE", "TIMEOUT"]
    actual_backend: Literal["CPU_REFERENCE", "FPGA_REAL"] | None
    model_called: bool
    validation_status: Literal["pass"] = "pass"
    validated_monotonic_ns: str = Field(pattern=r"^[1-9][0-9]*$")
    published_monotonic_ns: str = Field(pattern=r"^[1-9][0-9]*$")
    audio_played: Literal[False] = False
    browser_render_verified: Literal[False] = False
    user_read_verified: Literal[False] = False
    cache_provenance: dict | None = None

    @model_validator(mode="after")
    def consistent_provenance(self):
        if self.answer_source == "MODEL_CACHE":
            p=self.cache_provenance or {}
            if (self.schema_version!='text-delivery.v2' or self.model_called or self.actual_backend is not None
                or p.get('current_model_called') is not False or p.get('current_PL_submissions')!=0
                or p.get('text_sha256')!=self.answer_sha256 or p.get('origin',{}).get('eos') is not True
                or p.get('origin',{}).get('execution_kind') not in ('CPU_REFERENCE','FPGA_REAL')):
                raise ValueError('Cache receipt lacks distinct current/original provenance')
        elif self.cache_provenance is not None:
            raise ValueError('Non-cache receipt cannot claim cached origin')
        if int(self.validated_monotonic_ns) > int(self.published_monotonic_ns):
            raise ValueError("Publication precedes validation")
        if self.model_called != (self.actual_backend in ("CPU_REFERENCE", "FPGA_REAL")):
            raise ValueError("Backend and model invocation disagree")
        if self.answer_source in ("MODEL", "TIMEOUT") and not self.model_called:
            raise ValueError("Model/timeout answer without a model invocation")
        if self.answer_source == "DEMO_RULE" and self.model_called:
            raise ValueError("Demo cannot claim model execution")
        return self


class TurnFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str
    message: str


class TurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str
    operation_id: str
    question: str
    status: Literal["RUNNING", "COMPLETED", "CANCELLED", "FAILED"]
    answer: str | None
    answer_source: Literal["MODEL", "MODEL_CACHE", "DEMO_RULE", "TEMPLATE", "TIMEOUT"] | None
    actual_backend: Literal["CPU_REFERENCE", "FPGA_REAL"] | None
    delivery_kind: Literal["WEB_TEXT_PUBLISHED"] | None
    delivery_receipt: DeliveryReceipt | None
    error: TurnFailure | None
    timing: dict | None = None
    cache_provenance: dict | None = None

    @model_validator(mode="after")
    def consistent_delivery(self):
        if self.status == "COMPLETED":
            receipt = self.delivery_receipt
            if self.answer is None or receipt is None or self.error is not None:
                raise ValueError("Completed turn lacks a valid receipt")
            if (receipt.request_id != self.request_id or receipt.operation_id != self.operation_id
                    or receipt.answer_sha256 != text_hash(self.answer)
                    or receipt.answer_source != self.answer_source
                    or receipt.actual_backend != self.actual_backend
                    or receipt.cache_provenance != self.cache_provenance
                    or receipt.delivery_kind != self.delivery_kind):
                raise ValueError("Turn result differs from published receipt")
        elif any(value is not None for value in (self.answer, self.answer_source,
                 self.actual_backend, self.delivery_kind, self.delivery_receipt)):
            raise ValueError("Unpublished turn exposes an answer or receipt")
        return self

