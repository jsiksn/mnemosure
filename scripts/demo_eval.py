"""
5단계(Part A) 시연 — 우리 시스템을 3축 정답표로 채점한다.

채점 도구(정답표 + LLM 채점관 + 토큰·길이 관찰)가 제대로 작동하는지,
우리 시스템 답변에 대해 회상 성공률·환각률·토큰을 낸다.
(베이스라인 핸드오프 비교와 세션별 회상 곡선은 Part B에서.)

실행: 프로젝트 루트에서  python3 scripts/demo_eval.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure.demo.sample_sessions import SESSIONS, SIDE_SESSIONS  # noqa: E402
from mnemosure.evaluation.answer_key import QUESTIONS  # noqa: E402
from mnemosure.evaluation.harness import evaluate  # noqa: E402
from mnemosure.memory.forget import run_forgetting  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402


def main():
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()

    print("시나리오 적재 + 망각 분류 중...")
    for s in SESSIONS + SIDE_SESSIONS:
        ingest_session(s["session_id"], s["date"], s["text"], store)
    run_forgetting(store)
    print(f"기억 {len(store.all())}개 준비 (유효 {len(store.active())}개).\n")

    def our_answer(question):
        r = recall(question, store)
        return {"answer": r.answer, "confidence": r.confidence, "tokens": r.tokens}

    report = evaluate(our_answer, QUESTIONS)

    print("=" * 74)
    print("문항별 채점  (정확성만 채점 / 토큰·길이는 '관찰', 점수 아님)")
    print("=" * 74)
    for r in report["rows"]:
        print(f"[{r['id']} · {r['axis']}] {r['question']}")
        print(f"   회상성공={r['recall_success']}  환각={r['hallucinated']}  "
              f"토큰={r['tokens']}  길이={r['len']}자  확신도={r['confidence']}")
        print(f"   채점사유: {r['note']}")
        print(f"   답변: {r['answer']}")
        print()

    s = report["summary"]
    print("=" * 74)
    print("요약 (우리 시스템)")
    print("=" * 74)
    print(f"  회상 성공률 : {s['회상_성공률'] * 100:.0f}%")
    print(f"  환각률      : {s['환각률'] * 100:.0f}%")
    print(f"  평균 토큰   : {s['평균_토큰']:.0f}   (간결성 관찰용 / 점수 아님)")
    print(f"  평균 길이   : {s['평균_길이']:.0f}자")


if __name__ == "__main__":
    main()
