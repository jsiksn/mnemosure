"""
기억 꺼내기 (3단계 — 회상 코어).

질문을 받으면:
  1) 질문을 벡터로 바꿔 창고에서 의미가 가까운 기억 후보를 모은다 (대체된 옛 기억도 포함!).
  2) rerank 모델로 후보를 질문 관련도 순으로 정밀 재정렬한다.
     (rerank를 끈 경우엔 1차 유사도(코사인) 점수를 그대로 순위·게이트에 쓴다)
  3) 상위 기억의 연합(대체/원인) 링크를 따라가 사슬을 펼친다 (연합 인출).
  4) 메인 두뇌가 그 증거에만 근거해 확신도(certain/vague/unknown)와 함께 답한다.
     - 옛 기억이 'superseded'면 사실로 단정하지 않고 새 것으로 바로잡는다(환각 차단).
     - 근거가 없으면 지어내지 않고 '기록에 없다'고 답한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .. import config, llm
from .models import Memory
from .storage import MemoryStore
from .store import _cosine, _parse_json  # 같은 보조 함수 재사용(중복 방지)


CANDIDATE_K = 6        # 임베딩으로 1차로 모을 후보 수
EVIDENCE_N = 4         # rerank 후 '씨앗 증거'로 쓸 상위 수
# 정직 게이트: 최상위 관련도가 이보다 낮으면 근거 없음(unknown)으로 본다.
# 기본값은 기본 모델(cohere/rerank-4-fast · bge-m3) 기준 보정값 — 다른 모델을 쓰면 env로 조정.
RERANK_FLOOR = float(os.environ.get("MNEMOSURE_RERANK_FLOOR", "0.15"))   # rerank 점수용
COSINE_FLOOR = float(os.environ.get("MNEMOSURE_COSINE_FLOOR", "0.35"))   # rerank off일 때 코사인 점수용


@dataclass
class RecallResult:
    """회상 한 번의 결과."""
    query: str
    confidence: str                         # certain | vague | unknown
    answer: str
    cited: list[str] = field(default_factory=list)
    tokens: int = 0                         # 답변 생성에 쓴 토큰 (토큰 효율 측정용)
    candidates: list[dict] = field(default_factory=list)  # 투명성/디버그용


ANSWER_SYSTEM = """You are a source-grounded memory assistant. Answer ONLY from the [memory evidence] below, in the SAME LANGUAGE as the question (Korean question -> Korean answer, English question -> English answer).
Rules:
1) Never state anything that is not in the evidence.
2) If a memory has status=superseded and the memory that replaced it is also in the evidence,
   do NOT assert the old fact as current — correct it: "that was the old way; it has since changed to ~".
   When possible, also give the reason for the change (the cause linked via `because`).
3) Pick exactly one confidence level:
   - "certain": the evidence clearly answers the question
   - "vague": related but incomplete -> honestly separate what is known from what is not
   - "unknown": no grounds -> do not invent; answer "this is not in the record"
4) End the answer with its sources. Use the 'title/date' written in each evidence item's '출처=' field verbatim (never internal codes like mem_001 or E1).
5) Focus on what was asked and answer concisely. Add only context that directly helps, without listing unrelated threads.
   Exception: when the user asks broadly ("summary / overview / everything / decisions so far"), cover ALL core decisions in the evidence.
6) When a memory's reason note or `because` link explains a change, make sure to use it.
7) Use scope=tangential memories (ops/environment side notes) only when the question asks about them DIRECTLY. Never mention them in general or summary questions.
8) For "why did it change" / "how did it change" / history questions, explain the changed decision together with its cause (because/reason note).
   If there were multiple steps, lead with the pivotal change and its reason; do not dwell on minor follow-up refinements that have no reason of their own.

The confidence value must always be exactly one of the English tokens (certain/vague/unknown); the answer text follows the question's language.
Reply in JSON only:
{"confidence": "certain|vague|unknown", "answer": "answer in the question's language (with sources)", "cited": ["mem_002", ...]}"""


# 구버전(한국어 토큰) 호환: 모델이 옛 토큰으로 답해도 표준 토큰으로 정규화한다.
_CONF_NORMALIZE = {"확실": "certain", "어렴풋": "vague", "모름": "unknown"}


def _norm_conf(value: str, default: str = "vague") -> str:
    v = (value or "").strip()
    v = _CONF_NORMALIZE.get(v, v)
    return v if v in ("certain", "vague", "unknown") else default


def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def _not_in_record(query: str) -> str:
    """게이트가 닫혔을 때의 고정 답변 — 질문 언어에 맞춘다(정적 문자열이라 모델을 안 거친다)."""
    if _has_hangul(query):
        return "그 부분은 제 기억에 남아 있지 않습니다."
    return "That is not in my records."


# '전체를 훑는' 요약·정리형 질문 단서. 이런 질문은 상위 몇 개만 보면 핵심을 빠뜨린다.
_OVERVIEW_HINTS = ("요약", "정리", "전체", "모든", "중요한 결정", "지금까지", "목록", "리스트", "뭐가 있", "어떤 결정")


def _is_overview(query: str) -> bool:
    return any(h in query for h in _OVERVIEW_HINTS)


def recall(query: str, store: MemoryStore, answer_model: str = config.MODEL_BRAIN) -> RecallResult:
    memories = [m for m in store.all() if m.embedding]
    if not memories:
        return RecallResult(query, "unknown", _not_in_record(query))

    if _is_overview(query):
        # 넓은 요약·정리 질문: 상위 K개가 아니라 '활성 기억 전체'를 근거로 준다(요약 누락 방지).
        # 곁다리(tangential)는 답변 프롬프트 규칙 7이 일반·요약 질문에서 거르므로 같이 넘겨도 안전하다.
        evidence = [m for m in memories if m.status == "active"]
        cand_view = [{"id": m.id} for m in evidence]
    else:
        # 1) 임베딩 검색 — 대체된 기억도 포함해서 모은다(바로잡으려면 옛것을 찾아야 한다).
        qvec = llm.embed(query)[0]
        scored = sorted(
            ((_cosine(qvec, m.embedding), m) for m in memories),
            key=lambda x: x[0], reverse=True,
        )
        candidates = [m for _s, m in scored[:CANDIDATE_K]]

        # 2) 정밀 재정렬 — rerank 모델 사용(기본). 껐으면 코사인 점수를 그대로 쓴다.
        if config.RERANK_ENABLED:
            hits = llm.rerank(query, [m.content for m in candidates])
            ranked = sorted(
                ((candidates[h.index], h.score) for h in hits),
                key=lambda x: x[1], reverse=True,
            )
            floor = RERANK_FLOOR
        else:
            ranked = [(m, s) for s, m in scored[:CANDIDATE_K]]
            floor = COSINE_FLOOR
        cand_view = [{"id": m.id, "score": round(s, 3)} for m, s in ranked]

        # 가장 관련 있는 것조차 동떨어졌으면 -> 근거 없음(지어내지 않는다).
        if not ranked or ranked[0][1] < floor:
            return RecallResult(query, "unknown", _not_in_record(query), candidates=cand_view)

        # 끌어오기는 넓게(곁다리 포함). 망각(분별)은 '말하기' 단계(답변 프롬프트)에서
        # 관련성으로 거른다 -> 직접 물으면 꺼내오고, 일반 질문엔 곁다리를 안 들먹인다. (결정 3)
        seeds = [m for m, _s in ranked[:EVIDENCE_N]]

        # 3) 연합 인출 — 상위 기억의 대체/원인 링크를 2홉까지 펼친다.
        evidence = _expand(seeds, store)

    # 4) 근거 확인 + 확신도 + 답변 (메인 두뇌).
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": f"[질문]\n{query}\n\n[기억 증거]\n{_format_evidence(evidence)}"},
    ]
    result, tokens = _answer(messages, answer_model)

    return RecallResult(
        query=query,
        confidence=_norm_conf(result.get("confidence", "vague")),
        answer=result.get("answer", ""),
        cited=result.get("cited", []),
        tokens=tokens,
        candidates=cand_view,
    )


def _answer(messages, model=config.MODEL_BRAIN):
    """두뇌 호출 -> (파싱된 결과, 사용 토큰). JSON 모드 실패 시 평범 모드로 재시도."""
    for kwargs in ({"response_format": {"type": "json_object"}, "temperature": 0}, {"temperature": 0}):
        try:
            resp = llm.chat(messages, model=model, **kwargs)
            return _parse_json(resp.text), resp.usage.get("total_tokens", 0)
        except Exception:
            continue
    return {"confidence": "vague", "answer": "(failed to parse the model response)", "cited": []}, 0


def _expand(seeds: list[Memory], store: MemoryStore, max_hops: int = 2, cap: int = 8) -> list[Memory]:
    """씨앗 기억에서 연합(대체/원인) 링크를 따라가 관련 기억을 모은다(중복 제거, 상한 cap)."""
    seen = {m.id: m for m in seeds}
    frontier = list(seeds)
    for _ in range(max_hops):
        nxt = []
        for m in frontier:
            for a in m.associations:
                if a.target_id not in seen:
                    tgt = store.get(a.target_id)
                    if tgt:
                        seen[tgt.id] = tgt
                        nxt.append(tgt)
        frontier = nxt
        if len(seen) >= cap or not frontier:
            break
    return list(seen.values())[:cap]


def _format_evidence(evidence: list[Memory]) -> str:
    """증거 기억들을 메인 두뇌가 읽기 좋은 형태로 정리한다(상태·출처·연합 포함)."""
    lines = []
    for m in evidence:
        assoc = "; ".join(f"{a.type}->{a.target_id}({a.note})" for a in m.associations) or "없음"
        reason = f"\n  원인메모: {m.reason}" if m.reason else ""
        lines.append(
            f"- id={m.id} | kind={m.kind} | status={m.status} | scope={m.scope} | "
            f"출처={(m.source.title or m.source.session_id)}/{m.source.date}\n"
            f"  내용: {m.content}{reason}\n"
            f"  연합: {assoc}"
        )
    return "\n".join(lines)
