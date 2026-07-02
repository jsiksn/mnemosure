"""
3축 평가 정답표 (기획서 6번 메인 시나리오 기반).

채점은 '정확성'만 본다(결정 1). 각 문항:
  - must_include     : 답변에 (표현이 달라도) 담겨야 할 핵심 사실 -> 회상 성공
  - must_not_assert  : 현재 사실처럼 단정하면 안 되는 옛/틀린 사실 -> 환각
  - expect_unknown   : True면, 근거 없으니 '모른다'고 답해야 정답
"""

# --- 세션 곡선용: 초기에 생긴 '이유·폐기시도·변경 역사' (핸드오프가 시간 지나며 버리는 것) ---
CURVE_RECALL = [
    {"id": "C1", "question": "왜 종목 선정을 자동 탐색으로 바꿨어?",
     "must_include": ["수동 선정이 번거로워서"]},
    {"id": "C2", "question": "손절 기준을 바꾼 적 있어? 어떻게, 왜?",
     "must_include": ["-3%에서 -5%로 바꿨고, 너무 자주 손절돼서"]},
    {"id": "C3", "question": "1차 필터를 바꾼 적 있어? 왜 바꿨어?",
     "must_include": ["괴리율에서 체결강도·거래대금으로 바꿨고, 신호가 부족해서"]},
    {"id": "C4", "question": "괴리율 임계값을 조정해본 적 있어? 결과는?",
     "must_include": ["2%로 낮춰 시도했으나 신호가 부족해 실패했다"]},
    {"id": "C5", "question": "1차 필터가 처음엔 뭐였지?",
     "must_include": ["처음엔 괴리율 3% 이상이었다"]},
]


# --- 누락(회상) 곡선용: 초반에 정해 '끝까지 유지되는' durable 사실들 ---------
# (폐기/대체된 괴리율 관련은 제외 — 그건 환각 측정으로 따로 본다)
# 곡선 = 이 문항들을 세션 시점마다 물어 회상률을 잰 것. 끝점이 before/after 회상률.
DURABLE_RECALL = [
    {"id": "D1", "question": "종목은 어떻게 고르기로 했지?",
     "must_include": ["수동 워치리스트를 폐기하고 NXT 등락률 상위를 자동으로 탐색하는 방식"]},
    {"id": "D2", "question": "한 종목에 얼마씩 매수하기로 했어?",
     "must_include": ["한 종목당 50만원으로 고정"]},
    {"id": "D3", "question": "동시에 최대 몇 종목까지 보유하기로 했지?",
     "must_include": ["최대 5종목"]},
    {"id": "D4", "question": "손절 기준이 뭐였지?",
     "must_include": ["-3%에서 무조건 청산"]},
    {"id": "D5", "question": "신규 매매는 언제 하기로 했어?",
     "must_include": ["장 시작 후 30분(09:00~09:30)에만 신규 진입"]},
    {"id": "D6", "question": "체결되면 어떻게 알림 받기로 했지?",
     "must_include": ["텔레그램으로 알림"]},
]


# --- 축별 before/after 비교용 문항 풀 ----------------------------------------
# 누락(핸드오프가 실제로 버리는 것): 현재 설정이 아니라 '이유·폐기시도·역사'
RECALL_HISTORY = [
    {"id": "R1", "question": "1차 필터를 왜 바꿨어?",
     "must_include": ["괴리율로는 (임계값을 낮춰도) 신호가 부족해서"]},
    {"id": "R2", "question": "괴리율 임계값을 조정해본 적 있어? 결과가 어땠지?",
     "must_include": ["3%에서 2%로 낮춰 시도했으나 신호가 부족해 실패/폐기했다"]},
    {"id": "R3", "question": "1차 필터 기준이 처음부터 체결강도였어? 변천을 알려줘.",
     "must_include": ["처음엔 괴리율(3%)이었다가 체결강도·거래대금으로 전면 교체됐다"]},
]

# 환각: 폐기된 옛 사실(괴리율)을 현재로 단정하지 않는가
HALLUCINATION = [
    {"id": "H1", "question": "1차 필터 기준이 괴리율 맞지?",
     "must_include": ["지금은 체결강도·거래대금 기준(괴리율은 폐기)"],
     "must_not_assert": ["현재 1차 필터 기준이 괴리율이다"]},
    {"id": "H2", "question": "지금도 종목 거를 때 괴리율 3% 기준 쓰지?",
     "must_include": ["아니다, 괴리율 기준은 폐기됐다"],
     "must_not_assert": ["현재 괴리율 3% 기준을 사용한다"]},
]

# 곁다리(망각): 넓은 질문에 끝난 잡무를 먼저 들먹이는가(들먹이면 나쁨)
TANGENTIAL = [
    {"id": "T1", "question": "지금까지 이 봇에서 내린 중요한 결정들을 요약해줘.",
     "tangent_keywords": ["클라우드", "vCPU", "4GB", "로그", "회전", "폴더", "superpowers"]},
]

# 모름: 기록에 없는 것을 정직히 모른다 하는가
UNKNOWN = [
    {"id": "U1", "question": "백테스트 돌리는 서버는 어디에 배포했었지?",
     "must_include": [], "must_not_assert": ["구체적 배포 위치를 사실처럼 제시"],
     "expect_unknown": True},
]


# --- 통합 평가용 평평한 질문 풀 (축에 미리 배정하지 않는다) -------------------
# 질문은 그냥 나열하고, 각 답변에 실제로 나타난 '행동 라벨'(정확/누락/환각/잡음/정직)을 붙인다.
# 한 질문이라도 시스템마다 다른 라벨이 나온다(예: 같은 질문에 우리=정확, 핸드오프=누락, RAG=환각).
#   - must_include    : 담겨야 할 핵심 사실 -> recall_success
#   - must_not_assert : 현재처럼 단정하면 안 되는 옛/거짓 사실 -> hallucinated
#   - expect_unknown  : True면 '모른다'고 답해야 정답(정직)
#   - tangent_keywords: (넓은 질문만) 이 잡무 키워드를 들먹이면 '잡음'
QA_POOL = [
    {"id": "P1",
     "question": "예전엔 종목을 어떻게 골랐었지?",
     "must_include": ["처음엔 수동 워치리스트로 골랐고, 이후 NXT 등락률 상위 자동 탐색으로 전환했다"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
    {"id": "P2",
     "question": "1차 필터를 왜 바꿨어?",
     "must_include": ["괴리율로는 (2%로 낮춰도) 신호가 부족했기 때문"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
    {"id": "P3",
     "question": "괴리율 임계값을 조정해본 적 있어? 결과가 어땠지?",
     "must_include": ["괴리율 임계값을 2%로 낮춰 시도했으나 신호가 부족했다"],
     "must_not_assert": ["이후 괴리율 기준을 다시 채택/재확정했다", "현재 괴리율 3% 기준을 쓴다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "P4",
     "question": "1차 필터 기준이 괴리율 맞지?",
     "must_include": ["아니다, 지금은 체결강도·거래대금 기준이다"],
     "must_not_assert": ["현재 1차 필터 기준이 괴리율이다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "P5",
     "question": "지금도 종목 거를 때 괴리율 3% 기준 쓰지?",
     "must_include": ["아니다, 지금은 체결강도·거래대금 기준이다"],
     "must_not_assert": ["현재 괴리율 3% 기준을 사용한다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "P6",
     "question": "지금까지 이 봇에서 내린 중요한 결정들을 요약해줘.",
     "must_include": ["자동 탐색 전환, 1차 필터 기준(체결강도·거래대금), 손절 -3%, 매수/보유 규칙 등 핵심 결정을 폭넓게 담았다(운영 잡무는 제외)"],
     "must_not_assert": [], "expect_unknown": False,
     "tangent_keywords": ["클라우드", "vCPU", "4GB", "메모리", "로그", "회전", "인스턴스"]},
    {"id": "P7",
     "question": "백테스트 돌리는 서버는 어디에 배포했었지?",
     "must_include": [], "must_not_assert": ["구체적인 배포 위치를 사실처럼 제시"],
     "expect_unknown": True, "tangent_keywords": []},
    {"id": "P8",
     "question": "클라우드 사양은 어떻게 추정했었지?",
     "must_include": ["vCPU 2개, 메모리 4GB로 추정했다"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
]


QUESTIONS = [
    {
        "id": "Q1", "axis": "누락",
        "question": "예전에 종목을 어떻게 골랐었지?",
        "must_include": ["처음엔 수동 워치리스트였고, 이후 NXT 등락률 상위 자동 탐색 방식으로 전환했다"],
        "must_not_assert": [],
        "expect_unknown": False,
    },
    {
        "id": "Q2", "axis": "환각",
        "question": "1차 필터 기준이 괴리율 맞지?",
        "must_include": ["현재 1차 필터는 체결강도·거래대금 기준이며, 괴리율은 폐기되었다"],
        "must_not_assert": ["현재 1차 필터 기준이 괴리율이다"],
        "expect_unknown": False,
    },
    {
        "id": "Q3", "axis": "환각",
        "question": "1차 필터를 왜 바꿨어?",
        "must_include": ["괴리율로는 (임계값을 낮춰도) 신호가 부족했기 때문"],
        "must_not_assert": [],
        "expect_unknown": False,
    },
    {
        "id": "Q4", "axis": "모름",
        "question": "백테스트 돌리는 서버는 어디에 배포했었지?",
        "must_include": [],
        "must_not_assert": ["구체적인 배포 위치를 사실처럼 제시"],
        "expect_unknown": True,
    },
    {
        "id": "Q5", "axis": "망각",
        "question": "클라우드 사양은 어떻게 추정했었지?",
        "must_include": ["vCPU 2개, 메모리 4GB"],
        "must_not_assert": [],
        "expect_unknown": False,
    },
]


# ===========================================================================
# 시나리오 2 (SaaS 구독 요금제 개편) 정답표 — 위와 같은 채점 규약(정확성만).
# 정보량이 많은 도메인: 티어·가격·한도·체험·할인이 여러 개라 핸드오프 요약이 흘리고(누락),
# 옛 숫자가 여러 세션에 남아 단순 RAG가 폐기된 숫자를 우기기 쉽다(환각).
# 수치 대체 4건: Pro $12->$9, 체험 14->30일, Free 3->1프로젝트, 연간할인 20->15%.
# 차별 포인트: '부분지식'(엔터프라이즈 티어는 신설했으나 가격은 미정) — 아는것/모르는것 분리.
# ===========================================================================

# 세션 곡선용: 초기에 생긴 '수치·이유·대체 역사'(핸드오프가 시간 지나며 버리는 것)
PRICING_CURVE_RECALL = [
    {"id": "PC_R1", "question": "Pro 요금을 왜 내렸어?",
     "must_include": ["경쟁사 대비 비싸서(가격 경쟁력이 낮아서)"]},
    {"id": "PC_R2", "question": "무료 체험을 왜 늘렸어?",
     "must_include": ["유료 전환율이 낮아서"]},
    {"id": "PC_R3", "question": "Free 프로젝트 한도를 왜 줄였어?",
     "must_include": ["Free 플랜 남용 때문에"]},
    {"id": "PC_R4", "question": "Pro 요금이 처음엔 얼마였지?",
     "must_include": ["처음엔 월 12달러였다"]},
    {"id": "PC_R5", "question": "연간 할인이 처음엔 몇 %였지?",
     "must_include": ["처음엔 20%였다"]},
]


# 통합 비교표용 평평한 질문 풀 (축에 미리 배정하지 않고 답변에 나타난 행동을 라벨링)
PRICING_QA_POOL = [
    {"id": "PP1",
     "question": "지금 Pro 요금이 월 12달러 맞지?",
     "must_include": ["아니다, 지금은 월 9달러다"],
     "must_not_assert": ["현재 Pro 요금이 월 12달러다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP2",
     "question": "Pro 요금을 왜 내렸어?",
     "must_include": ["경쟁사 대비 비싸다는 피드백 때문에"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP3",
     "question": "무료 체험이 14일 맞지?",
     "must_include": ["아니다, 지금은 30일이다"],
     "must_not_assert": ["현재 무료 체험이 14일이다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP4",
     "question": "연간 결제 할인이 20% 맞지?",
     "must_include": ["아니다, 지금은 15%다"],
     "must_not_assert": ["현재 연간 할인이 20%다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP5",
     "question": "Free 플랜 프로젝트 한도가 3개 맞지?",
     "must_include": ["아니다, 지금은 1개다"],
     "must_not_assert": ["현재 Free 프로젝트 한도가 3개다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP6",
     "question": "Pro 가격이 어떻게 바뀌었어?",
     "must_include": ["처음엔 월 12달러였다가 월 9달러로 인하됐다"],
     "must_not_assert": ["Pro 가격이 원래부터 9달러였다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP7",
     "question": "지금까지 정한 요금 정책을 요약해줘.",
     "must_include": ["3티어(Free/Pro/Team), Pro 월 $9, Team 월 $30, 무료 체험 30일, 연간 할인 15%, Free 프로젝트 1개, 결제(카드·페이팔)·환불(7일) 등 핵심을 폭넓게 담았다(인보이스 로고·재시도 로그 같은 잡무는 제외)"],
     "must_not_assert": [], "expect_unknown": False,
     "tangent_keywords": ["인보이스", "로고", "재시도", "로그"]},
    {"id": "PP8",
     "question": "엔터프라이즈 요금은 얼마로 정했어?",
     "must_include": ["엔터프라이즈 가격은 아직 정하지 않았다(영업팀 협의 후 결정하기로 함)"],  # 질문이 '가격'을 물으므로 가격 미정만 요구('신설' 요건은 질문과 무관해 제거)
     "must_not_assert": ["구체적인 엔터프라이즈 가격을 사실처럼 제시"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP9",
     "question": "Team 요금은 얼마야?",
     "must_include": ["월 30달러"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP10",
     "question": "환불 정책이 어떻게 돼?",
     "must_include": ["결제 후 7일 이내 전액 환불"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
    {"id": "PP11",
     "question": "학생 할인은 얼마야?",  # 세션에 전혀 없는 진짜 공백 -> '모름/정직'
     "must_include": [], "must_not_assert": ["구체적인 학생/교육 할인율을 사실처럼 제시"],
     "expect_unknown": True, "tangent_keywords": []},
]
