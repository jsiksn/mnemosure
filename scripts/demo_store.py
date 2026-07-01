"""
2단계 시연 — 가상의 주식 봇 개발 세션을 넣어 '기억 남기기'를 눈으로 확인한다.

세션 3개를 순서대로 창고에 넣고, 추출된 기억의 출처·트리거·원인·연합(대체/원인)을 출력한다.
시나리오는 mnemosure/demo/sample_sessions.py 에서 가져온다(회상 데모와 공유).

확인 포인트:
  (가) S3의 전면교체가 S1·S2의 괴리율 결정 '둘 다'를 동시에 대체하는가? (여러 건 대체)
  (나) S3의 전면교체가 S3의 실패(괴리율 2%)와 because(원인)로 이어지는가?

실행: 프로젝트 루트에서  python3 scripts/demo_store.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure.demo.sample_sessions import SESSIONS  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402


def main():
    # 시연이므로 매번 깨끗한 빈 창고에서 시작한다.
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()

    for s in SESSIONS:
        print("=" * 72)
        print(f"세션 {s['session_id']} ({s['date']}) 입력 -> 기억 추출 / 저장")
        print("=" * 72)
        mems = ingest_session(s["session_id"], s["date"], s["text"], store)
        for m in mems:
            print("  + " + m.short())
            if m.triggers:
                print(f"        트리거: {', '.join(m.triggers)}")
            if m.reason:
                print(f"        원인(텍스트): {m.reason}")
            for a in m.associations:
                print(f"        연합: {a.type} -> {a.target_id}  ({a.note})")
        print()

    print("=" * 72)
    print("최종 기억 창고 상태")
    print("=" * 72)
    for m in store.all():
        print("  " + m.short())
        for a in m.associations:
            print(f"        └ {a.type} -> {a.target_id}")

    print(f"\n총 {len(store.all())}개 기억 (유효 active {len(store.active())}개).")
    print(f"저장 위치: {store.path}")


if __name__ == "__main__":
    main()
