"""
5단계 - 환각 입증 (암묵적 대체 + 약한 모델).

시나리오에 "폐기/교체" 같은 명시적 단어 없이, 그냥 새 1차 필터를 정한다(암묵적 대체).
  - 우리: 저장 시점에 '체결강도 1차필터가 괴리율 1차필터를 대체'한다고 스스로 추론 -> superseded 표시.
  - RAG : 원문에 '폐기'가 없어, 약한 모델이 옛 괴리율 조각을 검색해 현재로 우김(환각).

실행: 프로젝트 루트에서  python3 scripts/demo_hallucination_implicit.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure import config  # noqa: E402
from mnemosure.evaluation.answer_key import HALLUCINATION  # noqa: E402
from mnemosure.evaluation.baseline import HandoffBaseline, NaiveRagBaseline  # noqa: E402
from mnemosure.evaluation.judge import judge  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402

# 암묵적 대체: 어디에도 "괴리율 폐기/교체/대신" 같은 말이 없다. 그냥 새 필터를 정할 뿐.
IMPLICIT_SESSIONS = [
    {"session_id": "J1", "date": "2026-03-15",
     "text": """사용자: 수동 워치리스트는 그만하고 NXT 등락률 상위 자동 탐색으로 가자.
어시스턴트: 네, 자동 탐색으로 전환하겠습니다.
사용자: 1차 필터는 괴리율로 하자. NXT와 KRX 가격 괴리율 3% 이상만 1차로 거른다.
어시스턴트: 1차 필터를 괴리율 3% 이상으로 설정하겠습니다."""},
    {"session_id": "J2", "date": "2026-03-22",
     "text": """사용자: 손절은 -3%에서 무조건 청산. 매수는 종목당 50만원 고정.
어시스턴트: 손절 -3%, 1회 매수 50만원으로 설정하겠습니다.
사용자: 확정."""},
    {"session_id": "J3", "date": "2026-04-05",
     "text": """사용자: 1차 필터는 체결강도와 거래대금으로 가자. 일평균 거래대금 100억 이상만 통과.
어시스턴트: 네, 1차 필터를 체결강도와 거래대금(일평균 100억 이상) 기준으로 설정하겠습니다.
사용자: 확정."""},
    {"session_id": "J4", "date": "2026-04-15",
     "text": """사용자: 봇 이름은 NXTBot으로 가자.
어시스턴트: 네, NXTBot으로 확정하겠습니다."""},
]

MODELS = [("강한(plus)", config.MODEL_BRAIN), ("약한(flash)", config.MODEL_FLASH)]


def tag(v):
    return ("O" if v["recall_success"] else "X") + ("/H" if v["hallucinated"] else "")


def main():
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()
    handoff = HandoffBaseline()
    rag = NaiveRagBaseline()

    print("암묵적 대체 시나리오 적재 중 ('폐기'라는 말은 어디에도 없음)...")
    for s in IMPLICIT_SESSIONS:
        ingest_session(s["session_id"], s["date"], s["text"], store)
        handoff.ingest(s["text"])
        rag.ingest(s["text"])

    print("\n[우리 시스템이 '대체'를 스스로 추론했는지 확인] (괴리율이 superseded면 성공)")
    for m in store.all():
        if "괴리율" in m.content or "체결강도" in m.content:
            print(f"  {m.id}: status={m.status:10s} | {m.content[:50]}")
    print()

    for q in HALLUCINATION:
        print("=" * 64)
        print(f"[{q['id']}] {q['question']}   (O=옳음, H=환각)")
        print("=" * 64)
        print(f"  {'답변모델':<12} 우리   핸드오프   RAG")
        last = {}
        for mname, model in MODELS:
            answers = {
                "우리": recall(q["question"], store, answer_model=model).answer,
                "핸드오프": handoff.answer(q["question"], model=model)["answer"],
                "RAG": rag.answer(q["question"], model=model)["answer"],
            }
            cells = {n: tag(judge(q["question"], a, q["must_include"], q["must_not_assert"], False))
                     for n, a in answers.items()}
            print(f"  {mname:<12} {cells['우리']:^4}  {cells['핸드오프']:^6}  {cells['RAG']:^4}")
            if model == config.MODEL_FLASH:
                last = answers
        print(f"\n  약한 모델 답변:")
        print(f"    - RAG : {last['RAG'][:140]}")
        print(f"    - 우리: {last['우리'][:140]}")
        print()


if __name__ == "__main__":
    main()
