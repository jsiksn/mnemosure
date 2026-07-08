"""
모델 호출 래퍼 — 이 프로젝트가 LLM과 대화하는 '유일한 통로'.

다른 모든 모듈(저장·회상·망각·평가)은 여기 함수만 불러 쓴다.
그래서 모델·게이트웨이를 바꿔도 이 파일(과 config)만 고치면 된다.

  - chat()   : 글을 보내고 글로 답을 받는다
  - embed()  : 문장을 의미를 담은 숫자 벡터로 바꾼다 (API 또는 로컬 fastembed)
  - rerank() : 후보 문장들을 질문과의 관련도 순으로 다시 줄세운다

접속처는 기본 OpenRouter(OpenAI 호환). chat·embed는 openai SDK로,
rerank는 OpenAI SDK에 라우트가 없어 같은 호스트의 /rerank 를 직접 호출한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from openai import OpenAI

from . import config


# openai 클라이언트는 한 번만 만들어 재사용한다(호출마다 새로 만들면 낭비).
_client: OpenAI | None = None
_embed_client: OpenAI | None = None
_local_embedder = None  # fastembed 인스턴스 (EMBED_PROVIDER=local일 때만)

# OpenRouter가 권장하는 앱 식별 헤더(집계용). 다른 게이트웨이는 무시한다.
_APP_HEADERS = {
    "HTTP-Referer": "https://github.com/jsiksn/mnemosure",
    "X-Title": "mnemosure",
}


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.get_api_key(),
            base_url=config.BASE_URL,
            default_headers=_APP_HEADERS,
        )
    return _client


def _get_embed_client() -> OpenAI:
    """임베딩용 클라이언트. 임베딩만 다른 곳/키로 보내는 분리 설정이 가능해서 따로 둔다."""
    global _embed_client
    if _embed_client is None:
        same_endpoint = (
            config.EMBED_BASE_URL == config.BASE_URL
            and not os.environ.get("MNEMOSURE_EMBED_API_KEY")
        )
        if same_endpoint:
            _embed_client = _get_client()
        else:
            _embed_client = OpenAI(
                api_key=config.get_embed_api_key(),
                base_url=config.EMBED_BASE_URL,
                default_headers=_APP_HEADERS,
            )
    return _embed_client


# --- 토큰 사용량 집계 (모델별 누적; 소비량 모니터링용) --------------------------
_usage_by_model: dict[str, int] = {}


def _track(model: str, tokens) -> None:
    _usage_by_model[model] = _usage_by_model.get(model, 0) + int(tokens or 0)


def get_usage() -> dict[str, int]:
    """모델별 누적 토큰 사용량(이 프로세스 시작 이후)."""
    return dict(_usage_by_model)


def reset_usage() -> None:
    _usage_by_model.clear()


# ---------------------------------------------------------------------------
# 1) chat — 글 → 글
# ---------------------------------------------------------------------------
@dataclass
class ChatResult:
    """chat() 결과 상자: 답 텍스트(text)와 토큰 사용량(usage)을 함께 담는다."""
    text: str
    usage: dict[str, Any]
    model: str


def chat(messages, model: str = config.MODEL_BRAIN, **opts) -> ChatResult:
    """
    글을 보내고 글로 답을 받는다.

    messages: 문자열 하나만 줘도 되고, [{"role": "user", "content": "..."}] 형식도 된다.
    model   : 기본은 메인 두뇌(config.MODEL_BRAIN). 가벼운 작업은 config.MODEL_FLASH 로 지정.
    """
    # 편의: 그냥 문자열을 주면 user 메시지 한 줄로 감싸준다.
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    resp = _get_client().chat.completions.create(
        model=model, messages=messages, **opts
    )
    usage = resp.usage.model_dump() if resp.usage else {}
    _track(model, usage.get("total_tokens", 0))
    return ChatResult(
        text=resp.choices[0].message.content or "",
        usage=usage,
        model=model,
    )


# ---------------------------------------------------------------------------
# 2) embed — 문장 → 숫자 벡터
# ---------------------------------------------------------------------------
def embed(texts, model: str = config.MODEL_EMBED) -> list[list[float]]:
    """
    문장을 '의미를 담은 숫자 벡터'로 바꾼다. 나중에 비슷한 기억을 찾는 재료가 된다.

    texts: 문장 하나(str) 또는 여러 개(list[str]).
    반환 : 항상 '벡터들의 리스트'. (문장 하나만 줘도 [벡터] 형태로 돌려준다)

    공급 방식은 config.EMBED_PROVIDER 를 따른다:
      - "api"  : OpenAI 호환 /embeddings 호출(기본, 기본 모델 bge-m3)
      - "local": fastembed 로 내 컴퓨터에서 계산(선택 설치: pip install "mnemosure[local]",
                 기본 모델 multilingual-e5-large — API 기본과 벡터가 다르므로 전환 시 재임베딩 필요)
    """
    if isinstance(texts, str):
        texts = [texts]
    if config.EMBED_PROVIDER == "local":
        return _embed_local(texts)
    resp = _get_embed_client().embeddings.create(model=model, input=texts)
    if resp.usage:
        _track(model, resp.usage.total_tokens)
    return [item.embedding for item in resp.data]


def _embed_local(texts: list[str]) -> list[list[float]]:
    """fastembed(ONNX)로 로컬 임베딩. 첫 사용 때 모델을 허깅페이스에서 내려받아 캐시한다."""
    global _local_embedder
    if _local_embedder is None:
        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise RuntimeError(
                'Local embeddings need the optional dependency: pip install "mnemosure[local]"'
            ) from e
        _local_embedder = TextEmbedding(model_name=config.MODEL_EMBED_LOCAL)
    return [vec.tolist() for vec in _local_embedder.embed(texts)]


# ---------------------------------------------------------------------------
# 3) rerank — 후보들을 관련도 순으로 재정렬 (★ /rerank 직접 호출)
# ---------------------------------------------------------------------------
@dataclass
class RerankHit:
    """rerank() 결과 한 줄: 원래 몇 번째 후보였는지(index)·관련도 점수(score)·문서 텍스트."""
    index: int
    score: float
    document: str


def rerank(
    query: str,
    documents: list[str],
    top_n: int | None = None,
    model: str = config.MODEL_RERANK,
) -> list[RerankHit]:
    """
    후보 문장들을 'query 와 얼마나 관련 있나' 순(점수 높은 순)으로 다시 줄세운다.

    ★ OpenAI SDK에는 rerank가 없어서, base_url 호스트의 /rerank 를 직접 HTTP 호출한다.
      (Cohere 관례 형식: {model, query, documents, top_n} → results[{index, relevance_score, ...}])
    """
    payload = {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": top_n if top_n is not None else len(documents),
    }
    headers = {
        "Authorization": f"Bearer {config.get_api_key()}",
        "Content-Type": "application/json",
        **_APP_HEADERS,
    }
    url = config.BASE_URL.rstrip("/") + "/rerank"
    resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
    resp.raise_for_status()  # 4xx/5xx 면 여기서 에러를 일으켜 호출부가 알게 한다.
    data = resp.json()
    usage = data.get("usage") or {}
    _track(model, usage.get("total_tokens", 0))

    hits: list[RerankHit] = []
    for r in data.get("results", []):
        idx = r["index"]
        score = r.get("relevance_score", r.get("score", 0.0))
        doc = r.get("document")
        if isinstance(doc, dict):
            text = doc.get("text", "")
        elif isinstance(doc, str):
            text = doc
        else:
            text = documents[idx] if 0 <= idx < len(documents) else ""
        hits.append(RerankHit(index=idx, score=score, document=text))
    return hits
