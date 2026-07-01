"""
평가 하네스 — 한 '시스템'을 정답표로 돌려 채점·집계한다.

  - 결정 1: 정확성(회상 성공률·환각률)만 채점.
  - 결정 2: 간결성은 채점하지 않고, 객관 수치(토큰·길이)로 따로 기록.

answer_fn(question:str) -> {"answer": str, "confidence": str, "tokens": int}
이 형태만 맞추면 우리 시스템이든 베이스라인이든 동일하게 평가된다.
"""
from __future__ import annotations

from typing import Callable

from .judge import judge


def evaluate(answer_fn: Callable[[str], dict], questions: list[dict]) -> dict:
    rows = []
    for q in questions:
        out = answer_fn(q["question"])
        answer = out.get("answer", "")
        verdict = judge(q["question"], answer,
                        q["must_include"], q["must_not_assert"], q["expect_unknown"])
        rows.append({
            "id": q["id"], "axis": q["axis"], "question": q["question"],
            "answer": answer, "confidence": out.get("confidence", ""),
            "tokens": out.get("tokens", 0), "len": len(answer),
            "recall_success": verdict["recall_success"],
            "hallucinated": verdict["hallucinated"],
            "note": verdict["note"],
        })

    n = len(rows) or 1
    summary = {
        "회상_성공률": sum(r["recall_success"] for r in rows) / n,
        "환각률": sum(r["hallucinated"] for r in rows) / n,
        "평균_토큰": sum(r["tokens"] for r in rows) / n,
        "평균_길이": sum(r["len"] for r in rows) / n,
    }
    return {"rows": rows, "summary": summary}
