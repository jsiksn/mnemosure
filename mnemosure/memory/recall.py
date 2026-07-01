"""
기억 꺼내기 (3단계 — 회상 코어).

질문을 받으면:
  1) 질문을 벡터로 바꿔 창고에서 의미가 가까운 기억 후보를 모은다 (대체된 옛 기억도 포함!).
  2) qwen3-rerank로 후보를 질문 관련도 순으로 정밀 재정렬한다.
  3) 상위 기억의 연합(대체/원인) 링크를 따라가 사슬을 펼친다 (연합 인출).
  4) qwen3.7-plus(메인 두뇌)가 그 증거에만 근거해 확신도(확실/어렴풋/모름)와 함께 답한다.
     - 옛 기억이 'superseded'면 사실로 단정하지 않고 새 것으로 바로잡는다(환각 차단).
     - 근거가 없으면 지어내지 않고 '기록에 없다'고 답한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config, qwen_client
from .models import Memory
from .storage import MemoryStore
from .store import _cosine, _parse_json  # 같은 보조 함수 재사용(중복 방지)


CANDIDATE_K = 6        # 임베딩으로 1차로 모을 후보 수
EVIDENCE_N = 4         # rerank 후 '씨앗 증거'로 쓸 상위 수
RERANK_FLOOR = 0.15    # 최상위 관련도가 이보다 낮으면 근거 없음(모름)으로 본다


@dataclass
class RecallResult:
    """회상 한 번의 결과."""
    query: str
    confidence: str                         # 확실 | 어렴풋 | 모름
    answer: str
    cited: list[str] = field(default_factory=list)
    tokens: int = 0                         # 답변 생성에 쓴 토큰 (토큰 효율 측정용)
    candidates: list[dict] = field(default_factory=list)  # 투명성/디버그용


ANSWER_SYSTEM = """너는 출처에 근거하는 메모리 비서다. 아래 '기억 증거'에만 근거해 '질문과 같은 언어'로 답한다(질문이 한국어면 한국어, 영어면 영어).
규칙:
1) 증거에 없는 내용은 절대 지어내지 않는다.
2) 어떤 기억이 status=superseded(대체됨)이고 그것을 대체한 새 기억이 증거에 있으면,
   옛 정보를 현재 사실로 단정하지 말고 "그건 이전 방식이고 지금은 ~로 바뀌었다"고 바로잡는다.
   가능하면 바뀐 이유(because로 연결된 원인)도 함께 말한다.
3) 신뢰도를 셋 중 하나로 정한다:
   - "확실": 증거가 질문에 명확히 답함
   - "어렴풋": 관련은 있으나 불완전 -> 아는 부분과 모르는 부분을 나눠 솔직히
   - "모름": 근거 없음 -> 지어내지 말고 "기록에 남아 있지 않다"고 답함
4) 답변 끝에 근거 출처를 붙인다. 출처는 각 증거의 '출처='에 적힌 '제목/날짜'를 그대로 쓴다(mem_001·E1 같은 내부 코드는 쓰지 않는다).
5) 질문이 물은 것에 초점을 맞춰 간결히 답한다. 답을 이해하는 데 직접 기여하는 맥락만 덧붙이고, 다른 줄기 정보는 나열하지 않는다.
   단, 사용자가 '요약/정리/전체/지금까지의 결정'처럼 넓게 물으면, 증거에 있는 핵심 결정(core)을 빠짐없이 폭넓게 정리한다.
6) 각 기억의 '원인메모(reason)'와 because 링크에 바뀐 이유가 있으면 반드시 활용한다.
7) scope=tangential(운영·환경 등 곁다리) 기억은 질문이 그것을 '직접' 물을 때만 답에 쓴다. 일반·요약 질문에서는 언급하지 않는다.
8) '왜 바꿨어' '어떻게 바뀌었어' '변천' 등 이유·역사를 물으면, 바뀐 결정과 그 원인(because/원인메모)을 함께 설명한다.
   변경이 여러 단계였다면 핵심이 되는 변경과 그 이유를 우선 설명하고, 이유가 따로 없는 사소한 후속 보완(수치 구체화 등)에 집착하지 않는다.

confidence 값은 항상 한국어 토큰(확실/어렴풋/모름) 그대로 쓰고, answer 는 질문과 같은 언어로 쓴다.
JSON으로만 답한다:
{"confidence": "확실|어렴풋|모름", "answer": "질문과 같은 언어의 답변(출처 포함)", "cited": ["mem_002", ...]}"""


# '전체를 훑는' 요약·정리형 질문 단서. 이런 질문은 상위 몇 개만 보면 핵심을 빠뜨린다.
_OVERVIEW_HINTS = ("요약", "정리", "전체", "모든", "중요한 결정", "지금까지", "목록", "리스트", "뭐가 있", "어떤 결정")


def _is_overview(query: str) -> bool:
    return any(h in query for h in _OVERVIEW_HINTS)


def recall(query: str, store: MemoryStore, answer_model: str = config.MODEL_BRAIN) -> RecallResult:
    memories = [m for m in store.all() if m.embedding]
    if not memories:
        return RecallResult(query, "모름", "기록에 남아 있는 기억이 없습니다.")

    if _is_overview(query):
        # 넓은 요약·정리 질문: 상위 K개가 아니라 '활성 기억 전체'를 근거로 준다(요약 누락 방지).
        # 곁다리(tangential)는 답변 프롬프트 규칙 7이 일반·요약 질문에서 거르므로 같이 넘겨도 안전하다.
        evidence = [m for m in memories if m.status == "active"]
        cand_view = [{"id": m.id} for m in evidence]
    else:
        # 1) 임베딩 검색 — 대체된 기억도 포함해서 모은다(바로잡으려면 옛것을 찾아야 한다).
        qvec = qwen_client.embed(query)[0]
        scored = sorted(
            ((_cosine(qvec, m.embedding), m) for m in memories),
            key=lambda x: x[0], reverse=True,
        )
        candidates = [m for _s, m in scored[:CANDIDATE_K]]

        # 2) rerank — 후보를 질문 관련도 순으로 정밀 재정렬.
        hits = qwen_client.rerank(query, [m.content for m in candidates])
        ranked = sorted(
            ((candidates[h.index], h.score) for h in hits),
            key=lambda x: x[1], reverse=True,
        )
        cand_view = [{"id": m.id, "score": round(s, 3)} for m, s in ranked]

        # 가장 관련 있는 것조차 동떨어졌으면 -> 근거 없음(지어내지 않는다).
        if not ranked or ranked[0][1] < RERANK_FLOOR:
            return RecallResult(query, "모름", "그 부분은 제 기억에 남아 있지 않습니다.", candidates=cand_view)

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
        confidence=result.get("confidence", "어렴풋"),
        answer=result.get("answer", ""),
        cited=result.get("cited", []),
        tokens=tokens,
        candidates=cand_view,
    )


def _answer(messages, model=config.MODEL_BRAIN):
    """두뇌 호출 -> (파싱된 결과, 사용 토큰). JSON 모드 실패 시 평범 모드로 재시도."""
    for kwargs in ({"response_format": {"type": "json_object"}, "temperature": 0}, {"temperature": 0}):
        try:
            resp = qwen_client.chat(messages, model=model, **kwargs)
            return _parse_json(resp.text), resp.usage.get("total_tokens", 0)
        except Exception:
            continue
    return {"confidence": "어렴풋", "answer": "(응답을 해석하지 못했습니다)", "cited": []}, 0


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
