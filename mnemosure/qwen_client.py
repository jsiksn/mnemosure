"""
Qwen 호출 래퍼 — 이 프로젝트가 Qwen 모델과 대화하는 '유일한 통로'.

다른 모든 모듈(앞으로 만들 저장·회상·망각·평가)은 여기 함수만 불러 쓴다.
그래서 모델을 바꾸거나 호출 방식을 손볼 일이 생겨도 이 파일만 고치면 된다.

  - chat()   : 글을 보내고 글로 답을 받는다     (qwen3.7-plus / qwen3.5-flash)
  - embed()  : 문장을 의미를 담은 숫자 벡터로 바꾼다 (text-embedding-v4)
  - rerank() : 후보 문장들을 질문과의 관련도 순으로 다시 줄세운다 (qwen3-rerank)

★ 중요한 분기: chat·embed 는 OpenAI 호환 모드(openai SDK)로 호출하지만,
   rerank 는 호환 모드에 라우트가 없어서 '네이티브 엔드포인트'로 직접 호출한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from openai import OpenAI

from . import config


# openai 클라이언트는 한 번만 만들어 재사용한다(호출마다 새로 만들면 낭비).
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.get_api_key(), base_url=config.BASE_URL)
    return _client


# --- 토큰 사용량 집계 (모델별 누적; 데모 사전계산 때 소비량 모니터링용) -----------
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
    model   : 기본은 메인 두뇌(qwen3.7-plus). 가벼운 작업은 config.MODEL_FLASH 로 지정.
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
# 2) embed — 문장 → 숫자 벡터(1024개)
# ---------------------------------------------------------------------------
def embed(texts, model: str = config.MODEL_EMBED) -> list[list[float]]:
    """
    문장을 '의미를 담은 숫자 벡터'로 바꾼다. 나중에 비슷한 기억을 찾는 재료가 된다.

    texts: 문장 하나(str) 또는 여러 개(list[str]).
    반환 : 항상 '벡터들의 리스트'. (문장 하나만 줘도 [벡터] 형태로 돌려준다)
    """
    if isinstance(texts, str):
        texts = [texts]
    resp = _get_client().embeddings.create(model=model, input=texts)
    if resp.usage:
        _track(model, resp.usage.total_tokens)
    return [item.embedding for item in resp.data]


# ---------------------------------------------------------------------------
# 3) rerank — 후보들을 관련도 순으로 재정렬 (★ 네이티브 엔드포인트 직접 호출)
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

    ★ 이 기능은 OpenAI 호환 모드에 없어서, 네이티브 엔드포인트로 직접 HTTP 호출한다.
    """
    payload = {
        "model": model,
        "input": {"query": query, "documents": documents},
        "parameters": {
            "return_documents": True,
            "top_n": top_n if top_n is not None else len(documents),
        },
    }
    headers = {
        "Authorization": f"Bearer {config.get_api_key()}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(config.RERANK_URL, json=payload, headers=headers, timeout=30.0)
    resp.raise_for_status()  # 4xx/5xx 면 여기서 에러를 일으켜 호출부가 알게 한다.
    data = resp.json()
    _track(model, data.get("usage", {}).get("total_tokens", 0))

    hits: list[RerankHit] = []
    for r in data["output"]["results"]:
        doc = r.get("document", {})
        text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
        hits.append(RerankHit(index=r["index"], score=r["relevance_score"], document=text))
    return hits
