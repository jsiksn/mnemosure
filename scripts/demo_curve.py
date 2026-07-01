"""
5단계 - 세션별 회상 곡선 (데모 클라이맥스).

핸드오프가 시간이 지나며 버리는 것 = '초기에 생긴 이유·폐기시도·변경 역사'.
이 5문항을, 변경이 누적되는 8세션을 점진 적재하며 체크포인트마다 양쪽에 물어 회상률을 잰다.

기대: 우리=평평(이유·역사를 구조적으로 보관), 핸드오프=세션 쌓일수록 우하향(초기 이유/역사 희석).
마지막 체크포인트의 회상률이 곧 before/after 회상 성공률.

실행: 프로젝트 루트에서  python3 scripts/demo_curve.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure.demo.sample_sessions import CURVE_SESSIONS  # noqa: E402
from mnemosure.evaluation.answer_key import CURVE_RECALL  # noqa: E402
from mnemosure.evaluation.baseline import HandoffBaseline  # noqa: E402
from mnemosure.evaluation.judge import judge  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402

CHECKPOINTS = {4, 8, len(CURVE_SESSIONS)}  # 12세션이면 {4,8,12}
HANDOFF_BUDGET = 800  # 더 현실적인 핸드오프 노트 크기(자)


def recall_rate(answer_fn, questions):
    ok = 0
    for q in questions:
        ans = answer_fn(q["question"])
        if judge(q["question"], ans, q["must_include"], [], False)["recall_success"]:
            ok += 1
    return ok / len(questions)


def main():
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()
    base = HandoffBaseline(budget=HANDOFF_BUDGET)

    print(f"초기 이유·폐기·역사 {len(CURVE_RECALL)}문항을 {len(CURVE_SESSIONS)}세션 점진 적재하며 추적.\n")
    curve = []
    for i, s in enumerate(CURVE_SESSIONS, 1):
        ingest_session(s["session_id"], s["date"], s["text"], store)
        base.ingest(s["text"])
        if i in CHECKPOINTS:
            our = recall_rate(lambda q: recall(q, store).answer, CURVE_RECALL)
            bse = recall_rate(lambda q: base.answer(q)["answer"], CURVE_RECALL)
            curve.append((i, bse, our))
            print(f"  [{i}세션 후] 핸드오프 회상률 {bse*100:3.0f}%  |  우리 {our*100:3.0f}%")

    print()
    print("=" * 50)
    print("세션별 회상 곡선  (초기 이유·역사 회상률)")
    print("=" * 50)
    print("  세션수 | 핸드오프 |  우리")
    for i, bse, our in curve:
        print(f"   {i:3d}  |  {bse*100:4.0f}%  | {our*100:4.0f}%")
    print()
    last = curve[-1]
    print(f"끝점(=before/after 회상 성공률): 핸드오프 {last[1]*100:.0f}% vs 우리 {last[2]*100:.0f}%")


if __name__ == "__main__":
    main()
