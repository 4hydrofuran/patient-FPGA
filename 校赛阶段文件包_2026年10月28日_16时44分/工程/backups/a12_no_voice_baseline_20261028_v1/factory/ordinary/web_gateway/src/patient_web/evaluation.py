"""Translate frozen A02 coverage results into evidence-backed, deterministic feedback."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TOPICS = {
    "location": "疼痛位置", "quality": "疼痛性质", "onset": "起病时间",
    "duration": "持续时间", "severity": "疼痛程度", "radiation": "放射部位",
    "trigger": "诱发或加重因素", "relief": "缓解因素", "dyspnea": "呼吸困难",
    "allergy": "过敏史",
}
REVIEW_REASONS = {
    "double_negation_ambiguous": "问题含双重否定，含义需要复核",
    "asr_review_required": "语音转写的可信度需要复核",
}
DISCLAIMER = "当前为待教师审核的问诊话题覆盖评分草案，不代表临床能力或诊断正确性。"
SCORING_NOTE = "按已接收的医生提问计分；回答取消或失败，不会自动撤销已记录的提问分数。"


class EvaluationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    turn_id: int = Field(ge=1)
    question_number: int = Field(ge=1)
    request_id: str
    question: str
    turn_status: Literal["COMPLETED", "CANCELLED", "FAILED"]
    answer_published: bool


class EvaluationTopic(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    topic_id: str
    label: str
    points: int = Field(ge=0)
    max_points: int = Field(ge=0)
    covered: bool
    evidence: list[EvaluationEvidence]


class ReviewItem(EvaluationEvidence):
    reason: str
    reason_label: str


class EvaluationResult(BaseModel):
    """Public envelope; the original rule score is retained verbatim for audit."""
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["chief-evaluation.v1"]
    evaluation_id: str
    instance_id: str
    session_id: str
    case_id: str
    case_version: str
    case_sha256: str
    frozen_at: str
    frozen_turn_count: int
    scoring_event_count: int
    rule_score: dict
    summary_status: Literal["READY"]
    summary_source: Literal["RULE_TEMPLATE"]
    summary_version: Literal["chief-summary-v1"]
    summary_text: str
    topics: list[EvaluationTopic]
    covered_topics: list[str]
    missing_topics: list[str]
    review_items: list[ReviewItem]
    recommendations: list[str]
    review_status: str
    meaning: str
    disclaimer: str
    scoring_note: str


def build_evaluation(*, instance_id, business_snapshot, turns, rule_score):
    """Build once on finish, using request IDs rather than assuming turn numbers align."""
    if not business_snapshot["closed"]:
        raise ValueError("Evaluation requires a closed business snapshot")
    if set(rule_score["items"]) != set(TOPICS):
        raise ValueError("Coverage rubric changed; topic labels need explicit review")
    public_turns = {turn["request_id"]: (number, turn) for number, turn in enumerate(turns, 1)}
    events = {event["turn_id"]: event for event in business_snapshot["received"]}

    def evidence(turn_id):
        event = events[turn_id]
        number, turn = public_turns[event["request_id"]]
        if event["transcript"] != turn["question"]:
            raise ValueError("Score evidence differs from recorded question")
        return {"turn_id": turn_id, "question_number": number,
                "request_id": event["request_id"], "question": event["transcript"],
                "turn_status": turn["status"], "answer_published": turn["answer"] is not None}

    topics = []
    for topic_id, label in TOPICS.items():
        item = rule_score["items"][topic_id]
        topics.append({"topic_id": topic_id, "label": label, "points": item["points"],
                       "max_points": item["max_points"], "covered": item["points"] > 0,
                       "evidence": [evidence(turn_id) for turn_id in item["evidence_turns"]]})
    covered = [item["topic_id"] for item in topics if item["covered"]]
    missing = [item["topic_id"] for item in topics if not item["covered"]]
    review = []
    for turn_id in rule_score["review_turns"]:
        event = events[turn_id]
        review.append(dict(evidence(turn_id), reason=event["route_reason"],
                           reason_label=REVIEW_REASONS.get(event["route_reason"], "该问题需要教师复核")))

    def labels(topic_ids):
        return "、".join(TOPICS[topic_id] for topic_id in topic_ids)

    sentences = [f"本次问诊话题覆盖得分为 {rule_score['score']}/{rule_score['max_score']}。"]
    sentences.append(f"已覆盖：{labels(covered)}。" if covered else "本次尚无可计分的话题覆盖记录。")
    sentences.append(f"尚未覆盖：{labels(missing)}。" if missing else "当前量表中的问诊话题已全部覆盖。")
    if review:
        sentences.append(f"另有 {len(review)} 条提问待复核，未作为已确认的得分依据。")
    recommendations = []
    if missing:
        recommendations.append(f"下一次练习请补充询问：{labels(missing)}。")
    if review:
        recommendations.append("请查看待复核提问，确认表述含义，再由教师复核。")
    if not missing:
        recommendations.append("请对照提问依据复盘；话题覆盖完整仍需结合教师反馈评估问诊质量。")
    advice = []
    if missing:
        advice.append("建议在下一次练习中补充上述未覆盖话题。")
    if review:
        advice.append("请结合原始提问核对待复核项。")
    if not missing:
        advice.append(recommendations[-1])
    summary = "\n".join(sentences + advice)
    frozen_at = datetime.now(timezone.utc).isoformat()
    identity = {key: business_snapshot[key] for key in ("session_id", "case_id", "case_version", "case_sha256")}
    payload = {"schema_version": "chief-evaluation.v1", "instance_id": instance_id,
               **identity, "frozen_at": frozen_at, "frozen_turn_count": len(turns),
               "scoring_event_count": len(events), "rule_score": deepcopy(rule_score),
               "summary_status": "READY", "summary_source": "RULE_TEMPLATE",
               "summary_version": "chief-summary-v1", "summary_text": summary,
               "topics": topics, "covered_topics": covered, "missing_topics": missing,
               "review_items": review, "recommendations": recommendations,
               "review_status": rule_score["review_status"],
               "meaning": "draft_question_topic_coverage_only", "disclaimer": DISCLAIMER,
               "scoring_note": SCORING_NOTE}
    payload["evaluation_id"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return EvaluationResult.model_validate(payload).model_dump()
