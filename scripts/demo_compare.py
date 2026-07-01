"""
5단계 - 축별 before/after 비교 (우리 vs 핸드오프 vs 나이브 RAG).

  - 누락 : 이유·폐기시도·역사 (핸드오프가 '현재 상태'만 남기며 버리는 것)
  - 환각 : 폐기된 괴리율을 현재로 단정하나 (RAG가 옛 청크를 검색해 단정하기 쉬움)
  - 곁다리: 넓은 질문에 끝난 잡무를 먼저 들먹이나 (들먹이면 나쁨)
  - 모름 : 기록에 없는 걸 정직히 모른다 하나

답변 모델은 세 시스템 모두 qwen3.7-plus. 차이는 '기억 구조'에서만.
실행: 프로젝트 루트에서  python3 scripts/demo_compare.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure.demo.sample_sessions import EVAL_SESSIONS  # noqa: E402
from mnemosure.evaluation.answer_key import (  # noqa: E402
    HALLUCINATION, RECALL_HISTORY, TANGENTIAL, UNKNOWN,
)
from mnemosure.evaluation.baseline import HandoffBaseline, NaiveRagBaseline  # noqa: E402
from mnemosure.evaluation.judge import judge  # noqa: E402
from mnemosure.memory.forget import run_forgetting  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402


def mark(ok):
    return "O" if ok else "X"


def main():
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()
    handoff = HandoffBaseline()
    rag = NaiveRagBaseline()

    print(f"{len(EVAL_SESSIONS)}세션을 세 시스템에 적재 중...")
    for s in EVAL_SESSIONS:
        ingest_session(s["session_id"], s["date"], s["text"], store)
        handoff.ingest(s["text"])
        rag.ingest(s["text"])
    run_forgetting(store)
    print("적재 완료.\n")

    systems = {
        "우리": lambda q: recall(q, store).answer,
        "핸드오프": lambda q: handoff.answer(q)["answer"],
        "RAG": lambda q: rag.answer(q)["answer"],
    }

    # --- 누락: 회상 성공(O/X) ---
    print("=" * 70)
    print("[누락] 이유·폐기시도·역사 회상  (O=회상 성공)")
    print("=" * 70)
    print(f"  {'문항':<34} 우리  핸드오프  RAG")
    for q in RECALL_HISTORY:
        res = {}
        for name, fn in systems.items():
            ans = fn(q["question"])
            res[name] = judge(q["question"], ans, q["must_include"], [], False)["recall_success"]
        print(f"  {q['question'][:32]:<34} {mark(res['우리']):^3}  {mark(res['핸드오프']):^6}  {mark(res['RAG']):^3}")

    # --- 환각: 옳게 답(O/X) + 환각여부(H) ---
    print("\n" + "=" * 70)
    print("[환각] 폐기된 괴리율을 현재로 단정하나  (O=옳음, H=환각 발생)")
    print("=" * 70)
    print(f"  {'문항':<34} 우리  핸드오프  RAG")
    for q in HALLUCINATION:
        cells = {}
        for name, fn in systems.items():
            ans = fn(q["question"])
            v = judge(q["question"], ans, q["must_include"], q["must_not_assert"], False)
            tag = mark(v["recall_success"])
            if v["hallucinated"]:
                tag += "/H"
            cells[name] = tag
        print(f"  {q['question'][:32]:<34} {cells['우리']:^3}  {cells['핸드오프']:^6}  {cells['RAG']:^3}")

    # --- 곁다리: 잡무 들먹임 여부(Yes 나쁨) ---
    print("\n" + "=" * 70)
    print("[곁다리] 넓은 질문에 끝난 잡무를 들먹이나  (Yes=나쁨)")
    print("=" * 70)
    print(f"  {'문항':<34} 우리  핸드오프  RAG")
    for q in TANGENTIAL:
        cells = {}
        for name, fn in systems.items():
            ans = fn(q["question"])
            volunteered = any(kw in ans for kw in q["tangent_keywords"])
            cells[name] = "Yes" if volunteered else "No"
        print(f"  {q['question'][:32]:<34} {cells['우리']:^3}  {cells['핸드오프']:^6}  {cells['RAG']:^3}")

    # --- 모름: 정직히 모른다 하나(O) ---
    print("\n" + "=" * 70)
    print("[모름] 기록 없는 걸 정직히 모른다 하나  (O=정직, H=지어냄)")
    print("=" * 70)
    print(f"  {'문항':<34} 우리  핸드오프  RAG")
    for q in UNKNOWN:
        cells = {}
        for name, fn in systems.items():
            ans = fn(q["question"])
            v = judge(q["question"], ans, q["must_include"], q["must_not_assert"], True)
            tag = mark(v["recall_success"])
            if v["hallucinated"]:
                tag += "/H"
            cells[name] = tag
        print(f"  {q['question'][:32]:<34} {cells['우리']:^3}  {cells['핸드오프']:^6}  {cells['RAG']:^3}")


if __name__ == "__main__":
    main()
