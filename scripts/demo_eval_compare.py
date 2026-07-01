"""
5단계 Part B 시연 — 베이스라인(기존 핸드오프) vs 우리 시스템.

  1) 세션별 회상 곡선: 세션을 점진 적재하며, 가장 오래된 결정을 체크포인트마다 양쪽에 물어
     회상 성공을 기록한다. (기대: 우리=평평, 베이스라인=세션 쌓일수록 우하향)
  2) before/after 표: 같은 정답표 5문항으로 양쪽 채점 -> 회상 성공률·환각률·토큰 비교.

답변 모델은 양쪽 동일(qwen3.7-plus). 차이는 '기억 구조'에서만 난다.
실행: 프로젝트 루트에서  python3 scripts/demo_eval_compare.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure.demo.sample_sessions import (  # noqa: E402
    EXTRA_SESSIONS, SESSIONS, SIDE_SESSIONS,
)
from mnemosure.evaluation.answer_key import QUESTIONS  # noqa: E402
from mnemosure.evaluation.baseline import HandoffBaseline  # noqa: E402
from mnemosure.evaluation.harness import evaluate  # noqa: E402
from mnemosure.evaluation.judge import judge  # noqa: E402
from mnemosure.memory.forget import run_forgetting  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402

# 날짜 순으로 전체 세션을 정렬(가장 오래된 것부터).
ALL = sorted(SESSIONS + SIDE_SESSIONS + EXTRA_SESSIONS, key=lambda s: s["date"])

# 곡선 추적용 '가장 오래된 결정' 질문.
ANCHOR_Q = "예전에 종목을 어떻게 골랐었지?"
ANCHOR_INCLUDE = ["처음엔 수동 워치리스트였고, 이후 NXT 등락률 상위 자동 탐색 방식으로 전환했다"]
CHECKPOINTS = {2, 4, len(ALL)}


def _recall_ok(question, answer):
    return judge(question, answer, ANCHOR_INCLUDE, [], False)["recall_success"]


def main():
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()
    base = HandoffBaseline()

    print(f"세션 {len(ALL)}개를 두 시스템에 점진 적재하며 '가장 오래된 결정' 회상을 추적합니다.\n")
    curve = []
    for i, s in enumerate(ALL, 1):
        ingest_session(s["session_id"], s["date"], s["text"], store)
        base.ingest(s["text"])
        if i in CHECKPOINTS:
            our = recall(ANCHOR_Q, store)
            bse = base.answer(ANCHOR_Q)
            o_ok = _recall_ok(ANCHOR_Q, our.answer)
            b_ok = _recall_ok(ANCHOR_Q, bse["answer"])
            curve.append((i, b_ok, o_ok))
            print(f"  [{i}세션 후] 베이스라인 회상={'O' if b_ok else 'X'} | 우리 회상={'O' if o_ok else 'X'}")
            print(f"      베이스라인 답: {bse['answer'][:120]}")
            print(f"      우리 답   : {our.answer[:120]}")
    print()

    # 우리 시스템: 망각 분류 후 정답표 채점.
    run_forgetting(store)
    print("정답표 5문항으로 양쪽 채점 중...\n")
    base_report = evaluate(base.answer, QUESTIONS)
    our_report = evaluate(lambda q: _our(recall(q, store)), QUESTIONS)

    print("=" * 60)
    print("[1] 세션별 '오래된 결정' 회상 곡선")
    print("=" * 60)
    print("  세션수 | 베이스라인 | 우리")
    for i, b_ok, o_ok in curve:
        print(f"   {i:3d}  |     {'O' if b_ok else 'X'}     |   {'O' if o_ok else 'X'}")
    print()

    bs, ours = base_report["summary"], our_report["summary"]
    print("=" * 60)
    print("[2] before/after  (정답표 5문항)")
    print("=" * 60)
    print(f"  지표          | 베이스라인 |   우리")
    print(f"  회상 성공률    |   {bs['회상_성공률']*100:4.0f}%  |  {ours['회상_성공률']*100:4.0f}%")
    print(f"  환각률        |   {bs['환각률']*100:4.0f}%  |  {ours['환각률']*100:4.0f}%")
    print(f"  평균 토큰(답변) |   {bs['평균_토큰']:5.0f}  |  {ours['평균_토큰']:5.0f}")
    print()

    print("베이스라인 문항별 (어디서 무너지나):")
    for r in base_report["rows"]:
        print(f"  [{r['id']}·{r['axis']}] 회상={r['recall_success']} 환각={r['hallucinated']}  ::  {r['answer'][:78]}")

    print("\n우리 시스템 문항별 (환각 원인 추적):")
    for r in our_report["rows"]:
        flag = "  <<환각!>>" if r["hallucinated"] else ""
        print(f"  [{r['id']}·{r['axis']}] 회상={r['recall_success']} 환각={r['hallucinated']}{flag}")
        print(f"        답변: {r['answer'][:110]}")
        print(f"        판정: {r['note']}")


def _our(r):
    return {"answer": r.answer, "confidence": r.confidence, "tokens": r.tokens}


if __name__ == "__main__":
    main()
