"""
6단계 데모 웹 서버 (FastAPI).

라이브로 Qwen을 호출하는 건 /ask(질문 응답)뿐. 기억 창고는 data/memories.json에서 로드만 하고
(재적재 안 함), 무거운 평가/곡선 결과는 data/demo_results.json을 그대로 서빙한다.

실행:  uvicorn mnemosure.demo.server:app --port 8000
      (또는 python scripts/run_demo.py)
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ..memory.recall import recall
from ..memory.storage import DEFAULT_PATH, MemoryStore
from .sample_sessions import EVAL_SESSIONS

# 세션 id -> 사람이 읽을 제목 (출처 표시용)
_SESSION_TITLES = {s["session_id"]: s.get("title", s["session_id"]) for s in EVAL_SESSIONS}

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(ROOT, "data", "demo_results.json")

app = FastAPI(title="Mnemosure Demo")

# 시작 시 라이브 기억 창고를 1회 로드(파일에서). 질문마다 재적재하지 않는다.
_store = MemoryStore(path=DEFAULT_PATH)


class Ask(BaseModel):
    question: str


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "index.html"))


@app.post("/ask")
def ask(body: Ask):
    """질문을 라이브 회상 엔진에 넘겨 근거 기반 답을 돌려준다."""
    r = recall(body.question, _store)
    return {
        "question": body.question,
        "confidence": r.confidence,
        "answer": r.answer,
        "cited": r.cited,
        "candidates": r.candidates,
    }


@app.get("/memories")
def memories():
    """기억 창고 전체(패널 렌더용). 임베딩 벡터는 빼고 가볍게 보낸다."""
    out = []
    for m in _store.all():
        out.append({
            "id": m.id,
            "content": m.content,
            "kind": m.kind,
            "status": m.status,
            "scope": m.scope,
            "reason": m.reason,
            "source": {"session_id": m.source.session_id, "date": m.source.date,
                       "title": _SESSION_TITLES.get(m.source.session_id, m.source.session_id)},
            "associations": [{"type": a.type, "target_id": a.target_id} for a in m.associations],
        })
    return {"memories": out, "active": len(_store.active()), "total": len(out)}


@app.get("/results")
def results():
    """사전계산된 곡선 + 축별 before/after."""
    if not os.path.exists(RESULTS_PATH):
        return JSONResponse({"error": "demo_results.json 없음 — 먼저 scripts/gen_demo_data.py 실행"}, status_code=404)
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)
