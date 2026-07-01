"""
망각 (4단계).

'삭제'가 아니라 '분별'이다. 이미 쌓인 기억 중 본론과 무관한 일회성 곁다리 잡무를
가려내(scope=tangential) 평소 회상에서 들먹이지 않게 한다.
지우지는 않으므로, 정확히 그것을 물으면 여전히 꺼내올 수 있다.

  run_forgetting(store) : 창고의 모든 기억을 core/tangential 로 분류해 표시한다(flash 1회).
"""
from __future__ import annotations

from .. import config
from .storage import MemoryStore
from .store import _chat_json


FORGET_SYSTEM = """각 기억을 둘 중 하나로 분류한다.
- core      : 제품·전략·설계의 본질적 결정·변경·교훈, 그리고 프로젝트 정체성
              (예: 종목 선별 로직, 필터 기준 변경, 매매·손절 규칙, 실패 교훈, 봇·프로젝트 이름 확정)
- tangential: 본론과 무관하게 한 번 하고 끝난 운영·환경·정리성 잡무
              (예: 클라우드 사양 추정, 폴더 정리, 로그 회전 정책, 개발 도구 세팅)

입력은 "[id] 내용" 목록이다. 모든 id에 대해 JSON으로만 답한다:
{"scopes": {"mem_001": "core", "mem_007": "tangential"}}"""


def run_forgetting(store: MemoryStore) -> dict[str, str]:
    """창고의 모든 기억을 core/tangential 로 분류·표시하고 {id: scope} 를 돌려준다."""
    memories = store.all()
    if not memories:
        return {}

    listing = "\n".join(f"[{m.id}] {m.content}" for m in memories)
    data = _chat_json(
        [{"role": "system", "content": FORGET_SYSTEM},
         {"role": "user", "content": listing}],
        config.MODEL_FLASH,
    )
    scopes = data.get("scopes", {})

    for m in memories:
        scope = scopes.get(m.id)
        if scope in ("core", "tangential"):
            m.scope = scope
    store.save()
    return {m.id: m.scope for m in memories}
