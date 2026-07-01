"""
기억 창고(warehouse) — 모든 기억을 JSON 파일 하나에 저장하고 불러온다.

이 창고를 저장(2단계)·회상(3단계)·망각(4단계)이 함께 쓴다.
간단하고 사람이 직접 열어볼 수 있는 JSON 파일을 쓴다(해커톤 규모엔 충분).
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .models import Memory

# 프로젝트 루트/data/memories.json 를 기본 저장 위치로 한다.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PATH = os.path.join(_ROOT, "data", "memories.json")


class MemoryStore:
    """기억들을 담아두고 파일로 저장/복원하는 창고."""

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.memories: list[Memory] = []
        self._counter = 0
        self.load()

    def load(self) -> None:
        """파일이 있으면 읽어들이고, 없으면 빈 창고로 시작한다."""
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.memories = [Memory.from_dict(d) for d in raw.get("memories", [])]
            self._counter = raw.get("counter", len(self.memories))
        else:
            self.memories = []
            self._counter = 0

    def save(self) -> None:
        """현재 기억 전부를 JSON 파일로 저장한다."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "counter": self._counter,
            "memories": [m.to_dict() for m in self.memories],
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def next_id(self) -> str:
        """mem_001, mem_002 ... 식으로 겹치지 않는 id를 발급한다."""
        self._counter += 1
        return f"mem_{self._counter:03d}"

    def add(self, memory: Memory) -> None:
        self.memories.append(memory)

    def get(self, mem_id: str) -> Optional[Memory]:
        for m in self.memories:
            if m.id == mem_id:
                return m
        return None

    def active(self) -> list[Memory]:
        """아직 유효한(대체/폐기되지 않은) 기억만."""
        return [m for m in self.memories if m.status == "active"]

    def all(self) -> list[Memory]:
        return list(self.memories)
