"""
4단계 시연 — 망각(분별). 곁다리 잡무를 평소 회상에서 빼되, 직접 물으면 꺼내온다.

  1) 본론(SESSIONS) + 곁다리(SIDE_SESSIONS)를 함께 적재
  2) 망각 분류(run_forgetting) 실행 -> core/tangential 표시
  3) 넓은 질문("중요한 결정 요약") -> 곁다리(클라우드 사양/폴더 정리/로그)를 안 들먹이는가?
  4) 직접 질문("클라우드 사양 추정?")   -> 지운 게 아니므로 꺼내오는가?

실행: 프로젝트 루트에서  python3 scripts/demo_forget.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure.demo.sample_sessions import SESSIONS, SIDE_SESSIONS  # noqa: E402
from mnemosure.memory.forget import run_forgetting  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402


def main():
    # 깨끗한 창고에 본론 + 곁다리 적재.
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()

    print("세션 적재 중 (본론 + 곁다리)...")
    for s in SESSIONS + SIDE_SESSIONS:
        ingest_session(s["session_id"], s["date"], s["text"], store)
    print(f"기억 {len(store.all())}개 적재.\n")

    print("=" * 72)
    print("망각(분별) 실행 -> core / tangential 분류")
    print("=" * 72)
    run_forgetting(store)
    for m in store.all():
        print(f"  {m.id}: {m.scope:10s} | {m.content[:46]}")
    print()

    questions = [
        ("넓은 질문 — 곁다리를 들먹이지 않는가?", "이 봇 작업에서 중요한 결정들을 요약해줘."),
        ("직접 질문 — 지운 건 아니다", "클라우드 사양은 어떻게 추정했었지?"),
    ]
    for label, q in questions:
        print("=" * 72)
        print(f"[{label}]\n질문: {q}")
        print("=" * 72)
        r = recall(q, store)
        print(f"  확신도: {r.confidence}")
        print(f"  답변  : {r.answer}")
        print(f"  근거  : {', '.join(r.cited) if r.cited else '-'}")
        print(f"  (후보 관련도: {r.candidates})")
        print()


if __name__ == "__main__":
    main()
