---
marp: true
size: 16:9
paginate: true
title: Mnemosure — a source-grounded memory layer for AI agents
style: |
  section {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: #fcfcfb;
    color: #0b0b0b;
    font-size: 23px;
    padding: 56px 64px;
    line-height: 1.45;
  }
  h1 { font-size: 44px; margin: 0 0 8px 0; }
  h2 { font-size: 32px; margin: 0 0 20px 0; }
  h2 strong, h1 strong { color: #2a78d6; }
  a { color: #2a78d6; }
  code { background: #f0efec; padding: 1px 6px; border-radius: 4px; font-size: 0.92em; }
  table { font-size: 19px; }
  th { background: #f0efec; }
  section::after { color: #898781; font-size: 16px; }
  .muted { color: #52514e; }
  .small { font-size: 17px; }
  .tiny { color: #898781; font-size: 14.5px; }
  .cols { display: flex; gap: 28px; align-items: flex-start; }
  .cols > div { flex: 1; }
  .card {
    background: #ffffff; border: 1px solid #e1e0d9; border-radius: 12px;
    padding: 18px 22px; margin: 8px 0;
  }
  .good { color: #2a78d6; font-weight: 700; }
  .bad  { color: #d03b3b; font-weight: 700; }
  section.lead { text-align: center; justify-content: center; }
  section.lead h1 { font-size: 60px; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

# Mnemosure

**An AI memory that says *"I don't know"* when it doesn't,<br>cites its source when it does,<br>and corrects itself when the facts change.**

<br>

<span class="muted">Qwen Cloud Global AI Hackathon · Track 1 — MemoryAgent</span>
<span class="tiny">github.com/jsiksn/mnemosure · pypi.org/project/mnemosure</span>

---

## The problem — forgetting and hallucination **feed each other**

<div class="cols">
<div class="card">

### It forgets
Decisions that *were* made quietly vanish.
Summary-style memory keeps the current
value but drops **why** it was decided —
the reasons and history go first.

</div>
<div class="card">

### It makes things up
Decisions that were *never* made get
stated anyway. Stale facts are asserted
**with full confidence** long after they
were overturned.

</div>
</div>

<br>

The less it remembers, the more it fills the gaps by inventing —
so most "memory" add-ons make both failures **worse at the same time**.

---

## Core idea — a memory with **three duties**

**It does not invent what it cannot remember, and it does not drop what it remembers.**

<div class="cols">
<div class="card">

### Store
Keep only what will matter later — decisions, changes, failures, facts. Throw away the chatter.

</div>
<div class="card">

### Link
A new decision marks the old one `superseded`; its **reason** links back to the failure that caused it (`because`). Failures are kept forever.

</div>
<div class="card">

### Recall
Answer **grounded only in evidence**, with sources. Correct stale facts. No evidence → **"not in the record."**

</div>
</div>

Every answer carries a confidence level — **certain / vague / unknown** — and cites the memories it used.

---

## Same question, different behavior <span class="muted">— real demo output</span>

| The question | A baseline answers | Mnemosure answers |
|---|---|---|
| "Free plan is still capped at **3 projects**, right?" | <span class="bad">hallucination</span> — naive RAG: *"Yes, 3."* (overturned weeks ago) | <span class="good">corrects</span> — *"No, it's **1** now — cut after free-tier abuse was found."* + sources |
| "**Why** did we lower the Pro price?" | <span class="bad">omission</span> — handoff notes: *"I don't know."* (the reason was dropped) | <span class="good">explains</span> — *"Feedback said we were pricier than competitors — so **$12 → $9**/mo."* + sources |
| "What's the **student discount**?" *(never discussed in any session)* | handoff & naive RAG: *"I don't know."* — honest here too | <span class="good">honest</span> — *"Not in the record."* — with an explicit confidence label: **unknown** |

<span class="tiny">Verbatim behavior from the committed demo snapshot (`data/scenarios/pricing/results.json`), translated from the Korean demo. Rows 1–2 quote the baseline that failed on that question — full scores per system are on the Results slide. Answers are produced by the pipeline, never hardcoded.</span>

---

## Architecture — **all model calls run on Qwen**

![w:1080](assets/architecture.png)

<span class="tiny">Extract `qwen3.5-flash` · Embed `text-embedding-v4` (1024-dim) · Rerank `qwen3-rerank` · Answer `qwen3.7-plus` — DashScope, temperature 0 (deterministic).</span>

---

## How it **corrects** — and how it stays **honest**

- **It looks for outdated memories on purpose.** You can only say *"it's $9 now"* if you first find the old *"Pro is $12"* memory. So retrieval never hides replaced facts — it brings them back together with what replaced them.
- **If the evidence is weak, it doesn't answer.** When even the best-matching memory falls below a relevance bar, the answer is **"not in the record."** Refusing to guess is a feature, not a failure.
- **Memories are linked by judgment, not similarity.** Two memories aren't connected just because they *sound* alike — a model decides whether one actually *replaces* the other, or *explains why* it changed.
- **Every sentence stays inside the evidence.** The answer may only use the memories it retrieved, and each claim carries its source.

---

## Results — measured on committed snapshots

| Scenario | Mnemosure | Handoff notes | Naive RAG |
|---|---|---|---|
| Pricing revamp (11 questions) | **11/11** | 4/11 | 4/11 |
| Trading bot (8 questions) | **8/8** | 2/8 | 2/8 |

<br>

- The handoff baseline keeps current values but **drops the reasons** — it misses every "why did we…?" question
- Naive RAG asserts **stale numbers** as if they were still true — hallucinations
- Baselines answer with the **same Qwen brain model** — the difference is memory design, not model horsepower
- Every question, answer and source conversation is browsable in the demo — the memories are *extracted*, not hardcoded

---

## Why the gap keeps **widening**

![w:780](assets/curve.svg)

A handoff note is **rewritten every session** — later decisions push earlier ones (and their *whys*) out of the summary, and what falls out never comes back: **0.8 → 0.4**. Mnemosure doesn't rewrite, it **links** — early facts stay reachable, so accuracy holds at **1.0**.

<span class="tiny">Pricing scenario — memory is built up through session N, then all questions are re-asked; each point = mean of 3 runs.</span>

---

## A product, not a script

<div class="cols">
<div>

**MCP server** — any MCP-capable agent gets
`recall` · `remember` · `list_memories` as tools:

```bash
pip install mnemosure          # PyPI 0.2.1
claude mcp add mnemosure \
  --env DASHSCOPE_API_KEY=sk-… \
  -- mnemosure-mcp
```

**Web demo** — scenario snapshots committed,
so the comparison demo runs right after cloning.

**Deployment** — Docker image, deployed on
**Alibaba Cloud ECS** (`/health`, port-configurable).

</div>
<div>

![w:520](assets/demo.png)

<span class="tiny">Live demo: ask the memory questions, inspect the warehouse, compare against baselines.</span>

</div>
</div>

---

<!-- _class: lead -->

# Remembering less,<br>but **never wrong about it**

**Store what matters · link why it changed · answer only what the record supports**

<br>

`pip install mnemosure`

<span class="muted">GitHub — github.com/jsiksn/mnemosure · PyPI — pypi.org/project/mnemosure</span>
<span class="muted">Live demo — `http://<ECS-IP>/` *(Alibaba Cloud deployment)*</span>

<br>

<span class="tiny">Next up — provider-agnostic 0.3.0: optional rerank, MCP sampling to run on the host agent's own model (Qwen stays the reference).</span>
<span class="tiny">Qwen Cloud Global AI Hackathon · Track 1 — MemoryAgent</span>
