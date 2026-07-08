"""
창고 재임베딩 CLI — 임베딩 모델을 바꿨을 때 기존 기억을 새 벡터로 다시 계산한다.

왜 필요한가: 임베딩 모델이 다르면 벡터의 '눈금'이 달라서, 옛 벡터가 담긴 창고에
새 모델로 질문하면 검색이 조용히 망가진다. 창고를 통째로 한 번 재계산하면 된다.

사용:
  python -m mnemosure.reembed              # 기본 창고(현재 문맥의 memories.json)
  python -m mnemosure.reembed <파일경로>    # 특정 창고 파일

현재 설정(MNEMOSURE_MODEL_EMBED 또는 로컬 설정)의 모델로 다시 계산해 저장한다.
"""
from __future__ import annotations

import sys

from . import config, llm
from .memory.storage import DEFAULT_PATH, MemoryStore
from .memory.store import embed_text_for

BATCH = 16  # 한 번에 임베딩할 기억 수(요청 크기 제한을 피하는 안전값)


def reembed(path: str = DEFAULT_PATH) -> int:
    """창고의 모든 기억을 현재 임베딩 설정으로 재계산해 저장한다. 반환: 처리한 개수."""
    store = MemoryStore(path=path, check_embedding=False)  # 불일치 창고를 열려는 것이므로 검사 끔
    targets = [m for m in store.memories if m.content]
    if not targets:
        print(f"no memories to re-embed in {path}")
        return 0

    print(f"re-embedding {len(targets)} memories in {path}")
    print(f"  -> model: {config.embed_model_id()} (provider: {config.EMBED_PROVIDER})")
    done = 0
    for i in range(0, len(targets), BATCH):
        batch = targets[i : i + BATCH]
        vectors = llm.embed([embed_text_for(m.content, m.triggers) for m in batch])
        for m, v in zip(batch, vectors):
            m.embedding = v
        done += len(batch)
        print(f"  {done}/{len(targets)}")

    store.save()  # 새 임베딩 메타(모델명·차원)도 함께 기록된다
    print("done.")
    return done


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    reembed(path)


if __name__ == "__main__":
    main()
