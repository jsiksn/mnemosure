"""
6단계 데모용 데이터 사전계산 (무거운 LLM 작업, 1회 실행).

생성물:
  - data/memories.json   : 라이브 기억 창고(EVAL 시나리오 + 망각) — 서버가 로드
  - data/demo_results.json: 세션 곡선(3회 평균) + 축별 before/after

모델별 토큰 사용량을 단계마다 출력한다. flash가 한계 근접 시 중단하고 모델을 바꿔
못 돌린 만큼만 다시 돌리면 된다.

실행: 프로젝트 루트에서  python3 scripts/gen_demo_data.py
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure import qwen_client  # noqa: E402
from mnemosure.demo.sample_sessions import CURVE_SESSIONS, EVAL_SESSIONS  # noqa: E402
from mnemosure.evaluation.answer_key import CURVE_RECALL, QA_POOL  # noqa: E402
from mnemosure.evaluation.baseline import HandoffBaseline, NaiveRagBaseline  # noqa: E402
from mnemosure.evaluation.judge import judge  # noqa: E402
from mnemosure.evaluation.label import behavior_label  # noqa: E402
from mnemosure.memory.forget import run_forgetting  # noqa: E402
from mnemosure.memory.models import Memory  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import DEFAULT_PATH, MemoryStore  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")
TMP_PATH = os.path.join(DATA_DIR, "_eval_tmp.json")
RESULTS_PATH = os.path.join(DATA_DIR, "demo_results.json")
CURVE_CHECKPOINTS = [4, 5, 6, 7, 8]
CURVE_RUNS = 3
HANDOFF_BUDGET_CURVE = 800


def usage_line(tag):
    u = qwen_client.get_usage()
    parts = ", ".join(f"{m}={t/1000:.0f}K" for m, t in sorted(u.items()))
    print(f"   [tokens @ {tag}] {parts}")


def fresh_store(path):
    s = MemoryStore(path=path)
    s.memories = []
    s._counter = 0
    s.save()
    return s


def _parallel(thunks, workers=6):
    """무인자 함수들을 동시에 실행하고 결과를 입력 순서대로 돌려준다(LLM 대기시간 단축)."""
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda f: f(), thunks))


def recall_rate(answer_fn, questions):
    def ok(q):
        return judge(q["question"], answer_fn(q["question"]), q["must_include"], [], False)["recall_success"]
    res = _parallel([(lambda q=q: ok(q)) for q in questions])
    return sum(1 for r in res if r) / len(questions)


def _cell(q, fn):
    """셀 = {label: 행동 라벨, ans: 실제 답변, conf: 확신도(우리만)}.
    질문을 축에 배정하지 않고, 채점관 판정 + 잡무 들먹임 여부 -> 하나의 행동 라벨로 변환한다."""
    out = fn(q["question"])
    ans = out["answer"]
    conf = out.get("conf")
    jv = judge(q["question"], ans, q.get("must_include", []),
               q.get("must_not_assert", []), q.get("expect_unknown", False))
    tangent = bool(q.get("tangent_keywords")) and any(kw in ans for kw in q["tangent_keywords"])
    label = behavior_label(jv["recall_success"], jv["hallucinated"],
                           q.get("expect_unknown", False), tangent)
    cell = {"label": label, "ans": ans}
    if conf:
        cell["conf"] = conf
    return cell


def eval_table(systems, questions):
    """질문을 평평하게 나열하고, 시스템마다 답변에 행동 라벨을 붙인 표(rows)를 만든다."""
    pairs = [(qi, name, fn, q) for qi, q in enumerate(questions) for name, fn in systems.items()]
    vals = _parallel([(lambda fn=fn, q=q: _cell(q, fn)) for (_, _, fn, q) in pairs])
    rows = [{"q": q["question"]} for q in questions]
    for (qi, name, _, _), val in zip(pairs, vals):
        rows[qi][name] = val
    return rows


def build_curve():
    # 1) 한 번만 점진 적재하며 체크포인트마다 (기억 스냅샷, 핸드오프 노트) 저장.
    store = fresh_store(TMP_PATH)
    base = HandoffBaseline(budget=HANDOFF_BUDGET_CURVE)
    snaps = {}
    for i, s in enumerate(CURVE_SESSIONS, 1):
        if i > max(CURVE_CHECKPOINTS):
            break
        ingest_session(s["session_id"], s["date"], s["text"], store)
        base.ingest(s["text"])
        if i in CURVE_CHECKPOINTS:
            snaps[i] = ([m.to_dict() for m in store.memories], base.note)
    usage_line("curve-적재")

    # 2) 모든 측정(체크포인트 × 반복 × 시스템 × 문항)을 한꺼번에 병렬 실행 후 (cp,시스템)별 평균.
    tasks, meta = [], []
    for cp in CURVE_CHECKPOINTS:
        mem_dicts, note = snaps[cp]
        snap_store = MemoryStore(path=TMP_PATH)
        snap_store.memories = [Memory.from_dict(d) for d in mem_dicts]
        snap_base = HandoffBaseline(budget=HANDOFF_BUDGET_CURVE)
        snap_base.note = note
        sysfns = {
            "ours": (lambda q, st=snap_store: recall(q, st).answer),
            "handoff": (lambda q, b=snap_base: b.answer(q)["answer"]),
        }
        for _ in range(CURVE_RUNS):
            for sysname, fn in sysfns.items():
                for q in CURVE_RECALL:
                    meta.append((cp, sysname))
                    tasks.append((lambda q=q, fn=fn: judge(
                        q["question"], fn(q["question"]), q["must_include"], [], False)["recall_success"]))

    flags = _parallel(tasks, workers=6)

    agg = {}  # (cp, sysname) -> [맞은 수, 전체 수]
    for (cp, sysname), ok in zip(meta, flags):
        a = agg.setdefault((cp, sysname), [0, 0])
        a[0] += 1 if ok else 0
        a[1] += 1
    handoff = [round(agg[(cp, "handoff")][0] / agg[(cp, "handoff")][1], 3) for cp in CURVE_CHECKPOINTS]
    ours = [round(agg[(cp, "ours")][0] / agg[(cp, "ours")][1], 3) for cp in CURVE_CHECKPOINTS]
    for k, cp in enumerate(CURVE_CHECKPOINTS):
        print(f"   cp{cp}: 핸드오프 {handoff[k] * 100:.0f}% / 우리 {ours[k] * 100:.0f}%")
    usage_line("curve-측정")
    return {"checkpoints": CURVE_CHECKPOINTS, "handoff": handoff, "ours": ours}


def _load_or_build_store(path, sessions, forget):
    """저장된 기억이 있으면 '로드만'(재적재·재추출 없음), 없으면 1회 적재 후 저장."""
    store = MemoryStore(path=path)
    if store.all():
        return store  # 이미 적재됨 — 그대로 재사용
    store.memories = []
    store._counter = 0
    for s in sessions:
        ingest_session(s["session_id"], s["date"], s["text"], store, title=s.get("title", ""))
    if forget:
        run_forgetting(store)
    store.save()
    return store


def _systems(store_path, sessions, forget=True):
    # '우리'는 저장된 기억을 재사용(무거운 추출/대체판정 재실행 없음).
    store = _load_or_build_store(store_path, sessions, forget)
    # 핸드오프/RAG는 가벼우니 세션 텍스트로 구성(핸드오프=요약 소량 flash, RAG=임베딩).
    handoff = HandoffBaseline()
    rag = NaiveRagBaseline()
    for s in sessions:
        handoff.ingest(s["text"])
        rag.ingest(s["text"])
    return {
        "우리": lambda q: (lambda r: {"answer": r.answer, "conf": r.confidence})(recall(q, store)),
        "핸드오프": lambda q: {"answer": handoff.answer(q)["answer"]},
        "RAG": lambda q: {"answer": rag.answer(q)["answer"]},
    }


def load_results():
    if os.path.exists(RESULTS_PATH):
        try:
            with open(RESULTS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_results(r):
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)


def live_store_ready():
    if not os.path.exists(DEFAULT_PATH):
        return False
    try:
        with open(DEFAULT_PATH, encoding="utf-8") as f:
            return bool(json.load(f).get("memories"))
    except Exception:
        return False


def main():
    """단계별로 저장하며 진행(resumable). 시간 제한에 걸려도 다시 돌리면 이어서 한다."""
    qwen_client.reset_usage()
    os.makedirs(DATA_DIR, exist_ok=True)
    results = load_results()

    # 1) 라이브 기억 창고 (이미 있으면 건너뜀)
    if live_store_ready():
        print("1) 라이브 창고 이미 존재 — 건너뜀")
    else:
        print("1) 라이브 기억 창고 적재 (EVAL) -> data/memories.json")
        live = MemoryStore()
        live.memories = []
        live._counter = 0
        for s in EVAL_SESSIONS:
            ingest_session(s["session_id"], s["date"], s["text"], live, title=s.get("title", ""))
        run_forgetting(live)
        live.save()
        usage_line("live")

    # 2) 세션 곡선 (이미 계산됐으면 건너뜀)
    if "curve" in results:
        print("2) 곡선 이미 계산됨 — 건너뜀")
    else:
        print("2) 세션 곡선 (CURVE, 3회 재측정 평균)")
        results["curve"] = build_curve()
        save_results(results)
        print("   -> 곡선 저장됨")
        usage_line("curve-saved")

    # 3) 통합 비교표 (하나의 시나리오 + 평평한 질문, 답변마다 행동 라벨) — 이미 있으면 건너뜀
    results.pop("axes", None)  # 옛 축별 구조가 있으면 버린다(단일 표로 대체).
    if "table" in results:
        print("3) 비교표 이미 계산됨 — 건너뜀")
    else:
        print("3) 통합 비교표 (질문 나열 + 답변별 행동 라벨) — 저장된 기억 재사용")
        systems = _systems(DEFAULT_PATH, EVAL_SESSIONS, forget=True)
        results["table"] = {"rows": eval_table(systems, QA_POOL)}
        save_results(results)
        print(f"   -> 비교표 저장됨 ({len(QA_POOL)}문항)")
        usage_line("table-saved")

    if os.path.exists(TMP_PATH):
        os.remove(TMP_PATH)
    print("\n완료: data/memories.json + data/demo_results.json")
    usage_line("final")


if __name__ == "__main__":
    main()
