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
# 시나리오 2 (모바일 앱 UI/UX 개편) 정답표 — 위와 같은 채점 규약(정확성만).
# 주식봇과 동일 원칙: 암묵적 대체(파랑->초록, 3단계->1화면), 진짜 공백(다크모드 팔레트)=모름,
# 곁다리 잡무(아이콘 파일명·피그마 정리)는 넓은 질문에 먼저 들먹이면 잡음.
# ===========================================================================

# 세션 곡선용: 초기에 생긴 '이유·대체 역사'(핸드오프가 시간 지나며 버리는 것)
UIUX_CURVE_RECALL = [
    {"id": "UC_R1", "question": "메인 컬러를 왜 바꿨어?",
     "must_include": ["파랑이 대비가 낮아 접근성 기준을 통과하지 못해서"]},
    {"id": "UC_R2", "question": "온보딩을 바꾼 적 있어? 어떻게, 왜?",
     "must_include": ["3단계 튜토리얼에서 1화면으로 바꿨고, 이탈률이 높아서"]},
    {"id": "UC_R3", "question": "메인 컬러가 처음엔 뭐였지?",
     "must_include": ["처음엔 파랑이었다"]},
    {"id": "UC_R4", "question": "온보딩이 처음엔 어땠지?",
     "must_include": ["처음엔 3단계 튜토리얼이었다"]},
]


# 통합 비교표용 평평한 질문 풀 (축에 미리 배정하지 않고 답변에 나타난 행동을 라벨링)
UIUX_QA_POOL = [
    {"id": "UP1",
     "question": "메인 컬러가 파랑 맞지?",
     "must_include": ["아니다, 지금은 초록이다"],
     "must_not_assert": ["현재 메인 컬러가 파랑이다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "UP2",
     "question": "메인 컬러를 왜 바꿨어?",
     "must_include": ["파랑이 배경 대비가 낮아 접근성 기준(WCAG)을 통과하지 못해서"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
    {"id": "UP3",
     "question": "온보딩이 처음부터 1화면이었어? 변천을 알려줘.",
     "must_include": ["처음엔 3단계 튜토리얼이었다가 건너뛰기 가능한 1화면으로 바뀌었다"],
     "must_not_assert": ["온보딩이 원래부터 1화면이었다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "UP4",
     "question": "온보딩 지금도 3단계 튜토리얼이지?",
     "must_include": ["아니다, 지금은 건너뛰기 가능한 1화면이다"],
     "must_not_assert": ["현재 온보딩이 3단계 튜토리얼이다"],
     "expect_unknown": False, "tangent_keywords": []},
    {"id": "UP5",
     "question": "지금까지 이 앱 개편에서 내린 중요한 결정들을 요약해줘.",
     "must_include": ["메인 컬러(초록), 온보딩(1화면), 타깃(20~30대), 주요 화면(홈·검색·마이), 폰트, 앱 이름 등 핵심 결정을 폭넓게 담았다(파일명·피그마 정리 같은 잡무는 제외)"],
     "must_not_assert": [], "expect_unknown": False,
     "tangent_keywords": ["아이콘", "파일명", "ic_", "피그마"]},  # '페이지'는 '마이페이지'와 부분일치 오탐이라 제외('피그마'가 곁다리 누출을 잡음)
    {"id": "UP6",
     "question": "다크모드 색상 팔레트는 어떻게 정했지?",
     "must_include": [], "must_not_assert": ["구체적인 다크모드 팔레트를 사실처럼 제시"],
     "expect_unknown": True, "tangent_keywords": []},
    {"id": "UP7",
     "question": "타깃 사용자층이 누구였지?",
     "must_include": ["20~30대"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
    {"id": "UP8",
     "question": "아이콘 파일명은 어떻게 정리했지?",
     "must_include": ["ic_기능명 규칙으로 통일했다"],
     "must_not_assert": [], "expect_unknown": False, "tangent_keywords": []},
]
