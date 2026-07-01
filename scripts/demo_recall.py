"""
3단계 시연 — 가상 세션을 적재한 뒤, 3축 질문으로 '기억 꺼내기'를 확인한다.

  - 축1 (누락) : 오래된 결정을 출처와 함께 회상하는가?
  - 축2 (환각) : 바뀐 사실(괴리율->체결강도)을 옛것으로 단정하지 않고 바로잡는가?
  - 모름 테스트: 기록에 없는 걸 물으면 지어내지 않고 '모름'이라 하는가?

실행: 프로젝트 루트에서  python3 scripts/demo_recall.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure.demo.sample_sessions import SESSIONS  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402


QUESTIONS = [
    ("축1 · 누락", "예전에 종목을 어떻게 골랐었지?"),
    ("축2 · 환각", "1차 필터 기준이 괴리율 맞지?"),
    ("모름 테스트", "백테스트 돌리는 서버는 어디에 배포했었지?"),
]


def main():
    # 깨끗한 창고에 시나리오 적재.
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()

    print("세션 적재 중...")
    for s in SESSIONS:
        ingest_session(s["session_id"], s["date"], s["text"], store)
    print(f"기억 {len(store.all())}개 적재 완료 (유효 active {len(store.active())}개).\n")

    for label, q in QUESTIONS:
        print("=" * 72)
        print(f"[{label}] 질문: {q}")
        print("=" * 72)
        r = recall(q, store)
        print(f"  확신도: {r.confidence}")
        print(f"  답변  : {r.answer}")
        print(f"  근거  : {', '.join(r.cited) if r.cited else '-'}")
        print(f"  (후보 관련도: {r.candidates})")
        print()


if __name__ == "__main__":
    main()
