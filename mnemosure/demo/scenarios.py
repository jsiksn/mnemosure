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
    QA_POOL,
    UIUX_CURVE_RECALL,
    UIUX_QA_POOL,
)
from .sample_sessions import (
    CURVE_SESSIONS,
    EVAL_SESSIONS,
    UIUX_CURVE_SESSIONS,
    UIUX_EVAL_SESSIONS,
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
        "key": "uiux",
        "title": "모바일 앱 UI/UX 개편",
        "eval_sessions": UIUX_EVAL_SESSIONS,
        "curve_sessions": UIUX_CURVE_SESSIONS,
        "qa_pool": UIUX_QA_POOL,
        "curve_recall": UIUX_CURVE_RECALL,
        "sample_questions": [
            "메인 컬러가 파랑 맞지?",
            "메인 컬러를 왜 바꿨어?",
            "온보딩이 지금도 3단계 튜토리얼이지?",
            "지금까지 중요한 결정들 요약해줘",
            "다크모드 색상 팔레트는 어떻게 정했지?",
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
