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
#
# 무료 모드(MNEMOSURE_FREE=1): 크레딧 없이 쓰도록 brain·flash 기본값을 OpenRouter의
# 무료(:free) 모델로 바꾼다. 개별 MNEMOSURE_MODEL_* 지정은 여전히 그보다 우선한다.
# ★ 무료 모델은 하루 요청 수 제한(크레딧 미구매 계정 기준 50회/일)이 있고, 목록이
#   수시로 바뀐다 — 기본값이 사라지면 https://openrouter.ai/models?q=free 에서 골라
#   MNEMOSURE_MODEL_BRAIN / _FLASH 로 지정한다.
FREE_MODE = os.environ.get("MNEMOSURE_FREE", "").lower() in ("1", "true", "on", "yes")

_BRAIN_DEFAULT = "minimax/minimax-m3:free" if FREE_MODE else "qwen/qwen3.7-plus"
_FLASH_DEFAULT = "nvidia/nemotron-3.5-lightning:free" if FREE_MODE else "qwen/qwen3.7-flash"

MODEL_BRAIN = os.environ.get("MNEMOSURE_MODEL_BRAIN", _BRAIN_DEFAULT)     # 메인 두뇌: 답변 생성
MODEL_FLASH = os.environ.get("MNEMOSURE_MODEL_FLASH", _FLASH_DEFAULT)     # 보조 두뇌: 추출·분류·연결 판정
MODEL_EMBED = os.environ.get("MNEMOSURE_MODEL_EMBED", "baai/bge-m3")      # 색인(EMBED_PROVIDER=api 일 때)
MODEL_RERANK = os.environ.get("MNEMOSURE_MODEL_RERANK", "cohere/rerank-4-fast")  # 재순위(RERANK_PROVIDER=api 일 때)

EMBED_DIM = 1024  # 기본 두 모델(bge-m3 · multilingual-e5-large) 공통 차원


# --- 임베딩 공급 방식 --------------------------------------------------------
# "local": fastembed(ONNX)로 내 컴퓨터에서 계산(★기본). 키·비용 없이 돌고, 대화 원문이
#          밖으로 나가지 않는다. 첫 사용 때 모델 가중치를 Hugging Face에서 한 번 받아 캐시한다.
#          기본 모델은 multilingual-e5-large(1024차원, fastembed 지원 다국어 중 최상).
# "api"  : EMBED_BASE_URL 로 호출(기본 게이트웨이의 bge-m3). GPU가 없어 첫 색인이 느릴 때 쓴다.
#          ★ 두 모델은 벡터가 호환되지 않는다 — local↔api 를 바꾸면
#            `python -m mnemosure.reembed`로 창고를 한 번 재계산한다.
#            (불일치는 창고 메타 검사가 잡아서 안내한다)
EMBED_PROVIDER = os.environ.get("MNEMOSURE_EMBED_PROVIDER", "local").lower()
MODEL_EMBED_LOCAL = os.environ.get("MNEMOSURE_MODEL_EMBED_LOCAL", "intfloat/multilingual-e5-large")


# --- e5 계열 접두어 (기본 끔 — 실측에서 손해였다) -----------------------------
# e5 계열은 질문 앞에 "query: ", 문서 앞에 "passage: " 를 붙여 훈련된 모델이고, 모델 문서도
# 그렇게 쓰라고 한다. 그래서 붙여 보고 같은 자료로 맞대봤는데 **회수가 나빠졌다.**
#   연구노트 1,503조각 · 질문 103개, 정답 회수율 (접두어 없음 → 붙임)
#     상위  6개  72.8% → 66.0%   (-6.8%p)
#     상위 40개  85.4% → 81.6%   (-3.9%p)
#     정답 순위 75%지점  9위 → 20위
# 여섯 개 후보 수 전부에서 나빠졌으므로 기본은 끈다. fastembed 가 이미 붙이는 것도 아니다
# (e5 는 PooledEmbedding 으로 처리되고 접두어 전처리가 없다) — 중복이 아니라 진짜 손해다.
#
# 단, 위 측정의 '질문'은 결론 카드의 제목·요약이라 서술문에 가깝다. 실제 회상 질문은
# 의문문이므로 다른 결과가 나올 수 있다. 자기 문항으로 재보고 싶으면 켤 수 있게 남겨 둔다:
#   MNEMOSURE_E5_PREFIX=on
# ★ 켜면 벡터가 달라져 창고가 섞이면 안 되므로, 켠 창고는 모델 id에 표시를 단다.
_E5_PREFIX_SWITCH = os.environ.get("MNEMOSURE_E5_PREFIX", "off").lower()


def e5_prefix_active() -> bool:
    """지금 설정에서 e5 접두어를 붙이는가. 기본은 끔(실측에서 회수가 나빠졌다)."""
    if EMBED_PROVIDER != "local":
        return False        # 게이트웨이 기본(bge-m3)은 접두어를 쓰지 않는다
    return _E5_PREFIX_SWITCH in ("on", "1", "true", "yes")


def embed_model_id() -> str:
    """현재 설정이 실제로 쓰는 임베딩 모델 id. 창고 메타 기록·호환 검사용.

    접두어를 붙이면 같은 모델이라도 벡터 공간이 달라지므로 id에 표시를 남긴다."""
    if EMBED_PROVIDER != "local":
        return MODEL_EMBED
    return MODEL_EMBED_LOCAL + ("+e5prefix" if e5_prefix_active() else "")


def embed_base_model(model_id: str) -> str:
    """창고에 기록된 id에서 접두어 표시를 떼어 낸 순수 모델명."""
    return (model_id or "").split("+e5prefix")[0]


def embed_models_compatible(a: str, b: str) -> bool:
    """두 임베딩 모델 id가 같은 벡터 공간인지(대소문자·게이트웨이 접두 차이는 무시).
    예: 'baai/bge-m3'(API)와 'BAAI/bge-m3'(로컬)는 같은 모델이다."""
    norm = lambda s: (s or "").strip().lower()
    return norm(a) == norm(b)


# --- 재순위 공급 방식 --------------------------------------------------------
# "local": fastembed 교차인코더로 내 컴퓨터에서 계산(★기본). 키가 필요 없다.
#          기본 모델은 jina-reranker-v2-base-multilingual(한국어 포함 다국어).
#          ★ 이 모델은 로짓(음수 가능)을 내므로 시그모이드로 0~1로 옮겨서 쓴다 —
#            게이트 문턱(RERANK_FLOOR)이 api 쪽과 같은 척도가 되게 하기 위함.
# "api"  : BASE_URL 호스트의 /rerank 를 직접 호출(Cohere 관례 형식).
#          ★ 일반 로컬 추론 서버는 이 라우트를 내주지 않는다 — BASE_URL 을 그런 서버로
#            바꿀 때는 재순위를 local 로 두거나 껐다(MNEMOSURE_RERANK=off).
RERANK_PROVIDER = os.environ.get("MNEMOSURE_RERANK_PROVIDER", "local").lower()
MODEL_RERANK_LOCAL = os.environ.get(
    "MNEMOSURE_MODEL_RERANK_LOCAL", "jinaai/jina-reranker-v2-base-multilingual"
)


def rerank_model_id() -> str:
    """현재 설정이 실제로 쓰는 재순위 모델 id."""
    return MODEL_RERANK_LOCAL if RERANK_PROVIDER == "local" else MODEL_RERANK


# --- 로컬 계산 가속 (EMBED_PROVIDER / RERANK_PROVIDER 가 local 일 때만) --------
# fastembed 는 기본이 CPU다. GPU가 있으면 켜야 실제로 빨라진다.
#   MNEMOSURE_LOCAL_CUDA=1                 CUDA 사용(onnxruntime-gpu 설치 필요)
#   MNEMOSURE_LOCAL_DEVICE_IDS=0,1         쓸 GPU 번호
#   MNEMOSURE_LOCAL_THREADS=8              CPU 스레드 수(GPU가 없을 때 이걸 올리면 낫다)
# ROCm(AMD)·DirectML 등은 표준 onnxruntime 에 없으므로, 그런 장비는 임베딩만 로컬 서버로
# 보내는 편이 낫다(EMBED_PROVIDER=api + MNEMOSURE_EMBED_BASE_URL).
LOCAL_CUDA = os.environ.get("MNEMOSURE_LOCAL_CUDA", "").lower() in ("1", "true", "on", "yes")
_ids = os.environ.get("MNEMOSURE_LOCAL_DEVICE_IDS", "").strip()
LOCAL_DEVICE_IDS = [int(x) for x in _ids.split(",") if x.strip().isdigit()] or None
_th = os.environ.get("MNEMOSURE_LOCAL_THREADS", "").strip()
LOCAL_THREADS = int(_th) if _th.isdigit() else None


def local_compute_kwargs() -> dict:
    """fastembed 생성자에 넘길 가속 설정. 지정 안 한 값은 넘기지 않아 fastembed 기본을 따른다."""
    kw = {}
    if LOCAL_CUDA:
        kw["cuda"] = True
        if LOCAL_DEVICE_IDS:
            kw["device_ids"] = LOCAL_DEVICE_IDS
    if LOCAL_THREADS:
        kw["threads"] = LOCAL_THREADS
    return kw


# --- rerank 사용 여부 --------------------------------------------------------
# "on" : 회수 후보를 rerank 모델로 재정렬(기본, 권장).
# "off": rerank 호출 없이 1차 유사도(코사인) 점수로 순위·모름 판정. 비용 절감용.
RERANK_ENABLED = os.environ.get("MNEMOSURE_RERANK", "on").lower() != "off"
