"""
데모용 데이터 사전계산 (무거운 LLM 작업, 1회 실행) — 시나리오별.

생성물(시나리오 key 마다):
  - data/scenarios/<key>/memories.json : 라이브 기억 창고(EVAL 시나리오 + 망각) — 서버가 로드
  - data/scenarios/<key>/results.json  : 세션 곡선(3회 평균) + 축별 before/after 비교표

resumable: 이미 만들어진 부분은 건너뛴다. 이미 커밋된 시나리오(예: nxtbot)는 그대로 재사용.
모델별 토큰 사용량을 단계마다 출력한다.

실행:
  python3 scripts/gen_demo_data.py           # 모든 시나리오(미계산분만)
  python3 scripts/gen_demo_data.py uiux      # 특정 시나리오만
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mnemosure import qwen_client  # noqa: E402
from mnemosure.demo import scenarios  # noqa: E402
from mnemosure.evaluation.baseline import HandoffBaseline, NaiveRagBaseline  # noqa: E402
from mnemosure.evaluation.judge import judge  # noqa: E402
from mnemosure.evaluation.label import behavior_label  # noqa: E402
from mnemosure.memory.forget import run_forgetting  # noqa: E402
from mnemosure.memory.models import Memory  # noqa: E402
from mnemosure.memory.recall import recall  # noqa: E402
from mnemosure.memory.store import ingest_session  # noqa: E402
from mnemosure.memory.storage import MemoryStore  # noqa: E402

CURVE_CHECKPOINTS = [4, 5, 6, 7, 8]
CURVE_RUNS = 3
HANDOFF_BUDGET_CURVE = 800


def usage_line(tag):
    u = qwen_client.get_usage()
    parts = ", ".join(f"{m}={t/1000:.0f}K" for m, t in sorted(u.items()))
    print(f"   [tokens @ {tag}] {parts}")


def fresh_store(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s = MemoryStore(path=path)
    s.memories = []
    s._counter = 0
    s.save()
    return s


def _parallel(thunks, workers=6):
    """무인자 함수들을 동시에 실행하고 결과를 입력 순서대로 돌려준다(LLM 대기시간 단축)."""
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda f: f(), thunks))


# --- 곡선: '초기 이유·역사'를 세션이 쌓여도 회상하는가 (우리 vs 핸드오프) ------------
def build_curve(curve_sessions, curve_recall, tmp_path, checkpoints=CURVE_CHECKPOINTS):
    # 1) 한 번만 점진 적재하며 체크포인트마다 (기억 스냅샷, 핸드오프 노트) 저장.
    #    checkpoints는 '측정 시점(세션 수)'. 시나리오가 테스트하는 마지막 변경이 늦게 일어나면
    #    그 이후부터 재도록 시나리오별로 지정한다(그 전엔 사건이 없어 아무도 못 답함).
    store = fresh_store(tmp_path)
    base = HandoffBaseline(budget=HANDOFF_BUDGET_CURVE)
    snaps = {}
    for i, s in enumerate(curve_sessions, 1):
        if i > max(checkpoints):
            break
        ingest_session(s["session_id"], s["date"], s["text"], store)
        base.ingest(s["text"])
        if i in checkpoints:
            snaps[i] = ([m.to_dict() for m in store.memories], base.note)
    usage_line("curve-적재")

    # 2) 모든 측정(체크포인트 × 반복 × 시스템 × 문항)을 한꺼번에 병렬 실행 후 (cp,시스템)별 평균.
    tasks, meta = [], []
    for cp in checkpoints:
        mem_dicts, note = snaps[cp]
        snap_store = MemoryStore(path=tmp_path)
        snap_store.memories = [Memory.from_dict(d) for d in mem_dicts]
        snap_base = HandoffBaseline(budget=HANDOFF_BUDGET_CURVE)
        snap_base.note = note
        sysfns = {
            "ours": (lambda q, st=snap_store: recall(q, st).answer),
            "handoff": (lambda q, b=snap_base: b.answer(q)["answer"]),
        }
        for _ in range(CURVE_RUNS):
            for sysname, fn in sysfns.items():
                for q in curve_recall:
                    meta.append((cp, sysname))
                    tasks.append((lambda q=q, fn=fn: judge(
                        q["question"], fn(q["question"]), q["must_include"], [], False)["recall_success"]))

    flags = _parallel(tasks, workers=6)

    agg = {}  # (cp, sysname) -> [맞은 수, 전체 수]
    for (cp, sysname), ok in zip(meta, flags):
        a = agg.setdefault((cp, sysname), [0, 0])
        a[0] += 1 if ok else 0
        a[1] += 1
    handoff = [round(agg[(cp, "handoff")][0] / agg[(cp, "handoff")][1], 3) for cp in checkpoints]
    ours = [round(agg[(cp, "ours")][0] / agg[(cp, "ours")][1], 3) for cp in checkpoints]
    for k, cp in enumerate(checkpoints):
        print(f"   cp{cp}: 핸드오프 {handoff[k] * 100:.0f}% / 우리 {ours[k] * 100:.0f}%")
    usage_line("curve-측정")
    return {"checkpoints": checkpoints, "handoff": handoff, "ours": ours}


# --- 비교표: 같은 질문에 시스템(우리/핸드오프/RAG)마다 다른 '행동 라벨' -----------------
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


def _cell(q, fn):
    """셀 = {label: 행동 라벨, ans: 실제 답변, conf: 확신도(우리만)}."""
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


# --- 결과 파일 IO -----------------------------------------------------------
def _load_results(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_results(path, r):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)


def _store_ready(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            return bool(json.load(f).get("memories"))
    except Exception:
        return False


# --- 시나리오 하나 통째로 (resumable) ---------------------------------------
def build_scenario(sc):
    key = sc["key"]
    live_path = scenarios.memories_path(key)
    results_path = scenarios.results_path(key)
    tmp_path = os.path.join(os.path.dirname(live_path), "_eval_tmp.json")
    results = _load_results(results_path)

    print(f"\n=== 시나리오 [{key}] {sc['title']} ===")

    # 1) 라이브 기억 창고
    if _store_ready(live_path):
        print(f"[{key}] 1) 라이브 창고 존재 — 건너뜀")
    else:
        print(f"[{key}] 1) 라이브 기억 창고 적재 -> {live_path}")
        live = MemoryStore(path=live_path)
        live.memories = []
        live._counter = 0
        for s in sc["eval_sessions"]:
            ingest_session(s["session_id"], s["date"], s["text"], live, title=s.get("title", ""))
        run_forgetting(live)
        live.save()
        usage_line("live")

    # 2) 세션 곡선
    if "curve" in results:
        print(f"[{key}] 2) 곡선 이미 계산됨 — 건너뜀")
    else:
        print(f"[{key}] 2) 세션 곡선 (3회 재측정 평균)")
        checkpoints = sc.get("curve_checkpoints", CURVE_CHECKPOINTS)
        results["curve"] = build_curve(sc["curve_sessions"], sc["curve_recall"], tmp_path, checkpoints)
        _save_results(results_path, results)
        usage_line("curve-saved")

    # 3) 통합 비교표
    results.pop("axes", None)  # 옛 축별 구조가 있으면 버린다(단일 표로 대체).
    if "table" in results:
        print(f"[{key}] 3) 비교표 이미 계산됨 — 건너뜀")
    else:
        print(f"[{key}] 3) 통합 비교표 (질문 나열 + 답변별 행동 라벨)")
        systems = _systems(live_path, sc["eval_sessions"], forget=True)
        results["table"] = {"rows": eval_table(systems, sc["qa_pool"])}
        _save_results(results_path, results)
        print(f"   -> 비교표 저장됨 ({len(sc['qa_pool'])}문항)")
        usage_line("table-saved")

    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    print(f"[{key}] 완료: {live_path} + {results_path}")


def main(only=None):
    """모든 시나리오를 계산(미계산분만). only(키 목록)를 주면 그 시나리오만."""
    qwen_client.reset_usage()
    for sc in scenarios.all_scenarios():
        if only and sc["key"] not in only:
            print(f"[{sc['key']}] --only 지정으로 건너뜀")
            continue
        build_scenario(sc)
    usage_line("final")
    print("\n완료.")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
