"""
1단계 생존 확인 스크립트.

Qwen 4개 모델이 모두 정상 호출되는지 각각 '최소 호출'로 확인한다.
  - qwen3.7-plus  (LLM 메인)
  - qwen3.5-flash (LLM 보조)   ← 이번 단계에서 처음 실증
  - text-embedding-v4 (임베딩)
  - qwen3-rerank  (재순위, 네이티브 엔드포인트)

각 항목: [PASS]/[FAIL] 표시 + 토큰 사용량.
실패 시: 에러 전문을 그대로 출력(결제수단/권한 오류도 숨기지 않음).
하나라도 실패하면 종료코드 1 로 끝난다.

실행: 프로젝트 루트에서  python3 scripts/check_models.py
"""
import os
import sys
import traceback

# 이 스크립트(scripts/)의 부모 폴더 = 프로젝트 루트. import 경로에 추가한다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure import config, qwen_client  # noqa: E402


def _run(title, fn):
    """한 항목을 호출하고 성공/실패와 상세를 출력한 뒤, 성공 여부를 돌려준다."""
    print("\n" + "-" * 64)
    print(f"[ {title} ] 호출 중...")
    try:
        detail = fn()
        print("결과: [PASS]")
        for key, value in detail.items():
            print(f"  - {key}: {value}")
        return True
    except Exception:
        print("결과: [FAIL]  -- 아래 에러 전문 참고")
        print(traceback.format_exc())
        return False


def check_chat_plus():
    r = qwen_client.chat("Who are you? Answer in one sentence.", model=config.MODEL_BRAIN)
    return {"모델": r.model, "응답": r.text.strip(), "총 토큰": r.usage.get("total_tokens")}


def check_chat_flash():
    r = qwen_client.chat("Reply with exactly the two letters: OK", model=config.MODEL_FLASH)
    return {"모델": r.model, "응답": r.text.strip(), "총 토큰": r.usage.get("total_tokens")}


def check_embed():
    vectors = qwen_client.embed("The quick brown fox jumps over the lazy dog.")
    dim = len(vectors[0])
    ok = "OK" if dim == config.EMBED_DIM else f"예상({config.EMBED_DIM})과 다름"
    return {"모델": config.MODEL_EMBED, "차원": dim, "차원 확인": ok}


def check_rerank():
    hits = qwen_client.rerank(
        "What is the capital of France?",
        [
            "Paris is the capital and most populous city of France.",
            "Berlin is the capital of Germany.",
            "Bananas are a good source of potassium.",
        ],
    )
    top = hits[0]
    return {
        "모델": config.MODEL_RERANK,
        "후보 수": len(hits),
        "최상위": f"[{top.score:.3f}] {top.document}",
    }


def main():
    print("=" * 64)
    print("Mnemosure — Qwen 4개 모델 생존 확인")
    print("=" * 64)

    checks = [
        ("LLM 메인  (qwen3.7-plus)", check_chat_plus),
        ("LLM 보조  (qwen3.5-flash)", check_chat_flash),
        ("Embedding (text-embedding-v4)", check_embed),
        ("Rerank    (qwen3-rerank)", check_rerank),
    ]
    results = [(title, _run(title, fn)) for title, fn in checks]

    print("\n" + "=" * 64)
    print("요약")
    print("=" * 64)
    passed = 0
    for title, ok in results:
        mark = "[PASS]" if ok else "[FAIL]"
        print(f"  {mark}  {title}")
        passed += 1 if ok else 0

    print(f"\n총 {len(results)}개 중 {passed}개 성공.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
