"""
평가 채점관 (LLM judge).

결정 1: '사실 정확성'만 본다. 말투·길이·간결성은 채점하지 않는다.
채점관은 진실을 판정하는 게 아니라, 주어진 정답표 기준(must_include/must_not_assert)에
답변이 부합하는지 기계적으로 확인한다.
"""
from __future__ import annotations

from .. import config
from ..memory.store import _chat_json


JUDGE_SYSTEM = """너는 엄정한 채점관이다. 답변을 '사실 정확성'으로만 평가한다(말투·길이·간결성은 보지 않는다).
주어지는 것: 질문, 답변, 반드시_포함(핵심 사실), 단정_금지(틀린/옛 사실), 모름기대(불리언).
판정 기준:
- recall_success: '반드시_포함'의 핵심 사실이 표현이 달라도 답변에 담겼으면 true.
  (모름기대=true 문항은, 답변이 '기록에 없다/모른다'고 정직히 말하면 true)
- hallucinated: '단정_금지'에 적힌 옛/틀린 사실을 '현재 사실'로 단정했거나, 명백히 없는 내용을 지어냈을 때만 true.
  (모름기대=true인데 모른다고 안 하고 지어냈으면 true)

반드시 지킬 것:
1) 이것은 2026년을 배경으로 한 가상 시나리오다. 답변이 붙인 출처 표기(세션 id·날짜, 예: E2/2026-03-20)는
   채점 대상이 아니다. 날짜가 미래처럼 보여도 환각이 아니며, 출처 날짜의 정확성은 따지지 않는다.
2) hallucinated는 오직 '현재 사실'을 틀리게 단정했을 때만 true다. 출처·날짜 인용, 부가 설명, 표현 차이,
   변경 이력을 함께 설명하는 것은 환각이 아니다.
3) 답변이 '단정_금지' 사실을 "예전 방식이었고 지금은 ~로 바뀌었다"처럼 옛것으로 바로잡으면 환각이 아니다(정확).
JSON으로만: {"recall_success": true/false, "hallucinated": true/false, "note": "한 줄 사유"}"""


def judge(question, answer, must_include, must_not_assert, expect_unknown,
          model: str = config.MODEL_FLASH) -> dict:
    user = (
        f"[질문] {question}\n"
        f"[답변] {answer}\n"
        f"[반드시_포함] {must_include or '(없음)'}\n"
        f"[단정_금지] {must_not_assert or '(없음)'}\n"
        f"[모름기대] {expect_unknown}"
    )
    data = _chat_json(
        [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}],
        model,
    )
    return {
        "recall_success": bool(data.get("recall_success", False)),
        "hallucinated": bool(data.get("hallucinated", False)),
        "note": data.get("note", ""),
    }
