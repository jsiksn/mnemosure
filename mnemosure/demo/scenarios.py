"""
데모 시나리오 레지스트리.

여러 데모 시나리오를 한 곳에서 정의/조회한다. 각 시나리오는 자기 세션(입력)과
정답셋(평가)을 갖고, 사전계산 결과는 data/scenarios/<key>/{memories,results}.json 에 둔다.

새 시나리오 추가 = 세션(sample_sessions.py)·정답셋(evaluation/answer_key.py)을 만들고
아래 SCENARIOS 에 한 항목 추가하면 끝(서버·데모 UI·사전계산이 자동으로 인식).
"""
from __future__ import annotations

import os

from ..evaluation.answer_key import (
    CURVE_RECALL,
    PRICING_CURVE_RECALL,
    PRICING_QA_POOL,
    QA_POOL,
)
from .sample_sessions import (
    CURVE_SESSIONS,
    EVAL_SESSIONS,
    PRICING_CURVE_SESSIONS,
    PRICING_EVAL_SESSIONS,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCENARIOS_DIR = os.path.join(_ROOT, "data", "scenarios")


# 각 시나리오: key(경로·식별), title(사람이 읽는 이름), 세션들, 정답셋.
SCENARIOS = [
    {
        "key": "nxtbot",
        "title": "장전 자동매매 봇 (NXTBot)",
        "eval_sessions": EVAL_SESSIONS,
        "curve_sessions": CURVE_SESSIONS,
        "qa_pool": QA_POOL,
        "curve_recall": CURVE_RECALL,
        # 데모 예시 질문(칩): 환각교정 / 이유 / 곁다리 / 요약 / 모름 을 골고루.
        "sample_questions": [
            "1차 필터가 괴리율 맞지?",
            "1차 필터를 왜 바꿨어?",
            "클라우드 사양은 어떻게 추정했었지?",
            "지금까지 중요한 결정들 요약해줘",
            "백테스트 서버는 어디에 배포했었지?",
        ],
    },
    {
        "key": "pricing",
        "title": "구독 요금제 개편",
        "eval_sessions": PRICING_EVAL_SESSIONS,
        "curve_sessions": PRICING_CURVE_SESSIONS,
        "qa_pool": PRICING_QA_POOL,
        "curve_recall": PRICING_CURVE_RECALL,
        # 곡선이 테스트하는 마지막 변경(Free 한도 축소)이 5번째 세션에 일어나므로,
        # 측정은 세션 5 이후부터(그 전엔 사건이 없어 회상 불가 → 우리도 낮게 나옴).
        "curve_checkpoints": [5, 6, 7, 8, 9],
        "sample_questions": [
            "지금 Pro 요금이 월 12달러 맞지?",
            "Pro 요금을 왜 내렸어?",
            "연간 결제 할인이 20% 맞지?",
            "지금까지 정한 요금 정책을 요약해줘",
            "엔터프라이즈 요금은 얼마로 정했어?",
        ],
    },
]

_BY_KEY = {s["key"]: s for s in SCENARIOS}


def all_scenarios() -> list[dict]:
    return SCENARIOS


def get(key: str) -> dict | None:
    return _BY_KEY.get(key)


def default_key() -> str:
    return SCENARIOS[0]["key"]


def resolve_key(key: str | None) -> str:
    """요청으로 온 key 가 유효하면 그대로, 아니면 기본 시나리오 key 로."""
    return key if key in _BY_KEY else default_key()


def memories_path(key: str) -> str:
    return os.path.join(SCENARIOS_DIR, key, "memories.json")


def results_path(key: str) -> str:
    return os.path.join(SCENARIOS_DIR, key, "results.json")
