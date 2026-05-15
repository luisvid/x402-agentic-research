## How the eval works

The eval answers one question: **is the research engine producing good output?**

Unit tests check that code runs. The eval checks that the output makes sense.

---

### Step 1 — Pick a question from the golden dataset

`eval_cases.jsonl` has 25 pre-written research questions. The eval picks 5 (controlled by `EVAL_MAX_CASES`).

Example case:
```json
{
  "query": "What caused the USDC depeg event in March 2023?",
  "tier": "pro",
  "start_date": "2023-03-01",
  "end_date": "2023-04-15"
}
```

---

### Step 2 — Run the research engine on that question

The eval calls the real pipeline. Tavily searches, LLM analysis, everything. It gets back a `ResearchResponse` with:
- `summary` — the executive summary paragraph
- `sources` — the articles it found and used (with 500-char snippets)

---

### Step 3 — Ask RAGAS two questions about the output

RAGAS uses `gpt-4o-mini` as a judge. It reads the question, the answer, and the source snippets, then scores two things:

**`answer_relevancy`** — Does the answer actually address the question? This is the primary gate.

> Question: "What caused the USDC depeg event in March 2023?"
> Answer: "The USDC depeg was triggered by the collapse of Silicon Valley Bank, where Circle held $3.3B in reserves..."
> → Score: **high** — directly addresses the cause asked about

> Answer: "Stablecoins are tokens pegged to the dollar. USDC is issued by Circle..."
> → Score: **low** — generic, doesn't answer *what caused* it

**`faithfulness`** — Are the claims in the answer grounded in the sources? This is tracked but not enforced.

> Answer claims: "Circle held $3.3B at SVB"
> Source snippet: "...Circle disclosed $3.3 billion in deposits at Silicon Valley Bank..."
> → Score: **high** — claim is supported

> Answer claims: "The Fed intervened directly to backstop USDC"
> Source snippets: (no mention of Fed intervention)
> → Score: **low** — claim not grounded in retrieved sources

Faithfulness is informational because this engine synthesises conclusions across 15–25 articles. Those conclusions won't appear verbatim in any single source snippet even when accurate — that's what analysis means. Typical range: 0.30–0.60. A sudden drop below 0.20 is the signal to pay attention to, not the absolute value.

---

### Step 4 — Fail if the primary metric drops below threshold

```
answer_relevancy : 0.760  ✅  (threshold: 0.70)  ← primary gate
faithfulness     : 0.567  (informational only)
```

Only `answer_relevancy` failing → `make eval-live` exits with an error.

```
answer_relevancy : 0.65  ❌  (threshold: 0.70)
```

---

### Why this matters in practice

Say you edit a prompt in `research_analyzer.py`. All 41 unit tests still pass. But `make eval-live` shows:

```
answer_relevancy : 0.61  ❌  (threshold: 0.70)
```

That tells you the prompt change made answers less on-topic — something you couldn't detect from unit tests alone.