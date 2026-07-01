"""
데모 웹 서버 (FastAPI) — 여러 시나리오를 지원.

라이브로 Qwen을 호출하는 건 /ask 뿐. 나머지(/memories, /results, /sessions)는
시나리오별 사전계산 스냅샷·원본 세션 텍스트를 읽어 서빙한다(재계산 없음).

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
from ..memory.storage import MemoryStore
from . import scenarios

HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Mnemosure Demo")

# 시작 시 시나리오별 기억 창고를 1회 로드하고, 세션 제목을 캐시한다(질문마다 재적재 안 함).
_stores: dict[str, MemoryStore] = {}
_titles: dict[str, dict] = {}
for _s in scenarios.all_scenarios():
    _stores[_s["key"]] = MemoryStore(path=scenarios.memories_path(_s["key"]))
    _titles[_s["key"]] = {
        sess["session_id"]: sess.get("title", sess["session_id"])
        for sess in _s["eval_sessions"]
    }


class Ask(BaseModel):
    question: str
    scenario: str = ""


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "index.html"))


@app.get("/scenarios")
def list_scenarios():
    """데모 시나리오 목록(선택기용)."""
    return {
        "scenarios": [
            {"key": s["key"], "title": s["title"],
             "sample_questions": s.get("sample_questions", [])}
            for s in scenarios.all_scenarios()
        ],
        "default": scenarios.default_key(),
    }


@app.post("/ask")
def ask(body: Ask):
    """질문을 선택된 시나리오의 라이브 회상 엔진에 넘겨 근거 기반 답을 돌려준다."""
    key = scenarios.resolve_key(body.scenario)
    r = recall(body.question, _stores[key])
    return {
        "scenario": key,
        "question": body.question,
        "confidence": r.confidence,
        "answer": r.answer,
        "cited": r.cited,
        "candidates": r.candidates,
    }


@app.get("/memories")
def memories(scenario: str = ""):
    """선택 시나리오의 기억 창고 전체(패널 렌더용). 임베딩 벡터는 빼고 가볍게 보낸다."""
    key = scenarios.resolve_key(scenario)
    store = _stores[key]
    titles = _titles[key]
    out = []
    for m in store.all():
        out.append({
            "id": m.id,
            "content": m.content,
            "kind": m.kind,
            "status": m.status,
            "scope": m.scope,
            "reason": m.reason,
            "source": {"session_id": m.source.session_id, "date": m.source.date,
                       "title": titles.get(m.source.session_id, m.source.session_id)},
            "associations": [{"type": a.type, "target_id": a.target_id} for a in m.associations],
        })
    return {"scenario": key, "memories": out, "active": len(store.active()), "total": len(out)}


@app.get("/results")
def results(scenario: str = ""):
    """선택 시나리오의 사전계산된 곡선 + 축별 before/after."""
    key = scenarios.resolve_key(scenario)
    path = scenarios.results_path(key)
    if not os.path.exists(path):
        return JSONResponse(
            {"error": f"'{key}' 결과 없음 — 먼저 scripts/gen_demo_data.py 실행"}, status_code=404)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/sessions")
def sessions(scenario: str = ""):
    """선택 시나리오의 원본 세션(입력) 전문 — 기억이 '하드코딩'이 아니라
    이 대화들에서 추출·연결된 것임을 보이는 투명성 패널."""
    key = scenarios.resolve_key(scenario)
    sc = scenarios.get(key)
    return {
        "scenario": key,
        "sessions": [
            {"session_id": s["session_id"], "title": s.get("title", s["session_id"]),
             "date": s.get("date", ""), "text": s["text"]}
            for s in sc["eval_sessions"]
        ],
    }
