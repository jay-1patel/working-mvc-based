"""Universal message-intelligence engine (UC-01 … UC-05).

Shared code for every tenant. Labels / keywords come from
``profile.intelligence``; feature flags gate which UCs run:

  message_intelligence   → sentiment + message_type
  topic_tagging          → topics / components
  safety_escalation      → safety labels + escalate hint
  repeat_issue_detection → per-customer repeats + topic surges

Classification is keyword-first (fast, offline-safe). LLM enrichment can be
layered later without changing the profile contract or WhatsApp hook.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("message_intelligence")

_POS = (
    "thank", "thanks", "great", "excellent", "awesome", "love", "happy",
    "satisfied", "appreciate", "wonderful", "amazing", "good job", "perfect",
)
_NEG = (
    "angry", "frustrated", "terrible", "awful", "hate", "worst", "useless",
    "disappointed", "unacceptable", "scam", "cheat", "refund now", "pathetic",
    "not working", "broken", "failed", "failure", "defect", "complaint",
    "complain", "dying", "keeps dying", "issue", "problem", "fault",
)


@dataclass
class MessageIntelligenceResult:
    sentiment: Optional[str] = None
    message_type: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    safety_labels: List[str] = field(default_factory=list)
    safety_hit: bool = False
    safety_severity: str = ""
    escalate: bool = False
    escalate_flow: str = ""
    escalate_message: str = ""
    is_repeat: bool = False
    repeat_count: int = 0
    surge_topic: Optional[str] = None
    surge_count: int = 0
    enabled_ucs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _label_hit(text: str, keywords: Sequence[str]) -> bool:
    if not text or not keywords:
        return False
    for kw in keywords:
        k = (kw or "").strip().lower()
        if not k:
            continue
        if " " in k:
            if k in text:
                return True
        else:
            if re.search(rf"\b{re.escape(k)}\b", text):
                return True
    return False


def _best_label(text: str, labels: Sequence[Any]) -> Optional[str]:
    """Return the id of the highest keyword-hit label (ties → first)."""
    best_id = None
    best_score = 0
    for lab in labels or []:
        lid = getattr(lab, "id", None) or (lab.get("id") if isinstance(lab, dict) else None)
        kws = getattr(lab, "keywords", None) or (lab.get("keywords") if isinstance(lab, dict) else None) or []
        if not lid:
            continue
        score = 0
        for kw in kws:
            k = (kw or "").strip().lower()
            if not k:
                continue
            if " " in k:
                if k in text:
                    score += 2
            elif re.search(rf"\b{re.escape(k)}\b", text):
                score += 1
        if score > best_score:
            best_score = score
            best_id = str(lid)
    return best_id


def _all_matching_labels(text: str, labels: Sequence[Any]) -> List[Any]:
    hits = []
    for lab in labels or []:
        kws = getattr(lab, "keywords", None) or (lab.get("keywords") if isinstance(lab, dict) else None) or []
        if _label_hit(text, kws):
            hits.append(lab)
    return hits


def _sentiment(text: str, allowed: Sequence[str]) -> str:
    pos = sum(1 for w in _POS if w in text)
    neg = sum(1 for w in _NEG if w in text)
    if neg > pos and "negative" in allowed:
        return "negative"
    if pos > neg and "positive" in allowed:
        return "positive"
    if "neutral" in allowed:
        return "neutral"
    return allowed[0] if allowed else "neutral"


def analyze_message(
    text: str,
    *,
    tenant_id: str,
    wa_id: str = "",
    entity_values: Optional[Dict[str, str]] = None,
    persist: bool = True,
) -> Optional[MessageIntelligenceResult]:
    """Run enabled UCs for this tenant. Returns None if all flags are off."""
    try:
        from shared.tenancy.loader import get_tenant_profile
        profile = get_tenant_profile(tenant_id)
    except Exception:
        logger.exception("INTEL_PROFILE_LOAD_FAILED | tenant=%s", tenant_id)
        return None

    feats = profile.features
    run_msg = feats.is_on("message_intelligence")
    run_topic = feats.is_on("topic_tagging")
    run_safety = feats.is_on("safety_escalation")
    run_repeat = feats.is_on("repeat_issue_detection")
    if not (run_msg or run_topic or run_safety or run_repeat):
        return None

    intel = profile.intelligence
    body = _norm(text)
    if not body:
        return None

    result = MessageIntelligenceResult()
    entity_values = dict(entity_values or {})
    entity_values.setdefault("wa_id", wa_id or "")

    if run_msg:
        result.enabled_ucs.extend(["UC-01", "UC-02"])
        allowed = list(intel.sentiment_labels or ["positive", "neutral", "negative"])
        result.message_type = _best_label(body, intel.message_types) or "question"
        result.sentiment = _sentiment(body, allowed)
        # Complaint / safety language without strong polarity words still skews negative.
        if (
            result.message_type == "complaint"
            and result.sentiment == "neutral"
            and "negative" in allowed
        ):
            result.sentiment = "negative"
        elif result.message_type == "praise" and result.sentiment == "neutral" and "positive" in allowed:
            result.sentiment = "positive"

    if run_topic:
        result.enabled_ucs.append("UC-03")
        for lab in _all_matching_labels(body, intel.topics):
            lid = getattr(lab, "id", None) or lab.get("id")
            if lid and str(lid) not in result.topics:
                result.topics.append(str(lid))

    if run_safety:
        result.enabled_ucs.append("UC-04")
        safety = intel.safety
        hits = _all_matching_labels(body, safety.labels)
        sev_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        best_sev = ""
        best_rank = -1
        for lab in hits:
            lid = getattr(lab, "id", None) or lab.get("id")
            sev = (getattr(lab, "severity", None) or (lab.get("severity") if isinstance(lab, dict) else "") or "").lower()
            if lid:
                result.safety_labels.append(str(lid))
            rank = sev_rank.get(sev, 0)
            if rank > best_rank:
                best_rank = rank
                best_sev = sev
        if hits:
            result.safety_hit = True
            result.safety_severity = best_sev or "high"
            if safety.escalate:
                result.escalate = True
                result.escalate_flow = safety.escalate_flow or "human_handover"
                result.escalate_message = safety.response_message or ""

    if run_repeat:
        result.enabled_ucs.append("UC-05")
        try:
            _apply_repeat_detection(
                result,
                tenant_id=tenant_id,
                entity_values=entity_values,
                cfg=intel.repeat_detection,
            )
        except Exception as exc:
            # Fresh DBs before init_db / unit tests without the table — non-fatal.
            if "no such table" in str(exc).lower():
                logger.debug("INTEL_REPEAT_SKIPPED | table missing | tenant=%s", tenant_id)
            else:
                logger.exception("INTEL_REPEAT_FAILED | tenant=%s", tenant_id)

    if persist:
        try:
            save_intelligence_row(
                tenant_id=tenant_id,
                wa_id=wa_id or "",
                text=text,
                result=result,
                entity_values=entity_values,
            )
        except Exception:
            logger.exception("INTEL_PERSIST_FAILED | tenant=%s", tenant_id)

    logger.info(
        "INTEL_RESULT | tenant=%s | wa=%s | sentiment=%s | type=%s | topics=%s | safety=%s | repeat=%s/%s | surge=%s/%s",
        tenant_id,
        wa_id,
        result.sentiment,
        result.message_type,
        result.topics,
        result.safety_labels,
        result.is_repeat,
        result.repeat_count,
        result.surge_topic,
        result.surge_count,
    )
    return result


def _apply_repeat_detection(
    result: MessageIntelligenceResult,
    *,
    tenant_id: str,
    entity_values: Dict[str, str],
    cfg: Any,
) -> None:
    from routing.database import get_db_context

    window_days = int(getattr(cfg, "window_days", 90) or 90)
    min_repeats = int(getattr(cfg, "min_repeats", 2) or 2)
    surge_threshold = int(getattr(cfg, "surge_threshold", 10) or 10)
    entity_keys = list(getattr(cfg, "entity_keys", None) or ["wa_id"])
    since = (datetime.now().astimezone() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")

    topic = result.topics[0] if result.topics else (result.message_type or "")
    if not topic:
        return

    # Build entity fingerprint from configured keys that have values.
    parts = []
    for key in entity_keys:
        val = (entity_values.get(key) or "").strip()
        if val:
            parts.append(f"{key}:{val}")
    entity_key = "|".join(parts) if parts else f"wa_id:{entity_values.get('wa_id') or ''}"

    with get_db_context() as conn:
        # Per-customer / per-asset repeats on same topic
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM message_intelligence
            WHERE tenant_id = ?
              AND entity_key = ?
              AND (
                    (topics_json LIKE ? AND ? != '')
                    OR (message_type = ? AND ? != '')
                  )
              AND created_at >= ?
            """,
            (
                tenant_id,
                entity_key,
                f'%"{topic}"%',
                topic,
                topic,
                topic,
                since,
            ),
        ).fetchone()
        prior = int(row["n"] if row is not None else 0)
        # +1 for the current message (not yet inserted when called before persist)
        result.repeat_count = prior + 1
        result.is_repeat = result.repeat_count >= min_repeats

        # Cross-customer surge on same topic
        surge = conn.execute(
            """
            SELECT COUNT(DISTINCT entity_key) AS n FROM message_intelligence
            WHERE tenant_id = ?
              AND topics_json LIKE ?
              AND created_at >= ?
            """,
            (tenant_id, f'%"{topic}"%', since),
        ).fetchone()
        surge_n = int(surge["n"] if surge is not None else 0)
        # Current customer may not be in prior rows yet
        if entity_key:
            exists = conn.execute(
                """
                SELECT 1 FROM message_intelligence
                WHERE tenant_id = ? AND entity_key = ? AND topics_json LIKE ? AND created_at >= ?
                LIMIT 1
                """,
                (tenant_id, entity_key, f'%"{topic}"%', since),
            ).fetchone()
            if not exists:
                surge_n += 1
        if surge_n >= surge_threshold:
            result.surge_topic = topic
            result.surge_count = surge_n


def save_intelligence_row(
    *,
    tenant_id: str,
    wa_id: str,
    text: str,
    result: MessageIntelligenceResult,
    entity_values: Optional[Dict[str, str]] = None,
) -> None:
    from routing.database import get_db_context

    entity_values = dict(entity_values or {})
    entity_values.setdefault("wa_id", wa_id or "")
    parts = [f"{k}:{v}" for k, v in entity_values.items() if (v or "").strip()]
    entity_key = "|".join(parts) if parts else f"wa_id:{wa_id or ''}"

    with get_db_context() as conn:
        conn.execute(
            """
            INSERT INTO message_intelligence (
                tenant_id, wa_id, entity_key, message_text,
                sentiment, message_type, topics_json, safety_json,
                is_repeat, repeat_count, surge_topic, surge_count,
                escalate, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                wa_id or "",
                entity_key,
                (text or "")[:2000],
                result.sentiment,
                result.message_type,
                json.dumps(result.topics),
                json.dumps({
                    "labels": result.safety_labels,
                    "severity": result.safety_severity,
                    "hit": result.safety_hit,
                }),
                1 if result.is_repeat else 0,
                int(result.repeat_count or 0),
                result.surge_topic,
                int(result.surge_count or 0),
                1 if result.escalate else 0,
                json.dumps(result.to_dict()),
            ),
        )


def topic_surge_report(
    tenant_id: str,
    *,
    window_days: int = 90,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Admin helper: top topics by distinct customers in the window."""
    from routing.database import get_db_context

    since = (datetime.now().astimezone() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_context() as conn:
        rows = conn.execute(
            """
            SELECT topics_json, COUNT(DISTINCT entity_key) AS customers, COUNT(*) AS messages
            FROM message_intelligence
            WHERE tenant_id = ? AND created_at >= ? AND topics_json != '[]' AND topics_json IS NOT NULL
            GROUP BY topics_json
            ORDER BY customers DESC
            LIMIT ?
            """,
            (tenant_id, since, limit),
        ).fetchall()
    out = []
    for r in rows:
        try:
            topics = json.loads(r["topics_json"] or "[]")
        except Exception:
            topics = []
        out.append({
            "topics": topics,
            "customers": r["customers"],
            "messages": r["messages"],
        })
    return out
