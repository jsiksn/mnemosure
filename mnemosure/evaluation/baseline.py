"""
베이스라인 — 기존 '핸드오프 방식' (우리 시스템의 비교 대상).

세션이 끝날 때마다 '핸드오프 노트'를 길이 제한(budget) 안에서 다시 요약한다(최근 우선).
세션이 쌓이면 오래된 세부가 점점 밀려나 사라진다(누락). 출처·대체관계 추적이 없다(환각에 취약).

공정한 비교를 위해 '답변 모델'은 우리 시스템과 동일하게 qwen3.7-plus를 쓴다.
그래야 성능 차이가 '모델 능력'이 아니라 '기억 구조'에서만 나온다.
"""
from __future__ import annotations

from .. import config, llm
from ..memory.store import _cosine

HANDOFF_BUDGET = 300  # 핸드오프 노트 최대 길이(자). 작을수록 오래된 게 빨리 사라진다.

SUMMARIZE_SYS = f"""너는 다음 작업자에게 넘길 '핸드오프 노트'를 갱신한다.
이전 노트와 새 세션 내용을 합쳐, 약 {HANDOFF_BUDGET}자 이내의 한국어 노트로 다시 써라.
규칙: 최근 세션 내용을 우선한다. 분량이 넘치면 오래된 항목부터 압축·생략한다.
설명 없이 노트 본문만 출력한다."""

ANSWER_SYS = """너는 아래 '핸드오프 노트'만 보고 질문에 답하는 비서다.
노트에 있는 내용으로만 답하고, 노트에 없으면 모른다고 답한다. (별도 기억 검색 도구는 없다)
간결히 답하라."""


class HandoffBaseline:
    """길이 제한 핸드오프 노트를 굴리는 베이스라인."""

    def __init__(self, budget: int = HANDOFF_BUDGET):
        self.note = ""
        self.budget = budget

    def ingest(self, session_text: str) -> None:
        """새 세션을 노트에 합치고, 예산 안에서 다시 요약한다(최근 우선)."""
        user = f"[이전 노트]\n{self.note or '(없음)'}\n\n[새 세션]\n{session_text}"
        r = llm.chat(
            [{"role": "system", "content": SUMMARIZE_SYS},
             {"role": "user", "content": user}],
            model=config.MODEL_FLASH, temperature=0,
        )
        # 안전장치: 너무 길게 나오면 잘라 무한 성장 방지(요약 자체가 최근 우선).
        self.note = r.text.strip()[: self.budget + 200]

    def answer(self, question: str, model: str = config.MODEL_BRAIN) -> dict:
        """핸드오프 노트만 근거로 답한다. (출처·확신도·대체관계 개념 없음)"""
        user = f"[핸드오프 노트]\n{self.note}\n\n[질문]\n{question}"
        r = llm.chat(
            [{"role": "system", "content": ANSWER_SYS},
             {"role": "user", "content": user}],
            model=model, temperature=0,
        )
        return {"answer": r.text.strip(), "confidence": "-", "tokens": r.usage.get("total_tokens", 0)}


# --- 두 번째 베이스라인: 나이브 RAG (과거 로그 검색형) ----------------------
RAG_SYS = """다음은 과거 작업 기록에서 검색된 조각들이다. 이 조각들에 근거해 질문에 답하라.
조각에 없으면 모른다고 답하라. 간결히 답하라."""


class NaiveRagBaseline:
    """과거 세션 원문을 줄 단위 청크로 쌓고, 질문에 의미 가까운 top-k 청크를 찾아 답한다.

    출처·시점·대체관계 추적이 없다. 그래서 옛 사실 청크가 검색되면 그게 폐기된 줄 모르고
    현재처럼 단정(환각)하기 쉽다. (기획서의 '조회 vs 메모리' 대비의 '조회'쪽)
    """

    def __init__(self, k: int = 4):
        self.chunks: list[tuple[str, list[float]]] = []
        self.k = k

    def ingest(self, session_text: str) -> None:
        for line in session_text.split("\n"):
            line = line.strip()
            if line:
                self.chunks.append((line, llm.embed(line)[0]))

    def answer(self, question: str, model: str = config.MODEL_BRAIN) -> dict:
        if not self.chunks:
            return {"answer": "기록 없음", "confidence": "-", "tokens": 0}
        qv = llm.embed(question)[0]
        top = sorted(self.chunks, key=lambda c: _cosine(qv, c[1]), reverse=True)[: self.k]
        ctx = "\n".join(f"- {t}" for t, _ in top)
        r = llm.chat(
            [{"role": "system", "content": RAG_SYS},
             {"role": "user", "content": f"[검색된 과거 기록]\n{ctx}\n\n[질문]\n{question}"}],
            model=model, temperature=0,
        )
        return {"answer": r.text.strip(), "confidence": "-", "tokens": r.usage.get("total_tokens", 0)}
