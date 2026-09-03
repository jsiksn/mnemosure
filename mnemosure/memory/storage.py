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
#   2) 환경변수 MNEMOSURE_SCOPE 가 있으면 그 범위의 창고
#        user    → 사용자 홈의 ~/.mnemosure/memories.json (모든 프로젝트가 공유)
#        project → 서버가 뜬 폴더(프로젝트)의 .mnemosure/memories.json (프로젝트별 분리)
#      → MCP 등록 범위에 맞춰 창고를 가르고 싶을 때 쓴다. 예: 계정 전체(--scope user)
#        등록엔 MNEMOSURE_SCOPE=user, 특정 리포에만 등록엔 MNEMOSURE_SCOPE=project.
#   3) 소스 체크아웃(레포 루트에 pyproject.toml)에서 돌면 레포의 data/memories.json
#      → 데모·개발 스크립트가 커밋된 스냅샷을 그대로 쓴다(동작 불변)
#   4) pip 로 설치돼 쓰일 땐 사용자 홈의 ~/.mnemosure/memories.json (빈 창고로 시작)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_default_path() -> str:
    env_dir = os.environ.get("MNEMOSURE_DATA_DIR")
    if env_dir:
        return os.path.join(env_dir, "memories.json")
    scope = os.environ.get("MNEMOSURE_SCOPE", "").strip().lower()
    if scope == "project":
        # MCP 클라이언트(Claude Code 등)는 stdio 서버를 프로젝트 폴더에서 띄우므로
        # 그 시점의 작업 폴더가 곧 프로젝트 루트다.
        return os.path.join(os.getcwd(), ".mnemosure", "memories.json")
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".mnemosure", "memories.json")
    if scope:
        raise RuntimeError(
            f"MNEMOSURE_SCOPE={scope!r} is not valid — use 'user' or 'project' "
            "(or set MNEMOSURE_DATA_DIR to point at a folder directly)."
        )
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
                # 창고를 유지하려면 '그 모델을 쓰던 설정'으로 되돌려야 한다. 임베딩 모델은
                # 공급 방식(local/api)에 따라 다른 변수에서 오므로, 되돌릴 변수를 정확히 지목한다.
                base = config.embed_base_model(meta_model)
                had_prefix = meta_model != base
                if had_prefix:
                    # 같은 모델이지만 e5 접두어를 붙여 만든 창고다.
                    keep = (
                        f"      MNEMOSURE_EMBED_PROVIDER=local\n"
                        f"      MNEMOSURE_MODEL_EMBED_LOCAL={base}\n"
                        f"      MNEMOSURE_E5_PREFIX=on"
                    )
                elif config.EMBED_PROVIDER == "local" and base == config.MODEL_EMBED_LOCAL:
                    # 모델은 같고 접두어만 달라진 경우 — 끄면 그대로 열린다.
                    keep = "      MNEMOSURE_E5_PREFIX=off"
                elif config.EMBED_PROVIDER == "local":
                    keep = (
                        f"      MNEMOSURE_EMBED_PROVIDER=api\n"
                        f"      MNEMOSURE_MODEL_EMBED={base}"
                    )
                else:
                    keep = (
                        f"      MNEMOSURE_EMBED_PROVIDER=local\n"
                        f"      MNEMOSURE_MODEL_EMBED_LOCAL={base}"
                    )
                raise RuntimeError(
                    f"Embedding model mismatch: this warehouse was built with '{meta_model}' "
                    f"but the current setting is '{config.embed_model_id()}' "
                    f"(EMBED_PROVIDER={config.EMBED_PROVIDER}).\n"
                    f"  - To keep the warehouse as-is, set:\n{keep}\n"
                    f"  - To switch to the current model, re-embed once:\n"
                    f"      python -m mnemosure.reembed \"{self.path}\""
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
