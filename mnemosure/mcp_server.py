"""
MCP 서버 — Mnemosure 기억층을 '어떤 에이전트에서나' 도구로 쓰게 한다.

MCP(Model Context Protocol) 표준으로 노출하므로, Claude Desktop·Claude Code 등
MCP를 지원하는 에이전트라면 이 서버를 붙여 '근거 있는 기억'을 도구처럼 호출할 수 있다.
핵심 주장 그대로: 모르면 모른다고 하고, 아는 건 출처와 함께 답한다.

도구:
  - recall(query)               : 질문에 확신도(certain/vague/unknown)·출처와 함께 근거 기반 답을 돌려준다.
  - remember(text, date, title) : 대화/세션에서 결정·변경·실패를 추출해 기억으로 남긴다(대체·원인 자동 연결).
  - list_memories()             : 현재 유효한 기억 목록을 돌려준다.

★ 도구 docstring은 MCP 클라이언트(에이전트)가 읽는 인터페이스 문서라 영어로 쓴다.

실행(stdio):  python -m mnemosure.mcp_server
"""
from __future__ import annotations

from datetime import date as _date

from mcp.server.fastmcp import FastMCP

from .memory.recall import recall as _recall
from .memory.store import ingest_session as _ingest
from .memory.storage import DEFAULT_PATH, MemoryStore

mcp = FastMCP("mnemosure")

# 라이브 기억 창고를 한 번 로드해 재사용한다(remember가 갱신, recall이 조회).
_store = MemoryStore(path=DEFAULT_PATH)


@mcp.tool()
def recall(query: str) -> dict:
    """Answer a question grounded in stored memories. Says "not in the record" when it
    doesn't know; cites sources when it does; corrects superseded facts.

    query: the question (any language — the answer follows the question's language)
    returns: {"confidence": "certain|vague|unknown", "answer": grounded answer with sources, "cited": [memory ids]}
    """
    r = _recall(query, _store)
    return {"confidence": r.confidence, "answer": r.answer, "cited": r.cited}


@mcp.tool()
def remember(session_text: str, date: str = "", title: str = "") -> dict:
    """Extract durable memories (decisions, changes, failures, facts) from a conversation
    or session text. When a new decision overrides an old one, links supersedes/because
    automatically.

    session_text: the raw conversation/session text to remember
    date        : 'YYYY-MM-DD' (defaults to today)
    title       : human-readable session title used for source citations (optional)
    returns     : {"stored": [{"id", "content", "kind"}, ...], "count": n}
    """
    when = date or _date.today().isoformat()
    mems = _ingest(f"mcp-{when}", when, session_text, _store, title=title)
    return {
        "stored": [{"id": m.id, "content": m.content, "kind": m.kind} for m in mems],
        "count": len(mems),
    }


@mcp.tool()
def list_memories(include_superseded: bool = False) -> list[dict]:
    """List the memory warehouse (by default only currently-valid memories).

    include_superseded: when True, also include old memories that have been superseded
    each item: {"id", "content", "kind", "scope", "status", "source"}
    """
    mems = _store.all() if include_superseded else _store.active()
    return [
        {
            "id": m.id,
            "content": m.content,
            "kind": m.kind,
            "scope": m.scope,
            "status": m.status,
            "source": f"{m.source.title or m.source.session_id}/{m.source.date}",
        }
        for m in mems
    ]


def main() -> None:
    """콘솔 스크립트 진입점(`mnemosure-mcp`). 기본 전송은 stdio —
    에이전트가 이 프로세스를 띄워 표준입출력으로 통신한다."""
    mcp.run()


if __name__ == "__main__":
    main()
