"""
기억 남기기 (2단계 — 저장 코어).

세션 대화에서 '나중에 중요할' 결정·변경·실패만 추려(extract),
출처·트리거·원인을 붙이고, 기존 기억과의 연합(association)을 이어 창고에 넣는다.

연합은 두 종류를 잇는다:
  - 대체(supersedes) : 새 결정이 옛 결정(들)을 갈아엎으면 옛 것을 'superseded'로 표시.
                       한 변경이 여러 옛 결정을 '동시에' 대체할 수 있다(후보 전부 검사).
                       단, 실패·교훈(failure)은 영구 보존해야 하므로 대체 대상에서 제외한다.
  - 원인(because)    : 그 결정을 하게 만든 실패·관찰 기억과 연결(인과 사슬).
                       회상 때 '바꿈 + 왜 바꿨는지'를 함께 끌어오는 재료가 된다.

  extract_memories() : 세션 글 -> 기억 후보 목록 (LLM 추출, flash 사용)
  ingest_session()   : 추출 + 임베딩 + 대체/원인 연결 + 저장까지 한 번에
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np

from .. import config, qwen_client
from .models import Association, Memory, Source
from .storage import MemoryStore


# 의미 유사도가 이 값 이상일 때만 연합 후보로 본다(불필요한 모델 호출을 줄이는 1차 거름망).
# 대체 후보 1차 거름망. 한 변경이 여러 옛 결정을 대체할 때, 어휘가 조금 다른 옛 결정
# (예: '괴리율 적용 시간대'가 '체결강도 변경'에) 도 후보로 잡히도록 약간 느슨하게. 최종 판단은 LLM.
SUPERSEDE_THRESHOLD = 0.35
# 원인 후보 1차 거름망. 인과는 어휘가 서로 달라(예: '체결강도 변경' vs '괴리율 신호부족') 임베딩
# 유사도가 낮게 나오기 쉽다. 그래서 느슨하게 두고(0.15), 실제 인과 판단은 LLM(is_cause)에 맡긴다.
CAUSE_THRESHOLD = 0.15


# --- 1) 추출: 세션 글에서 핵심만 골라 JSON으로 받기 -------------------------
EXTRACT_SYSTEM = """너는 개발 세션 기록에서 '나중에 다시 중요해질' 것만 골라내는 메모리 추출기다.
다음만 추출한다: 결정(decision), 변경(change), 실패·폐기(failure), 확정된 사실(fact).
잡담·일회성 질문·단순 진행상황은 버린다. 단, '시도했다가 안 됐다'는 실패도 반드시 남긴다.

아래 JSON 형식으로만 출력한다(다른 설명 문장 금지):
{"memories": [
  {"content": "핵심을 담은 간결한 한국어 한 문장",
   "kind": "decision|change|failure|fact",
   "triggers": ["떠올릴 단서 키워드", "..."],
   "reason": "왜 그렇게 했는지(없으면 빈 문자열)"}
]}"""


def extract_memories(session_text: str, model: str = config.MODEL_FLASH) -> list[dict[str, Any]]:
    """세션 글을 넣으면 기억 후보 목록(딕셔너리들)을 돌려준다."""
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": f"다음 세션 기록에서 기억을 추출하라:\n\n{session_text}"},
    ]
    data = _chat_json(messages, model)
    return data.get("memories", [])


# --- 2) 연합 판정 프롬프트 -------------------------------------------------
SUPERSEDE_PROMPT = """새 기억이 옛 기억을 '대체하거나 폐기'하는가?
- 같은 대상의 결정·방식 자체가 새 것으로 갈아엎어졌거나, 새 것이 옛 것을 명시적으로 폐기하면: true
- 같은 분야지만 서로 다른 항목·설정이라 둘 다 여전히 유효하면: false
- 옛 결정은 그대로 두고 그 안의 한 항목을 더 구체화하거나 수치를 덧붙이는 '후속 보완'이면: false
  (예: '체결강도·거래대금으로 거른다'는 결정에 '거래대금 일평균 100억 이상' 조건을 더하는 것은 대체가 아니라 보완)
JSON으로만 답하라: {{"supersedes": true 또는 false}}

[옛 기억] {old}
[새 기억] {new}"""

CAUSE_PROMPT = """결정·변경과, 그 이전의 실패·관찰 기록이 있다.
그 실패·관찰이 이 결정·변경을 하게 된 '직접적인 원인·계기'인가? 엄격히 판단하라.
- true: 그 실패 '때문에' 방식 자체를 바꾸거나 새 방식을 채택한 경우
  (예: 괴리율이 신호 부족으로 실패 → 그래서 체결강도 방식으로 전환).
- false: 이미 채택한 새 방식의 세부를 구체화·수치 조정·후속 보완하는 결정은 옛 실패가 직접 원인이 아니다
  (예: 체결강도로 바꾼 뒤 '거래대금 일평균 100억 이상' 같은 조건을 정하는 것은 괴리율 실패가 원인이 아님).
- false: 단지 같은 주제·맥락이라는 이유만으로는 원인이 아니다.
JSON으로만 답하라: {{"is_cause": true 또는 false}}

[결정·변경] {decision}
[원인 후보] {cause}"""


def ingest_session(
    session_id: str,
    date: str,
    session_text: str,
    store: MemoryStore,
    extract_model: str = config.MODEL_FLASH,
    title: str = "",
) -> list[Memory]:
    """세션 하나를 통째로 받아: 추출 -> 임베딩 -> 대체/원인 연결 -> 저장.
    title: 사람이 읽는 세션 제목(있으면 기억 출처에 함께 저장 — 답변 출처 표기용)."""
    raw_items = extract_memories(session_text, model=extract_model)

    new_memories: list[Memory] = []
    for item in raw_items:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        triggers = [t for t in item.get("triggers", []) if t]

        # 임베딩 재료 = 핵심 + 단서. (단서가 나중 검색을 도와준다)
        embed_text = content + " / " + " ".join(triggers)
        vector = qwen_client.embed(embed_text)[0]

        mem = Memory(
            id=store.next_id(),
            content=content,
            kind=item.get("kind", "fact"),
            triggers=triggers,
            source=Source(session_id=session_id, date=date, title=title),
            reason=item.get("reason", ""),
            embedding=vector,
        )

        # 결정/변경이면 대체하는 기존 기억(들)을 찾아 연결한다.
        if mem.kind in ("change", "decision"):
            _link_supersession(mem, store)

        store.add(mem)
        new_memories.append(mem)

    # 2차 패스: 원인(because) 연결.
    # 세션의 모든 기억이 들어온 뒤에 한다 — 원인(실패)이 결정보다 늦게 추출돼도 놓치지 않도록.
    for mem in new_memories:
        if mem.kind in ("change", "decision"):
            _link_cause(mem, store)

    store.save()
    return new_memories


def _link_supersession(new_mem: Memory, store: MemoryStore) -> None:
    """새 결정/변경이 대체하는 '모든' 유효 결정을 찾아 연결하고 옛 것을 'superseded'로 표시한다.
    (실패·교훈 기억은 영구 보존해야 하므로 대체 대상에서 제외한다.)"""
    # 충분히 비슷한 기존 기억을 모두 모은다(실패 제외).
    scored: list[tuple[float, Memory]] = []
    for m in store.active():
        if not m.embedding or m.kind == "failure":
            continue
        sim = _cosine(new_mem.embedding, m.embedding)
        if sim >= SUPERSEDE_THRESHOLD:
            scored.append((sim, m))
    scored.sort(key=lambda x: x[0], reverse=True)

    # 의미가 가깝다고 무조건 대체는 아니다 -> 후보마다 모델에게 한 번씩 확인받는다.
    for _sim, old in scored:
        verdict = _chat_json(
            SUPERSEDE_PROMPT.format(old=old.content, new=new_mem.content),
            config.MODEL_FLASH,
        ).get("supersedes", False)
        if verdict:
            new_mem.associations.append(Association("supersedes", old.id, old.content))
            old.associations.append(Association("superseded_by", new_mem.id, new_mem.content))
            old.status = "superseded"


def _link_cause(new_mem: Memory, store: MemoryStore) -> None:
    """새 결정/변경의 '원인'이 된 실패·관찰 기억을 찾아 because 링크로 잇는다(가장 그럴듯한 1건)."""
    scored: list[tuple[float, Memory]] = []
    for m in store.active():
        if m.id == new_mem.id or not m.embedding:
            continue
        if m.kind != "failure":  # 원인 후보는 실패·관찰 기록으로 한정한다.
            continue
        sim = _cosine(new_mem.embedding, m.embedding)
        if sim >= CAUSE_THRESHOLD:
            scored.append((sim, m))
    if not scored:
        return

    scored.sort(key=lambda x: x[0], reverse=True)
    _sim, cause = scored[0]
    is_cause = _chat_json(
        CAUSE_PROMPT.format(decision=new_mem.content, cause=cause.content),
        config.MODEL_FLASH,
    ).get("is_cause", False)
    if is_cause:
        new_mem.associations.append(Association("because", cause.id, cause.content))


# --- 보조 함수 -------------------------------------------------------------
def _cosine(a, b) -> float:
    """두 벡터가 얼마나 같은 방향인지(=의미가 비슷한지) 0~1 점수로."""
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(va.dot(vb) / denom)


def _chat_json(messages, model: str) -> dict[str, Any]:
    """모델에 물어 JSON 응답을 받아 파싱한다. JSON 모드를 시도하고, 안 되면 평범하게 재시도.
    temperature=0 으로 고정 — 추출·대체판정·망각분류·채점이 재현 가능하도록(라벨 흔들림 방지)."""
    try:
        resp = qwen_client.chat(messages, model=model, response_format={"type": "json_object"}, temperature=0)
    except Exception:
        resp = qwen_client.chat(messages, model=model, temperature=0)
    return _parse_json(resp.text)


def _parse_json(text: str) -> dict[str, Any]:
    """모델이 코드블록이나 군더더기를 붙여도 최대한 JSON을 건져낸다."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise
