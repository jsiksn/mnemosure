"""
설정 단일 출처(single source of truth).

다른 모든 모듈은 모델명·엔드포인트·API 키를 '오직 여기서만' 가져다 쓴다.
값을 바꿀 일이 생기면 이 파일 한 곳만 고치면 전체에 반영된다.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

# 프로젝트 루트의 .env 를 환경변수로 로드한다(있을 때만). cwd와 무관하게 늘 같은 .env를 본다.
# - 로컬·MCP: .env 파일에 키를 둔다(.gitignore로 커밋 안 됨). 에이전트가 깨끗한 env로 서버를 띄워도 동작.
# - 배포: 클라우드가 실제 환경변수를 주입하면 그게 우선한다(load_dotenv override=False 기본).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


# --- API 키 ---------------------------------------------------------------
# 키는 환경변수(또는 .env)에서만 읽는다. 코드에 절대 하드코딩하지 않는다(공개 레포 제출).
def get_api_key() -> str:
    """DASHSCOPE_API_KEY를 환경변수(또는 .env)에서 읽어 반환한다. 없으면 친절히 안내하고 멈춘다."""
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY가 설정되어 있지 않습니다. 아래 중 하나로 설정하세요.\n"
            "  - (권장) 프로젝트 루트에 .env 파일:  DASHSCOPE_API_KEY=발급받은_키\n"
            "  - 또는 셸 환경변수:  export DASHSCOPE_API_KEY=\"발급받은_키\"  (~/.zshenv 등)\n"
            "  - 확인: `echo ${#DASHSCOPE_API_KEY}` 가 0보다 큰 숫자를 출력하거나, .env 에 키가 있어야 합니다."
        )
    return key


# --- 엔드포인트 ------------------------------------------------------------
# OpenAI 호환 모드: Chat·Embedding 용. openai SDK의 base_url 로 사용한다.
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# 네이티브 모드: Rerank 전용. (OpenAI 호환 모드에는 rerank 라우트가 없어 직접 호출한다)
RERANK_URL = (
    "https://dashscope-intl.aliyuncs.com"
    "/api/v1/services/rerank/text-rerank/text-rerank"
)


# --- 모델명 ----------------------------------------------------------------
# 기본값은 아래 그대로. 바꾸고 싶으면 env(또는 .env)에 MNEMOSURE_MODEL_* 를 넣으면 그 값이 쓰인다.
# 자동 전환은 하지 않는다(원치 않은 모델로 바뀌는 걸 방지) — 오직 사용자가 env로 수동 지정.
MODEL_BRAIN = os.environ.get("MNEMOSURE_MODEL_BRAIN", "qwen3.7-plus-2026-05-26")   # 메인 두뇌: 답변 생성
MODEL_FLASH = os.environ.get("MNEMOSURE_MODEL_FLASH", "qwen3.5-flash")             # 보조 두뇌: 추출·채점·분류
MODEL_EMBED = os.environ.get("MNEMOSURE_MODEL_EMBED", "text-embedding-v4")         # 색인: 기억을 벡터로 저장·의미 검색
MODEL_RERANK = os.environ.get("MNEMOSURE_MODEL_RERANK", "qwen3-rerank")            # 정밀 선별: 회수 후보 재순위(네이티브)

EMBED_DIM = 1024  # text-embedding-v4 기본 차원 (연결 테스트에서 확인됨)
