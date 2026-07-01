"""
기억 한 조각의 '모양'을 정의한다 (데이터 모델).

기획서 4번 '남기기'가 요구한 요소를 그대로 담는다:
  - content      : 나중에 중요할 결정·변경의 핵심 한 줄
  - kind         : 종류 (decision 결정 / change 변경 / failure 실패·폐기 / fact 사실)
  - triggers     : 인출 단서(키워드). 사용자가 정확한 표현을 못 써도 이걸로 떠올린다.
  - source       : 출처 (어느 세션, 언제) — '기억의 근거'
  - reason       : 왜 그렇게 했는지(원인). 연합(인과) 인출의 재료.
  - associations : 다른 기억과의 연결 (예: 이 변경이 어떤 옛 기억을 대체했는지)
  - status       : 상태 (active 유효 / superseded 대체됨 / discarded 폐기)
  - embedding    : 의미 검색용 숫자 벡터 (저장할 때 한 번 계산해 둔다)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Source:
    """기억의 출처: 어느 세션에서, 언제 나온 것인지."""
    session_id: str
    date: str  # "2026-03-15" 같은 표기
    title: str = ""  # 사람이 읽는 세션 제목(예: '괴리율 1차필터·손절'). 답변 출처 표기에 쓴다.


@dataclass
class Association:
    """다른 기억과의 연결 한 줄."""
    type: str        # supersedes(대체함) | superseded_by(대체됨) | because(원인) | related(관련)
    target_id: str   # 연결 대상 기억의 id
    note: str = ""   # 사람이 보기 위한 짧은 메모


@dataclass
class Memory:
    """기억 한 조각."""
    id: str
    content: str
    kind: str                                  # decision | change | failure | fact
    triggers: list[str]
    source: Source
    reason: str = ""
    associations: list[Association] = field(default_factory=list)
    status: str = "active"                     # active | superseded | discarded
    scope: str = "core"                        # core | tangential (망각: 곁다리 분별)
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict[str, Any]:
        """JSON으로 저장할 수 있는 평범한 딕셔너리로 바꾼다."""
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Memory":
        """JSON에서 읽어온 딕셔너리를 다시 Memory 객체로 되살린다."""
        src = d.get("source") or {}
        return Memory(
            id=d["id"],
            content=d["content"],
            kind=d.get("kind", "fact"),
            triggers=list(d.get("triggers", [])),
            source=Source(session_id=src.get("session_id", ""), date=src.get("date", ""), title=src.get("title", "")),
            reason=d.get("reason", ""),
            associations=[Association(**a) for a in d.get("associations", [])],
            status=d.get("status", "active"),
            scope=d.get("scope", "core"),
            embedding=d.get("embedding"),
        )

    def short(self) -> str:
        """사람이 읽기 좋은 한 줄 요약 (긴 임베딩 벡터는 감춘다)."""
        flag = "" if self.status == "active" else f"  <{self.status}>"
        scope = "  [곁다리]" if self.scope == "tangential" else ""
        return f"[{self.id}] ({self.kind}) {self.content}{flag}{scope}  (출처 {self.source.session_id}/{self.source.date})"
