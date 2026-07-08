"""
설정 단일 출처(single source of truth).

다른 모든 모듈은 모델명·엔드포인트·API 키를 '오직 여기서만' 가져다 쓴다.
값을 바꿀 일이 생기면 이 파일 한 곳만 고치면 전체에 반영된다.

0.3.0: 접속처가 OpenRouter(기본)로 바뀌었다 — 키 하나로 chat·임베딩·rerank를
어떤 모델이든 골라 쓴다. OpenAI 호환 엔드포인트라면 MNEMOSURE_BASE_URL로
다른 곳(자체 게이트웨이 등)을 지정할 수도 있다.
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
# 키는 환경변수(또는 .env)에서만 읽는다. 코드에 절대 하드코딩하지 않는다(공개 레포).
def get_api_key() -> str:
    """API 키를 환경변수(또는 .env)에서 읽어 반환한다. 없으면 친절히 안내하고 멈춘다."""
    key = os.environ.get("MNEMOSURE_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "API key not set. mnemosure talks to models via OpenRouter (default).\n"
            "  1) Create a key at https://openrouter.ai/keys\n"
            "  2) Put it in a .env file at the project root:  OPENROUTER_API_KEY=sk-or-...\n"
            "     (or export it:  export OPENROUTER_API_KEY=\"sk-or-...\")\n"
            "  Using a different OpenAI-compatible gateway? Set MNEMOSURE_BASE_URL and MNEMOSURE_API_KEY."
        )
    return key


# --- 엔드포인트 ------------------------------------------------------------
# OpenAI 호환 모드: Chat·Embedding 용. openai SDK의 base_url 로 사용한다.
# rerank는 같은 호스트의 /rerank 라우트를 직접 호출한다(OpenAI SDK에 rerank가 없어서).
BASE_URL = os.environ.get("MNEMOSURE_BASE_URL", "https://openrouter.ai/api/v1")

# 임베딩만 다른 곳/키로 보내고 싶을 때(선택). 지정 없으면 chat과 같은 곳을 쓴다.
EMBED_BASE_URL = os.environ.get("MNEMOSURE_EMBED_BASE_URL", BASE_URL)


def get_embed_api_key() -> str:
    """임베딩용 키(선택 분리). 지정 없으면 본 키를 그대로 쓴다."""
    return os.environ.get("MNEMOSURE_EMBED_API_KEY") or get_api_key()


# --- 모델명 ----------------------------------------------------------------
# 기본값은 아래 그대로. 바꾸고 싶으면 env(또는 .env)에 MNEMOSURE_MODEL_* 를 넣으면 그 값이 쓰인다.
# 자동 전환은 하지 않는다(원치 않은 모델로 바뀌는 걸 방지) — 오직 사용자가 env로 수동 지정.
MODEL_BRAIN = os.environ.get("MNEMOSURE_MODEL_BRAIN", "qwen/qwen3.7-plus")            # 메인 두뇌: 답변 생성
MODEL_FLASH = os.environ.get("MNEMOSURE_MODEL_FLASH", "qwen/qwen3.5-flash-02-23")     # 보조 두뇌: 추출·분류·연결 판정
MODEL_EMBED = os.environ.get("MNEMOSURE_MODEL_EMBED", "baai/bge-m3")                  # 색인: 기억을 벡터로 저장·의미 검색
MODEL_RERANK = os.environ.get("MNEMOSURE_MODEL_RERANK", "cohere/rerank-4-fast")       # 정밀 선별: 회수 후보 재순위

EMBED_DIM = 1024  # bge-m3 고정 차원


# --- 임베딩 공급 방식 --------------------------------------------------------
# "api"  : 위 EMBED_BASE_URL 로 호출(기본).
# "local": fastembed(선택 설치, `pip install "mnemosure[local]"`)로 내 컴퓨터에서 계산.
#          기본 로컬 모델은 multilingual-e5-large(1024차원, fastembed 지원 다국어 중 최상).
#          ★ API 기본(bge-m3)과는 다른 모델이라 벡터가 호환되지 않는다 —
#            api↔local 을 바꾸면 `python -m mnemosure.reembed`로 창고를 한 번 재계산한다.
#            (불일치는 창고 메타 검사가 잡아서 안내한다)
EMBED_PROVIDER = os.environ.get("MNEMOSURE_EMBED_PROVIDER", "api").lower()
MODEL_EMBED_LOCAL = os.environ.get("MNEMOSURE_MODEL_EMBED_LOCAL", "intfloat/multilingual-e5-large")


def embed_model_id() -> str:
    """현재 설정이 실제로 쓰는 임베딩 모델 id. 창고 메타 기록·호환 검사용."""
    return MODEL_EMBED_LOCAL if EMBED_PROVIDER == "local" else MODEL_EMBED


def embed_models_compatible(a: str, b: str) -> bool:
    """두 임베딩 모델 id가 같은 벡터 공간인지(대소문자·게이트웨이 접두 차이는 무시).
    예: 'baai/bge-m3'(API)와 'BAAI/bge-m3'(로컬)는 같은 모델이다."""
    norm = lambda s: (s or "").strip().lower()
    return norm(a) == norm(b)


# --- rerank 사용 여부 --------------------------------------------------------
# "on" : 회수 후보를 rerank 모델로 재정렬(기본, 권장).
# "off": rerank 호출 없이 1차 유사도(코사인) 점수로 순위·모름 판정. 비용 절감용.
RERANK_ENABLED = os.environ.get("MNEMOSURE_RERANK", "on").lower() != "off"
