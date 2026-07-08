"""
기억 창고(warehouse) — 모든 기억을 JSON 파일 하나에 저장하고 불러온다.

이 창고를 저장(2단계)·회상(3단계)·망각(4단계)이 함께 쓴다.
간단하고 사람이 직접 열어볼 수 있는 JSON 파일을 쓴다(개인·팀 기억 규모엔 충분).
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .. import config
from .models import Memory

# 기본 저장 위치를 문맥에 맞게 정한다:
#   1) 환경변수 MNEMOSURE_DATA_DIR 이 있으면 그 폴더의 memories.json (배포·커스텀 우선)
#   2) 소스 체크아웃(레포 루트에 pyproject.toml)에서 돌면 레포의 data/memories.json
#      → 데모·개발 스크립트가 커밋된 스냅샷을 그대로 쓴다(동작 불변)
#   3) pip 로 설치돼 쓰일 땐 사용자 홈의 ~/.mnemosure/memories.json (빈 창고로 시작)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_default_path() -> str:
    env_dir = os.environ.get("MNEMOSURE_DATA_DIR")
    if env_dir:
        return os.path.join(env_dir, "memories.json")
    if os.path.isfile(os.path.join(_ROOT, "pyproject.toml")):
        return os.path.join(_ROOT, "data", "memories.json")
    return os.path.join(os.path.expanduser("~"), ".mnemosure", "memories.json")


DEFAULT_PATH = _resolve_default_path()


class MemoryStore:
    """기억들을 담아두고 파일로 저장/복원하는 창고."""

    def __init__(self, path: str = DEFAULT_PATH, check_embedding: bool = True):
        self.path = path
        self.memories: list[Memory] = []
        self._counter = 0
        self._check_embedding = check_embedding  # reembed CLI는 불일치 창고를 열어야 해서 끈다
        self.load()

    def load(self) -> None:
        """파일이 있으면 읽어들이고, 없으면 빈 창고로 시작한다.

        창고에 임베딩 모델 메타가 있으면 현재 설정과 대조한다 — 다른 모델의 벡터와
        섞이면 검색이 조용히 망가지므로, 불일치는 즉시 명확한 에러로 알린다.
        (0.2.x 창고는 메타가 없어 검사를 건너뛴다 — README의 재임베딩 안내 참조)
        """
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.memories = [Memory.from_dict(d) for d in raw.get("memories", [])]
            self._counter = raw.get("counter", len(self.memories))
            meta_model = (raw.get("embedding") or {}).get("model")
            has_vectors = any(m.embedding for m in self.memories)
            if self._check_embedding and meta_model and has_vectors and not config.embed_models_compatible(
                meta_model, config.embed_model_id()
            ):
                raise RuntimeError(
                    f"Embedding model mismatch: this warehouse was built with '{meta_model}' "
                    f"but the current setting is '{config.embed_model_id()}'.\n"
                    f"  - To keep the warehouse: set MNEMOSURE_MODEL_EMBED back to '{meta_model}'\n"
                    f"  - To switch models: re-embed once with  python -m mnemosure.reembed \"{self.path}\""
                )
        else:
            self.memories = []
            self._counter = 0

    def save(self) -> None:
        """현재 기억 전부를 JSON 파일로 저장한다(임베딩 모델 메타 포함)."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        # 차원은 실제 벡터에서 읽는다(사용자가 다른 차원의 모델을 쓸 수 있으므로 상수를 믿지 않는다).
        dim = next((len(m.embedding) for m in self.memories if m.embedding), config.EMBED_DIM)
        payload = {
            "counter": self._counter,
            "embedding": {"model": config.embed_model_id(), "dim": dim},
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
