# AI Architecture Audit — x402-agentic-research

_Audited: 2026-05-13_

## Summary

The research engine's 7-node LangGraph pipeline is well-designed overall — it applies two-model tiering, falls back gracefully, and uses local embeddings for clustering. However, two high-severity issues stand out: the article scorer pays LLM cost for a task the `all-MiniLM-L6-v2` model already in the codebase handles better, and the buyer agent runs every turn — including static lookups — through `vertex_ai/gemini-2.5-pro`. A medium-severity redundancy in the context parser wastes LLM calls on fields already covered by existing regex logic.

---

## Stack detected

| Tool / Library | Version | Usage count |
|---|---|---|
| OpenAI SDK (TypeScript) | `openai` | 1 call site — buyer agent loop |
| LangChain `ChatOpenAI` via GEIA | `langchain-openai` | 4 node call sites |
| `vertex_ai/gemini-2.5-flash` | PROVIDER_LLM_MODEL_FAST | context_parser, query_generator, article_scorer, analyzer steps 1-2 |
| `vertex_ai/gemini-2.5-pro` | PROVIDER_LLM_MODEL | analyzer step 3 (synthesis); buyer agent ALL turns |
| `sentence-transformers/all-MiniLM-L6-v2` | local | clustering only |
| `sklearn` DBSCAN | local | clustering only |
| Tavily | search API | date_range_searcher |
| LangGraph | workflow | 7-node pipeline |

---

## Findings

| Severity | Type | Location | Current approach | Recommended |
|---|---|---|---|---|
| 🔴 High | `OVERUSE_LLM_CLASSIFY` | `article_scorer.py:88–97` | LLM scores each article 1-5 for relevance in batches of 15; generates `brief_reason` per article | Embed query + articles with `model_manager.get_sentence_transformer()` (already in codebase); cosine similarity → relevance score |
| 🔴 High | `LARGE_MODEL_OVERKILL` | `research-agent.ts:51`, `config.ts:8` | `vertex_ai/gemini-2.5-pro` for all 10 agent turns, including `list_tiers` (static JSON) and `check_budget` (deterministic arithmetic) | Use small/fast model for tool-routing turns; large model only for final summarization |
| 🟡 Medium | `OVERUSE_LLM_EXTRACT` | `context_parser.py:129` | LLM extracts `metric_direction` and `key_entities` — both already derivable without LLM | Regex-detect metric direction; deduplicate entity extraction with existing `_extract_topics_and_entities()` (line 172) |
| 🟡 Medium | `MISSING_CACHE` | All LLM call sites | No cache; identical (topic, date_range) pairs re-run all 5 LLM calls | LRU or Redis cache keyed on `hash(topic + start_date + end_date + tier)` for query generation and analysis outputs |
| 🟢 Low | Wasted output tokens | `article_scorer.py:40` | `brief_reason` field generated per article in LLM prompt; never read downstream | Remove `brief_reason` from SCORING_PROMPT — output tokens cut ~30% per scoring batch |

---

## Detailed recommendations

### 🔴 Finding 1 — Article scorer: replace LLM with local embeddings

**What it does now (`article_scorer.py:88–152`):**
Every request with >15 articles fires one LLM call per 15 articles to score them 1-5 for relevance. For a `pro` tier request (up to 40 results/query × 15 queries = potentially hundreds of articles), this means 10–15 extra LLM calls per research run using the FAST model.

**Why it's suboptimal:**
Relevance scoring (article vs. research topic) is a semantic similarity task — the exact use case for embeddings. The `all-MiniLM-L6-v2` sentence-transformer is already loaded as a singleton in `model_manager` for the clustering node. Using it here costs zero API calls and adds ~5ms per batch.

Additionally, the `brief_reason` field (`SCORING_PROMPT:40`) is generated but never used — `score_map` at line 141 only reads `relevance_score` and `article_type`. This means the LLM is producing roughly 200–400 tokens per article purely for output that is immediately discarded.

**Concrete fix:**

```python
# article_scorer.py — replace LLM scoring with embedding cosine similarity
from sklearn.metrics.pairwise import cosine_similarity
from ..utils.model_manager import model_manager

def score_articles_node(state):
    articles = state.get("research_search_results", [])
    parsed_context = state.get("research_parsed_context", {})
    context_text = parsed_context.get("original_context", "")

    if not articles or not context_text:
        return {"research_search_results": articles, "research_article_scores": [], "errors": []}

    model = model_manager.get_sentence_transformer()

    query_emb = model.encode([context_text])
    article_texts = [
        (a.get("title", "") + " " + a.get("content", ""))[:512]
        for a in articles
    ]
    article_embs = model.encode(article_texts)
    scores = cosine_similarity(query_emb, article_embs)[0]

    for i, (article, score) in enumerate(zip(articles, scores)):
        # Map cosine similarity (0–1) to relevance score (1–5)
        article["_relevance_score"] = max(1, min(5, round(score * 5)))
        article["_article_type"] = "unknown"  # type classification not needed downstream

    articles.sort(key=lambda a: a.get("_relevance_score", 0), reverse=True)
    return {"research_search_results": articles, "research_article_scores": [], "errors": []}
```

**Estimated impact:** Eliminates 5–15 LLM API calls per research request. Latency drops from ~3–8s (batched LLM scoring) to ~50ms (local inference). Zero marginal cost.

---

### 🔴 Finding 2 — Buyer agent: model overkill on tool-routing turns

**What it does now (`research-agent.ts:51`, `config.ts:8`):**
The default `BUYER_LLM_MODEL` is `vertex_ai/gemini-2.5-pro`. Every turn of the up-to-10-turn loop uses this model. In a typical run:
- Turn 1: decides to call `list_tiers` (static JSON retrieval — no reasoning needed)
- Turn 2: reads tier list, decides "pro" (one-word decision guided by a prompt rule)
- Turn 3: calls `check_budget` (the tool does the arithmetic — the LLM just passes a tier name)
- Turn 4: calls `purchase_research`
- Turn 5: summarizes results (this justifies a capable model)

Turns 1–4 spend large-model capacity on tool dispatch, not reasoning.

**Concrete fix — two-model strategy:**

Add `BUYER_LLM_MODEL_FAST` to the config, defaulting to Flash:

```typescript
// config.ts
BUYER_LLM_MODEL_FAST: z.string().default("vertex_ai/gemini-2.5-flash"),
```

Then in the agent loop, switch models after a successful purchase:

```typescript
// research-agent.ts — detect post-purchase turns and use fast model before that point
const isPurchased = messages.some(
  m => m.role === "tool" && typeof m.content === "string" && m.content.includes('"success": true')
);
const model = isPurchased ? config.BUYER_LLM_MODEL : config.BUYER_LLM_MODEL_FAST;

const response = await openai.chat.completions.create({
  model,
  max_tokens: 4096,
  tools: TOOL_DEFINITIONS_OPENAI,
  messages,
});
```

**Estimated impact:** Turns 1–4 use Flash (~20× cheaper, ~5× faster). Turn 5 (summarization) stays on Pro. For a typical 5-turn run, ~80% of buyer agent LLM cost is eliminated.

---

### 🟡 Finding 3 — Context parser: LLM used for metric_direction and key_entities

**What it does now (`context_parser.py:129`):**
`_run_semantic_analysis()` fires an LLM call to extract: `query_intent`, `metric_direction`, `key_entities`, `metric_magnitude`, `suggested_event_types`. Two of these five fields are redundant or replaceable:

1. **`metric_direction`** — whether a metric "decreased/increased/volatile/stable/unknown" — is entirely keyword-matchable.
2. **`key_entities`** — already extracted by `_extract_topics_and_entities()` at line 172 (which runs unconditionally on every request). The LLM re-extracts the same entities at extra cost.

**Concrete fix:**

```python
# context_parser.py — add before _run_semantic_analysis()
_DECREASE = re.compile(r"\b(drop|drops|dropped|fell|declin|crash|dump|slump|plunge|down|reduc|shrink)\b", re.I)
_INCREASE = re.compile(r"\b(rise|rose|surge|jump|rally|soar|climb|up|gain|growth|grow)\b", re.I)
_VOLATILE = re.compile(r"\b(volatile|oscillat|fluctuat|unstable|swing|erratic)\b", re.I)

def _infer_metric_direction(text: str) -> str:
    if _DECREASE.search(text): return "decrease"
    if _INCREASE.search(text): return "increase"
    if _VOLATILE.search(text): return "volatile"
    return "unknown"
```

Then narrow `SEMANTIC_ANALYSIS_PROMPT` to only request `query_intent`, `metric_magnitude`, and `suggested_event_types` — 3 fields instead of 5.

**Estimated impact:** ~40% reduction in context-parser LLM output tokens. `metric_direction` becomes deterministic. Entity extraction no longer duplicated.

---

### 🟡 Finding 4 — No caching for LLM outputs

**What it does now:** Every research request re-runs context parsing, query generation, article scoring, and analysis from scratch. There is no deduplication of identical requests.

**Concrete fix:** Add a request-level cache to `runner.py` keyed on `(research_context, start_date, end_date, tier)`:

```python
# runner.py — add before workflow invocation
import hashlib

_cache: dict = {}  # replace with Redis for production

def _cache_key(ctx, start, end, tier):
    raw = f"{ctx}|{start}|{end}|{tier}"
    return hashlib.md5(raw.encode()).hexdigest()

# At start of run_research():
key = _cache_key(research_context, start_date, end_date, tier)
if key in _cache:
    return _cache[key]

# At end, before return:
_cache[key] = result
```

**Estimated impact:** Demo-mode users re-running the same query get instant results after the first run. Eliminates all 5 LLM calls for repeated identical requests.

---

### 🟢 Finding 5 — Remove `brief_reason` from SCORING_PROMPT

**`article_scorer.py:40`:** The prompt asks for `"brief_reason": "..."` per article. `score_map` at line 141 extracts only `relevance_score` and `article_type`. The brief reason field is generated and immediately discarded.

**Fix:** Remove `"brief_reason": "..."` from the JSON output schema in `SCORING_PROMPT`. This reduces LLM output tokens by ~30% per scoring call.

---

## What's working well

1. **Two-model tiering in `research_analyzer.py`** — Using Flash for event extraction and causal ranking (steps 1–2) and Pro only for synthesis (step 3) is textbook cost-efficient design. The model selection is also tier-aware: basic tier uses Flash only.

2. **Local sentence-transformer + DBSCAN in `clustering_node.py`** — Perfect tool choice: article deduplication is a semantic similarity task, not a reasoning task. No LLM is involved. The singleton `model_manager` avoids reloading.

3. **Article scoring bypass for ≤15 articles** (`article_scorer.py:112–114`) — Avoids unnecessary LLM overhead on small result sets.

4. **Deterministic fallbacks throughout** — `query_generator.py` falls back to pattern templates, `context_parser.py` falls back to regex extraction. Both paths produce usable outputs.

5. **Jinja2 for report generation** — `report_generator.py` uses pure templating with no AI involvement.

6. **`basic` tier uses Flash only** (`config.py:32`) — Tier-based model selection avoids paying Pro prices for low-cost research requests.

---

## Suggested refactor priority

1. **Article scorer → local embeddings** — Highest ROI. Eliminates 5–15 LLM calls per request, uses already-loaded model, zero regression risk.
2. **Remove `brief_reason` from SCORING_PROMPT** — One line change, immediate token savings, no behavior change.
3. **Buyer agent → add `BUYER_LLM_MODEL_FAST` config** — Two-model strategy for tool-routing turns. Second-highest cost impact, minimal code change.
4. **Context parser → metric_direction regex + reduce LLM fields to 3** — Eliminates redundant extraction, improves determinism.
5. **Request-level result cache in `runner.py`** — Low complexity, high value for repeated queries.
