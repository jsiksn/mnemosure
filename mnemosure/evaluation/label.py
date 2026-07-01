"""
행동 라벨 — 한 답변이 '사실을 어떻게 다뤘는지'를 한 단어로 정한다.

질문을 축에 미리 배정하지 않는다. 같은 질문이라도 시스템마다 다른 라벨이 나온다.
채점관(judge)이 낸 recall_success/hallucinated + 질문의 모름기대 + 잡무 들먹임 여부를
하나의 라벨로 합친다.

  정확 : 맞는 현재 사실을 답함
  누락 : 기록이 있는데 못 떠올림(잊음) / 모른다고 잘못 답함
  환각 : 틀리거나 옛 사실을 현재처럼 단정 / 근거 없이 지어냄
  잡음 : 안 물어본 불필요한 정보(끝난 운영·환경 잡무 등)를 들먹임
  정직 : 기록에 없는 것을 '모른다'고 정직하게 답함
"""
from __future__ import annotations

# UI 색상 클래스와 1:1로 맞춘 라벨 상수.
ACCURATE = "정확"
OMISSION = "누락"
HALLUCINATION = "환각"
TANGENT = "잡음"
HONEST = "정직"


def behavior_label(
    recall_success: bool,
    hallucinated: bool,
    expect_unknown: bool,
    tangent_volunteered: bool,
) -> str:
    """판정 결과를 하나의 행동 라벨로 변환한다(우선순위 적용)."""
    # 1) 옛/거짓 사실을 우김 — 가장 해로운 실패.
    if hallucinated:
        return HALLUCINATION
    # 2) 기록 없는 질문: 모른다고 정직히 답했으면(=recall_success) 정직, 아니면 누락.
    if expect_unknown:
        return HONEST if recall_success else OMISSION
    # 3) 넓은 질문에 안 물어본 잡무를 들먹임.
    if tangent_volunteered:
        return TANGENT
    # 4) 핵심 사실을 제대로 회상했으면 정확, 아니면 누락(잊음).
    return ACCURATE if recall_success else OMISSION
