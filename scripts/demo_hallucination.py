"""
5단계 - 환각 입증 (약한 모델 대조).

같은 환각 문항을 '강한 모델(plus)'과 '약한 모델(flash)'로 각각 답하게 해 비교한다.
가설: 강한 모델에선 셋 다 안 틀리지만, 약한 모델에선 RAG가 옛 사실(괴리율)을 우긴다(환각).
우리는 저장 시점에 'superseded' 표시를 박아둬서, 약한 모델도 그 표시만 읽어 안 틀린다.
(= 쓰기 시점 추론 -> 답변 시점 부담↓, 약한 모델로도 견고)

실행: 프로젝트 루트에서  python3 scripts/demo_hallucination.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure import config  # noqa: E402
from mnemosure.demo.sample_sessions import EVAL_SESSIONS  # noqa: E402
from mnemosure.evaluation.answer_key import HALLUCINATION  # noqa: E402
from mnemosure.evaluation.baseline import HandoffBaseline, NaiveRagBaseline  # noqa: E402
from mnemosure.evaluation.judge import judge  # noqa: E402
from mnemosure.memory.forget import run_forgetting  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402

MODELS = [("강한(plus)", config.MODEL_BRAIN), ("약한(flash)", config.MODEL_FLASH)]


def tag(v):
    t = "O" if v["recall_success"] else "X"
    return t + ("/H" if v["hallucinated"] else "")


def main():
    store = MemoryStore()
    store.memories = []
    store._counter = 0
    store.save()
    handoff = HandoffBaseline()
    rag = NaiveRagBaseline()

    print(f"{len(EVAL_SESSIONS)}세션 적재 중...")
    for s in EVAL_SESSIONS:
        ingest_session(s["session_id"], s["date"], s["text"], store)
        handoff.ingest(s["text"])
        rag.ingest(s["text"])
    run_forgetting(store)
    print("적재 완료. (O=옳음, H=환각 발생)\n")

    for q in HALLUCINATION:
        print("=" * 64)
        print(f"[{q['id']}] {q['question']}")
        print("=" * 64)
        print(f"  {'답변모델':<12} 우리   핸드오프   RAG")
        rag_flash_answer = None
        for mname, model in MODELS:
            answers = {
                "우리": recall(q["question"], store, answer_model=model).answer,
                "핸드오프": handoff.answer(q["question"], model=model)["answer"],
                "RAG": rag.answer(q["question"], model=model)["answer"],
            }
            cells = {}
            for name, ans in answers.items():
                v = judge(q["question"], ans, q["must_include"], q["must_not_assert"], False)
                cells[name] = tag(v)
            print(f"  {mname:<12} {cells['우리']:^4}  {cells['핸드오프']:^6}  {cells['RAG']:^4}")
            if model == config.MODEL_FLASH:
                rag_flash_answer = answers["RAG"]
                our_flash_answer = answers["우리"]
        print(f"\n  약한 모델 답변 비교:")
        print(f"    - RAG : {rag_flash_answer[:130]}")
        print(f"    - 우리: {our_flash_answer[:130]}")
        print()


if __name__ == "__main__":
    main()
