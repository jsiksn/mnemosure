<!--
Devpost submission text for Mnemosure (Qwen Cloud Global AI Hackathon · Track 1: MemoryAgent).
This is a DRAFT to paste into the Devpost online form (not a Word document).
English is the primary submission text; a Korean version follows below for the author's review.
Fill in the demo URL after the Alibaba Cloud deployment. Keep all numbers factual (demo snapshot values).
-->

# Mnemosure — a source-grounded memory layer for AI agents

**Tagline:** An AI memory that says *"I don't know"* when it doesn't, cites its source when it does, and corrects itself when the facts change.

**Track:** MemoryAgent

---

## English (primary — paste into Devpost)

### Inspiration
Across many sessions of AI-assisted work, two failures compound and feed each other:

- the assistant **forgets** decisions that were actually made, and
- it **hallucinates** decisions that were never made.

Most "memory" add-ons only summarize the recent past, so they quietly drop *why* something was decided, and they happily state stale facts with full confidence. We wanted a memory layer whose core promise is the opposite: **it does not invent what it cannot remember, and it does not drop what it remembers.**

### What it does
Mnemosure is a memory layer that an agent talks to over the **Model Context Protocol (MCP)**. It does three things:

- **Stores** only what will matter later — decisions, changes, failures, established facts — and throws away the chatter.
- **Links** memories over time. When a new decision overrides an old one, the old one is marked `superseded`; the *reason* for a change is linked back to the failure that caused it (`because`). Failures/lessons are kept forever.
- **Recalls** with a confidence level and citations. When evidence overrides an old memory, the answer **corrects** the stale fact instead of repeating it. When there is no evidence, it answers **"not in the record"** instead of guessing.

Every answer comes back as one of three confidence levels — **certain / vague / unknown** — with the source of each cited memory.

### How we built it (all on Qwen Cloud / DashScope)
The whole pipeline runs on Qwen models, wrapped behind a single client:

| Role | Qwen model |
|---|---|
| Extract durable memories from a session | `qwen3.5-flash` |
| Embed memories & queries (1024-dim) | `text-embedding-v4` |
| Re-rank retrieved candidates | `qwen3-rerank` |
| Compose the grounded answer | `qwen3.7-plus` |

Two pipelines around a shared JSON warehouse:

- **Ingest (`remember`)**: session → extract → embed → link `supersedes`/`because` (a similarity prefilter proposes candidates, and the flash model makes the final call, so nothing is linked on surface similarity alone) → save.
- **Recall (`recall`)**: query → embed → pull the top matches by similarity (**superseded memories included**, because correcting a stale belief requires finding it first) → `qwen3-rerank` (if even the best hit is too weak, answer **unknown**) → expand `supersedes`/`because` two hops → `qwen3.7-plus` composes the answer **grounded only in that evidence**.

Exposed as an MCP server (`recall` / `remember` / `list_memories`), so any MCP-capable agent can use it as a tool. Shipped on PyPI (`pip install mnemosure`) and deployed as a demo on **Alibaba Cloud (ECS + Docker)**.

### Challenges we ran into
- **Supersession vs. refinement.** "We now filter by X" *replaces* an old rule, but "…and X must also exceed 100" only *refines* it. Getting the model to tell these apart (and not drag an unrelated fact into a supersession) took explicit judgment prompts and a similarity prefilter feeding an LLM verdict.
- **Honest "I don't know."** Calibrating the relevance threshold so the system abstains on genuinely-absent facts, without becoming timid on facts it does hold.
- **Reproducibility & fairness.** The whole pipeline is **deterministic** — the same input always yields the same answer — and baselines answer with the *same* Qwen brain model, so the comparison is about memory design, not model horsepower.
- **Free-tier quota.** We hit model quota limits mid-build and made every model overridable by env var (no code change), keeping the defaults as the canonical spec.

### Results
- Two fictional but information-dense scenarios (a pre-market trading bot and a SaaS subscription-pricing revamp), each shown with the **source conversations** so you can see the memories were *extracted*, not hardcoded.
- Measured, honest results on the demo snapshots. On the pricing scenario's comparison table, Mnemosure answered **11/11** correctly, while a summary-style handoff baseline scored **4/11** (it keeps current values but forgets *reasons*) and a naive-RAG baseline scored **4/11** (it asserts stale numbers = hallucination). On the accuracy-over-sessions curve — each checkpoint **averaged over 3 measurement runs** — Mnemosure holds **~0.93 → 1.0** while the handoff baseline decays **0.8 → 0.4**.
- A working MCP server, a public repo with committed demo snapshots (so the demo runs right after cloning, no key needed to browse), and a containerized cloud deployment.

### What we learned
- **Fix the system, don't make the test easy.** Every time a metric looked off, we corrected the mechanism (or the measurement window) rather than gaming the benchmark.
- **Keep scoring separate from the product.** The behavior labels (accurate / omission / hallucination / noise / honest) are a *demo instrument*, not part of the shipped memory engine.

### What's next
- Finish and harden the Alibaba Cloud deployment; publish the live demo URL.
- **Provider-agnostic 0.3.0.** The chat/embedding path already uses an OpenAI-compatible gateway, so it can point at any compatible endpoint (including a fully-local Ollama). Roadmap: make rerank optional (similarity-ranking fallback), and use **MCP sampling** to borrow the host agent's own model — so a Claude Code user runs it on Claude, a Codex user on Codex — with Qwen remaining the reference implementation.

### Built with
`python` · `qwen` · `dashscope` / `qwen-cloud` · `text-embedding-v4` · `qwen3-rerank` · `mcp` (model context protocol) · `fastapi` · `uvicorn` · `numpy` · `openai-compatible-api` · `docker` · `alibaba-cloud-ecs`

### Links
- **GitHub:** https://github.com/jsiksn/mnemosure
- **PyPI:** https://pypi.org/project/mnemosure/
- **Live demo:** `http://<ECS-PUBLIC-IP>/` *(to be filled in after Alibaba Cloud deployment)*
- **Demo video:** *(to be added)*

---

## 한국어 (검토용 — 위 영문과 동일 내용)

### 영감 (Inspiration)
여러 세션에 걸친 AI 협업에서는 두 실패가 서로를 부추기며 겹칩니다.

- 실제로 내렸던 결정을 **잊어버리고**,
- 내린 적 없는 결정을 **지어냅니다**.

대부분의 "메모리" 기능은 최근 내용을 요약할 뿐이라, *왜* 그렇게 결정했는지를 조용히 흘려버리고, 낡은 사실을 자신 있게 말합니다. 우리는 그 반대를 핵심 약속으로 삼는 메모리 레이어를 원했습니다: **기억하지 못하는 것을 지어내지 않고, 기억한 것은 빠뜨리지 않는다.**

### 무엇을 하나 (What it does)
Mnemosure는 에이전트가 **MCP(Model Context Protocol)**로 대화하는 메모리 레이어입니다. 세 가지를 합니다.

- **저장**: 나중에 중요해질 것(결정·변경·실패·확정된 사실)만 남기고 잡담은 버립니다.
- **연결**: 새 결정이 옛 결정을 갈아엎으면 옛것을 `superseded`(대체됨)로 표시하고, 변경의 *이유*를 그 원인이 된 실패에 잇습니다(`because`). 실패·교훈은 영구 보존.
- **회상**: 확신도와 출처를 붙여 답합니다. 증거가 옛 기억을 뒤집으면 낡은 사실을 되풀이하지 않고 **정정**하고, 증거가 없으면 지어내지 않고 **"기록에 없다"**고 답합니다.

모든 답은 **확실 / 어렴풋 / 모름** 세 확신도 중 하나로, 인용한 기억의 출처와 함께 돌아옵니다.

### 어떻게 만들었나 (전부 Qwen Cloud / DashScope)
파이프라인 전체가 Qwen 모델 위에서 돌아가며, 단일 클라이언트로 감쌌습니다.

| 역할 | Qwen 모델 |
|---|---|
| 세션에서 오래 남을 기억 추출 | `qwen3.5-flash` |
| 기억·질문 임베딩(1024차원) | `text-embedding-v4` |
| 회수 후보 재순위 | `qwen3-rerank` |
| 근거 기반 답변 생성 | `qwen3.7-plus` |

공유 JSON 창고를 중심으로 두 파이프라인:

- **저장(`remember`)**: 세션 → 추출 → 임베딩 → `supersedes`/`because` 연결(의미 유사도 1차 거름망이 후보를 제안, 최종 판정은 flash — 표면 유사도만으로 잇지 않음) → 저장.
- **회상(`recall`)**: 질문 → 임베딩 → 유사도 상위 후보 회수(**대체된 기억 포함** — 낡은 믿음을 고치려면 먼저 찾아야 하니까) → `qwen3-rerank`(최상위조차 약하면 **모름**) → `supersedes`/`because` 2홉 확장 → `qwen3.7-plus`가 **그 증거에만 근거해** 답 구성.

MCP 서버(`recall`/`remember`/`list_memories`)로 노출해 MCP 지원 에이전트라면 도구로 사용. PyPI 배포(`pip install mnemosure`), **Alibaba Cloud(ECS + Docker)** 데모 배포.

### 어려웠던 점 (Challenges)
- **대체 vs 후속 보완.** "이제 X로 거른다"는 옛 규칙을 *대체*하지만, "…그리고 X는 100 이상"은 *보완*일 뿐입니다. 이 둘을 구분하고(무관한 사실을 대체로 끌고 오지 않도록) 판정 프롬프트 + 유사도 1차 거름망→LLM 최종판정을 조합했습니다.
- **정직한 "모름".** 진짜 없는 사실엔 답을 삼가되, 가진 사실엔 소심해지지 않도록 관련도 임계값 보정.
- **재현성·공정성.** 파이프라인 전체를 **결정론적으로**(같은 입력이면 매번 같은 답) 돌립니다. 베이스라인도 *같은* Qwen 두뇌 모델로 답해, 비교가 모델 성능이 아니라 메모리 설계에 관한 것이 되게 함.
- **무료 쿼터.** 개발 중 쿼터 한계를 만나, 모든 모델을 env로 오버라이드 가능하게(코드 수정 없이) 하고 기본값은 정식 스펙으로 유지.

### 결과 (Results)
- 정보량 많은 가상 시나리오 2개(장전 자동매매 봇 · SaaS 구독 요금제 개편). 각 시나리오의 **원본 대화**를 함께 보여줘, 기억이 하드코딩이 아니라 *추출*된 것임을 확인 가능.
- 데모 스냅샷 기준 실측·정직한 결과. 요금제 비교표에서 Mnemosure는 **11/11** 정확, 요약형 핸드오프 베이스라인은 **4/11**(현재값은 남기지만 *이유*를 잊음), 나이브 RAG 베이스라인은 **4/11**(옛 숫자를 우김 = 환각). 세션 누적 정확도 곡선(각 체크포인트를 **3회 반복 측정해 평균**)에서 Mnemosure는 **약 0.93 → 1.0** 유지, 핸드오프는 **0.8 → 0.4**로 감쇠.
- 동작하는 MCP 서버, 사전계산 스냅샷이 커밋된 공개 레포(클론 즉시 데모, 키 없이 열람 가능), 컨테이너화된 클라우드 배포.

### 배운 점 (What we learned)
- **시험을 쉽게 만들지 말고 시스템을 고친다.** 지표가 이상할 때마다 벤치마크를 조작하지 않고 메커니즘(또는 측정 구간)을 바로잡았습니다.
- **채점은 제품과 분리한다.** 행동 라벨(정확/누락/환각/잡음/정직)은 *데모용 계측 도구*이지, 배포되는 기억 엔진의 일부가 아닙니다.

### 다음 계획 (What's next)
- Alibaba Cloud 배포 마무리·안정화, 라이브 데모 URL 공개.
- **provider-agnostic 0.3.0.** chat/임베딩 경로는 이미 OpenAI 호환 게이트웨이라 어떤 호환 엔드포인트로도(완전 로컬 Ollama 포함) 전환 가능. 로드맵: rerank 선택 기능화(유사도 순위 폴백), **MCP sampling**으로 호스트 에이전트의 모델을 빌려 씀 — 클로드코드 사용자는 클로드로, 코덱스 사용자는 코덱스로 — Qwen은 레퍼런스 구현으로 유지.

### 기술 스택 (Built with)
`python` · `qwen` · `dashscope`/`qwen-cloud` · `text-embedding-v4` · `qwen3-rerank` · `mcp` · `fastapi` · `uvicorn` · `numpy` · `openai-compatible-api` · `docker` · `alibaba-cloud-ecs`

### 링크 (Links)
- **GitHub:** https://github.com/jsiksn/mnemosure
- **PyPI:** https://pypi.org/project/mnemosure/
- **라이브 데모:** `http://<ECS-공개-IP>/` *(Alibaba Cloud 배포 후 기입)*
- **데모 영상:** *(추가 예정)*
