# Implementation Details

This document provides a detailed, implementation-level overview of the system: the key files, internal module communication, and cross-component interactions for the three main services.

> For a high-level architecture overview, see [system-overview.md](system-overview.md).

---

## Table of Contents

- [End-to-End Request Flow](#end-to-end-request-flow)
- [Buyer Agent (`apps/buyer-agent`)](#buyer-agent-appsbuyer-agent)
- [Provider Gateway (`apps/provider-gateway`)](#provider-gateway-appsprovider-gateway)
- [Research Engine (`services/research-engine`)](#research-engine-servicesresearch-engine)
- [Cross-Component Interaction Diagrams](#cross-component-interaction-diagrams)

---

## End-to-End Request Flow

A research purchase traverses the system through this path:

```
CLI input
  → index.ts (parse command)
    → x402-client.ts (create payment-enabled HTTP client)
      → research-agent.ts (LLM agent loop) OR direct purchase
        → POST /research/:tier (gateway)
          → request-id middleware (assign UUID)
            → x402 payment middleware (402 → sign → verify)
              → research.ts route handler (validate, audit insert)
                → engine-client.ts (HTTP proxy with retry)
                  → server.py /internal/run-research
                    → runner.py (init state, run workflow)
                      → 7-node LangGraph pipeline
                    → runner.py (merge state, build response)
                  ← ResearchResponse JSON
                → research.ts (audit update, return response)
              ← 200 OK + research result
            ← response to buyer
          ← display result
```

---

## Buyer Agent (`apps/buyer-agent`)

### File Map

```
src/
├── index.ts                    # CLI entry point (Commander.js)
├── config.ts                   # Zod-validated environment config
├── display.ts                  # Console output formatting
├── client/
│   ├── x402-client.ts          # Payment-enabled axios client + purchaseResearch()
│   └── budget.ts               # In-memory daily + per-request budget tracker
└── agent/
    ├── research-agent.ts       # LLM agent loop (max 10 tool-calling turns)
    ├── tools.ts                # Tool implementations (list_tiers, check_budget, purchase_research)
    ├── types.ts                # AgentResult, TIERS definitions
    └── prompts.ts              # System prompt + tool schemas (Anthropic & OpenAI formats)
```

### Entry Points

**`index.ts`** defines two CLI commands via Commander.js:

| Command | Description | Flow |
|---------|-------------|------|
| `buyer agent "<goal>"` | LLM-driven mode — the agent decides tier, query, and dates | → `runResearchAgent()` |
| `buyer direct --query --tier --start-date --end-date` | Explicit parameters — skips agent reasoning | → `purchaseResearch()` directly |

### Internal Module Communication

```mermaid
graph TD
    CLI["index.ts<br/>(CLI parser)"]
    CFG["config.ts<br/>(Zod validation)"]
    X402["x402-client.ts<br/>(payment-enabled axios)"]
    BUD["budget.ts<br/>(BudgetTracker)"]
    AGT["research-agent.ts<br/>(agent loop)"]
    TOOLS["tools.ts<br/>(executeTool)"]
    PROMPT["prompts.ts<br/>(system prompt + tool defs)"]
    TYPES["types.ts<br/>(AgentResult, TIERS)"]
    DISP["display.ts<br/>(console output)"]

    CLI --> CFG
    CLI --> X402
    CLI --> AGT
    CLI --> BUD
    CLI --> DISP

    AGT --> TOOLS
    AGT --> PROMPT
    AGT --> TYPES

    TOOLS --> X402
    TOOLS --> BUD
    TOOLS --> TYPES
```

### Key Component Details

#### x402 Payment Client (`x402-client.ts`)

Creates an axios instance that automatically handles HTTP 402 payment challenges:

1. Loads buyer's private key → `viem.privateKeyToAccount()`
2. Creates Base Sepolia RPC client → `viem.createPublicClient()`
3. Wraps with EVM signer → `@x402/evm.toClientEvmSigner()`
4. Registers EIP-3009 signing scheme → `@x402/core.registerExactEvmScheme()`
5. Wraps axios with payment interceptor → `@x402/axios.wrapAxiosWithPayment()`

The interceptor is transparent: when the gateway returns 402, the client extracts payment requirements, signs an EIP-3009 authorization, attaches it as a header, and retries — all without caller awareness.

**`purchaseResearch(client, tier, request)`** sends:
```
POST /research/{tier}
Body: { query, start_date, end_date }
→ Returns: ResearchResponse
```

#### Budget Tracker (`budget.ts`)

In-memory enforcement (resets on restart):

- **`checkBudget(tier)`** — validates tier exists, price ≤ per-request limit, daily total within daily limit
- **`recordSpend(tier)`** — increments daily spend counter
- **`getStatus()`** — returns `{ dailySpent, dailyLimit, remaining }`

Hardcoded pricing: basic=$0.01, pro=$0.03, deep=$0.05.

#### Agent Loop (`research-agent.ts`)

`runResearchAgent(goal, config, client)` orchestrates up to 10 LLM tool-calling turns:

```
Initialize OpenAI client (GEIA endpoint)
Set messages = [system_prompt, user_goal]

FOR turn 0..9:
  response = openai.chat.completions.create({
    model, messages, tools: TOOL_DEFINITIONS_OPENAI, max_tokens: 4096
  })

  IF finish_reason == "stop":
    → Agent finished reasoning, break

  IF finish_reason == "tool_calls":
    FOR each tool_call:
      result = executeTool(name, args, { client, budget })
      Append tool result to messages
    CONTINUE to next turn

RETURN AgentResult { goal, tier, query, dates, summary, keyFindings, cost, success }
```

#### Tools (`tools.ts`)

Three tools available to the agent, all return JSON strings:

| Tool | Arguments | What it does |
|------|-----------|--------------|
| `list_tiers` | none | Returns static tier info (name, price, features) from `types.ts` |
| `check_budget` | `tier` | Calls `BudgetTracker.checkBudget()`, returns allowance + budget status |
| `purchase_research` | `query, start_date, end_date, tier` | Pre-checks budget → calls `purchaseResearch()` → records spend → returns result |

### External Calls

| Destination | Protocol | Purpose |
|-------------|----------|---------|
| GEIA (`api.saia.ai/v1`) | OpenAI-compatible REST | LLM tool-calling (agent reasoning) |
| Provider Gateway (`:8200`) | HTTP POST | Research purchase via `/research/{tier}` |
| Base Sepolia RPC | JSON-RPC | EIP-3009 payment signing (via viem) |

---

## Provider Gateway (`apps/provider-gateway`)

### File Map

```
src/
├── index.ts                        # Express server setup, middleware registration
├── config.ts                       # Zod-validated environment config
├── middleware/
│   ├── request-id.ts               # Assigns X-Request-ID if missing (UUID)
│   ├── x402.ts                     # x402 payment middleware configuration
│   └── error-handler.ts            # Global Express error handler
├── routes/
│   ├── research.ts                 # POST /research/:tier handler
│   └── admin.ts                    # GET /admin/records handler
├── services/
│   ├── engine-client.ts            # HTTP client to research engine + retry logic
│   └── audit-store.ts              # SQLite audit trail (better-sqlite3)
└── schemas/
    └── research.ts                 # Zod schemas for request validation + tier config
```

### Middleware Chain

`index.ts` registers middleware in this exact order:

```
1. express.json()                   — Parse JSON body
2. requestIdMiddleware              — Add X-Request-ID header
3. setupPaymentMiddleware()         — x402 payment validation (skipped in mock mode)
4. /research routes                 — Research purchase endpoints
5. /admin routes                    — Audit inspection endpoints
6. errorHandler                     — Catch-all error handler
```

Additionally, a `GET /health` endpoint probes the research engine's `/health`.

### Internal Module Communication

```mermaid
graph TD
    IDX["index.ts<br/>(Express setup)"]
    CFG["config.ts"]
    RID["request-id.ts<br/>(middleware)"]
    X402["x402.ts<br/>(payment middleware)"]
    ERR["error-handler.ts<br/>(middleware)"]
    RES["research.ts<br/>(route handler)"]
    ADM["admin.ts<br/>(route handler)"]
    ENG["engine-client.ts<br/>(HTTP proxy + retry)"]
    AUD["audit-store.ts<br/>(SQLite)"]
    SCH["schemas/research.ts<br/>(Zod validation)"]

    IDX --> CFG
    IDX --> RID
    IDX --> X402
    IDX --> ERR
    IDX --> RES
    IDX --> ADM

    RES --> SCH
    RES --> ENG
    RES --> AUD

    ADM --> AUD
```

### Key Component Details

#### Payment Middleware (`x402.ts`)

Uses `@x402/express.paymentMiddlewareFromConfig()` to protect three routes:

```
POST /research/basic  → $0.01 USDC
POST /research/pro    → $0.03 USDC
POST /research/deep   → $0.05 USDC
```

**Payment verification flow:**
1. Client request arrives without payment → middleware responds **402 Payment Required** with `{ price, payTo, network, asset }`
2. Client signs EIP-3009 authorization and retries with `X-PAYMENT` header
3. Middleware sends payment to `HTTPFacilitatorClient` at `x402.org/facilitator` for verification
4. If valid → `next()` proceeds to route handler
5. After response → facilitator settles the payment on-chain

**Mock mode:** `setupPaymentMiddleware()` returns immediately without registering any middleware — all requests pass through unpaid.

#### Research Route (`routes/research.ts`)

Handles `POST /research/:tier`:

```
1. Validate tier param with tierSchema (basic|pro|deep)
2. Validate body with researchRequestSchema:
   - query: 10-500 chars
   - start_date, end_date: YYYY-MM-DD, max 365-day range
   - format: "json" | "markdown" | "both" (default: "both")
3. auditStore.insert() — record with status "pending"
4. engineClient.runResearch() — proxy to engine (with retry)
5. auditStore.complete() — update status + latency
6. Return engine response or 502 on failure
```

#### Engine Client (`services/engine-client.ts`)

Proxies requests to the research engine at `POST /internal/run-research`:

```typescript
// Request payload
{
  request_id: string,
  query: string,
  start_date: string,
  end_date: string,
  tier: "basic" | "pro" | "deep",
  format: "json" | "markdown" | "both"
}
```

**Retry policy:**
- 3 attempts with exponential backoff (1s → 2s → 4s)
- Retries only on 5xx and network errors
- 4xx errors fail immediately (client validation issues)
- Timeout: 10 minutes per attempt

#### Audit Store (`services/audit-store.ts`)

SQLite database at `data/audit.db` using `better-sqlite3` with WAL mode:

```sql
CREATE TABLE run_records (
  request_id    TEXT PRIMARY KEY,
  query         TEXT NOT NULL,
  tier          TEXT NOT NULL,
  quoted_price  TEXT NOT NULL,       -- "$0.01", "$0.03", "$0.05"
  asset         TEXT DEFAULT 'USDC',
  network       TEXT DEFAULT 'base-sepolia',
  payment_status TEXT DEFAULT 'pending',  -- "paid" | "mock" | "unpaid"
  provider_status TEXT DEFAULT 'pending', -- "completed" | "failed" | "no_data" | "pending"
  engine_latency_ms INTEGER,
  created_at    TEXT DEFAULT (datetime('now')),
  completed_at  TEXT
);
```

**Lifecycle:** `insert()` on request arrival (pending) → `complete()` after engine response (status + latency).

### External Calls

| Destination | Protocol | Purpose |
|-------------|----------|---------|
| x402 Facilitator (`x402.org/facilitator`) | HTTPS | Payment signature verification + settlement |
| Research Engine (`:8100`) | HTTP POST | `POST /internal/run-research` (proxied request) |

---

## Research Engine (`services/research-engine`)

### File Map

```
src/
├── server.py                           # FastAPI app, /health and /internal/run-research endpoints
├── schemas.py                          # Pydantic models (ResearchRequest, ResearchResponse)
├── config.py                           # Tier config builder (queries, models, features per tier)
├── mock_engine.py                      # Deterministic mock responses
├── templates/
│   └── research_analysis.md            # Jinja2 markdown report template
└── engine/
    ├── state.py                        # GraphState TypedDict (shared LangGraph state)
    ├── workflow.py                     # LangGraph DAG definition (7 nodes, conditional edge)
    ├── runner.py                       # Orchestrator: init state → run workflow → merge → build response
    ├── nodes/
    │   ├── context_parser.py           # Node 1: Parse query, extract entities
    │   ├── query_generator.py          # Node 2: Generate search queries (LLM)
    │   ├── date_range_searcher.py      # Node 3: Execute web searches
    │   ├── research_correlator.py      # Node 4: Filter, cluster, deduplicate articles
    │   ├── article_scorer.py           # Node 5: LLM relevance scoring
    │   ├── research_analyzer.py        # Node 6: 3-step causal analysis (LLM)
    │   └── report_generator.py         # Node 7: Jinja2 report rendering
    ├── clustering/
    │   └── clustering_node.py          # DBSCAN + SentenceTransformer embedding clustering
    ├── search/
    │   └── unified_search_engine.py    # Multi-provider search (Tavily, Serper, DuckDuckGo)
    └── utils/
        ├── model_factory.py            # LangChain ChatModel factory (GEIA, OpenAI, Anthropic)
        └── model_manager.py            # Singleton cache for SentenceTransformer model
```

### Entry Point

**`server.py`** exposes two FastAPI endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Returns `{ status, service, mock_mode }` |
| `POST /internal/run-research` | Accepts `ResearchRequest`, routes to mock or real engine |

When `MOCK_MODE=true`, the endpoint calls `run_mock_research()` (deterministic canned data). Otherwise, it calls `run_engine()` which executes the full LangGraph pipeline.

### Internal Module Communication

```mermaid
graph TD
    SRV["server.py<br/>(FastAPI)"]
    SCH["schemas.py<br/>(Pydantic models)"]
    CFG["config.py<br/>(tier config builder)"]
    MOCK["mock_engine.py"]
    RUN["runner.py<br/>(orchestrator)"]
    WF["workflow.py<br/>(LangGraph DAG)"]
    ST["state.py<br/>(GraphState)"]

    N1["context_parser.py"]
    N2["query_generator.py"]
    N3["date_range_searcher.py"]
    N4["research_correlator.py"]
    N5["article_scorer.py"]
    N6["research_analyzer.py"]
    N7["report_generator.py"]

    SEARCH["unified_search_engine.py"]
    CLUST["clustering_node.py"]
    MF["model_factory.py"]
    MM["model_manager.py"]
    TPL["research_analysis.md<br/>(Jinja2 template)"]

    SRV --> SCH
    SRV --> MOCK
    SRV --> RUN

    RUN --> CFG
    RUN --> WF
    RUN --> ST
    RUN --> SCH

    WF --> N1 & N2 & N3 & N4 & N5 & N6 & N7

    N1 --> MF
    N2 --> MF
    N3 --> SEARCH
    N4 --> CLUST
    N5 --> MF
    N6 --> MF
    N7 --> TPL

    CLUST --> MM
```

### Tier Configuration (`config.py`)

`build_engine_config(tier)` returns tier-specific settings:

| Setting | basic | pro | deep |
|---------|-------|-----|------|
| `max_queries` | 8 | 15 | 25 |
| `results_per_query` | 3 | 5 | 5 |
| LLM for extraction/scoring | Flash | Flash | Flash |
| LLM for synthesis | Flash | Pro | Pro |
| `include_report` | No | Yes | Yes |
| `include_causal_chain` | No | Yes | Yes |

### The 7-Node LangGraph Pipeline

All nodes communicate through a shared `GraphState` (TypedDict). Each node reads fields set by prior nodes and writes its own output fields. Fields annotated with `Annotated[List, operator.add]` accumulate across nodes via list concatenation.

```mermaid
graph LR
    N1["1. parse_research<br/>_context"]
    N2["2. generate_research<br/>_queries"]
    N3["3. search_date<br/>_range"]
    N4["4. correlate<br/>_research"]
    N5["5. score<br/>_articles"]
    N6["6. llm_analyze<br/>_research"]
    N7["7. generate_research<br/>_report"]
    END1["END<br/>(no data)"]
    END2["END<br/>(complete)"]

    N1 --> N2 --> N3 --> N4
    N4 -->|"articles found"| N5 --> N6 --> N7 --> END2
    N4 -->|"no articles"| END1
```

#### Node 1: `parse_research_context` (`context_parser.py`)

| | |
|---|---|
| **Reads** | `research_context`, `research_date_range`, `config` |
| **Writes** | `research_parsed_context` |
| **LLM** | Flash (optional semantic analysis — falls back to regex) |
| **Purpose** | Validate dates, extract entities/phrases/acronyms/keywords, optionally run LLM semantic analysis for query intent and metric direction |

Output structure: `{ original_context, start_date, end_date, days_span, phrases, entities, acronyms, keywords, include_terms, exclude_terms, semantic_analysis? }`

#### Node 2: `generate_research_queries` (`query_generator.py`)

| | |
|---|---|
| **Reads** | `research_parsed_context`, `config` |
| **Writes** | `search_queries`, `research_search_batches` |
| **LLM** | Flash (temperature=0.7) |
| **Purpose** | Generate 15-25 diverse search queries covering news, partnerships, regulatory, competitive, on-chain metrics, etc. Falls back to pattern-based generation if LLM fails. |

#### Node 3: `search_date_range` (`date_range_searcher.py`)

| | |
|---|---|
| **Reads** | `research_search_batches`, `config` |
| **Writes** | `research_search_results`, `raw_articles`, `search_metadata` |
| **LLM** | None |
| **Purpose** | Execute searches via `UnifiedSearchEngine` (Tavily by default), enrich articles with research window metadata, deduplicate by URL |

`UnifiedSearchEngine` supports three providers (selected via `SEARCH_ENGINE` env var):
- **Tavily** (default) — `search_depth="advanced"`, `include_raw_content=True`, date range filtering
- **Serper** — Google search via `google.serper.dev/search`
- **DuckDuckGo** — Free, no API key, limited date filtering

#### Node 4: `correlate_research` (`research_correlator.py`)

| | |
|---|---|
| **Reads** | `research_search_results`, `research_parsed_context`, `config` |
| **Writes** | `research_search_results` (filtered), `clustered_events` |
| **LLM** | None |
| **Purpose** | Filter, cluster, and deduplicate articles |

Processing steps:
1. **URL validation** — remove non-article URLs (.pdf, .jpg, .mp4, etc.)
2. **Term filtering** — exclude/include based on parsed context terms
3. **Generic content penalization** — penalize listicles ("Top 10...", "How to...")
4. **Semantic clustering** — `ClusteringNode` uses `SentenceTransformer("all-MiniLM-L6-v2")` to embed article titles+content, then `DBSCAN(eps=0.3, min_samples=2)` groups similar articles
5. **Deduplication** — remove duplicate URLs across clusters
6. Sort clusters by `buzz_score` (article count per cluster)

#### Node 5: `score_articles` (`article_scorer.py`)

| | |
|---|---|
| **Reads** | `research_search_results`, `research_parsed_context`, `config` |
| **Writes** | `research_search_results` (re-sorted), `research_article_scores` |
| **LLM** | Flash (temperature=0.1) |
| **Purpose** | Batch-score articles by relevance (1-5) and classify type. Skipped if ≤15 articles. Processes in batches of 15. |

Article types: `breaking_news`, `analysis`, `data_report`, `trend_report`, `opinion`, `generic`

#### Node 6: `llm_analyze_research` (`research_analyzer.py`)

| | |
|---|---|
| **Reads** | `research_search_results`, `research_parsed_context`, `config` |
| **Writes** | `research_analysis_result` |
| **LLM** | Flash (steps 1-2) + Pro (step 3) |
| **Purpose** | Three-step causal analysis pipeline. Falls back to single-prompt analysis on failure. |

**Step 1 — Event Extraction (Flash):**
Extract distinct events, classify each by causal role:
- `trigger` — discrete event initiating metric change
- `precondition` — pre-existing trend creating vulnerability
- `consequence` — downstream outcome caused by trigger
- `contextual` — background conditions influencing magnitude

**Step 2 — Causal Ranking (Flash):**
Rank events by explanatory power, build causal chain structure:
`{ preconditions[], trigger, cascading_effects[], contextual_factors[] }`

**Step 3 — Synthesis (Pro):**
Generate executive summary, key findings with confidence scores, timeline, and implications.

Output: `{ status, total_articles, context, dates, analysis: { executive_summary, key_findings[], causal_chain, timeline, implications }, intermediate_data }`

#### Node 7: `generate_research_report` (`report_generator.py`)

| | |
|---|---|
| **Reads** | `research_analysis_result`, `research_parsed_context`, `research_search_results`, `research_article_scores` |
| **Writes** | `final_report` |
| **LLM** | None |
| **Purpose** | Render markdown report via Jinja2 template (`templates/research_analysis.md`) |

Report sections: Executive Summary → Key Findings → Causal Model → Timeline → Implications → Sources → Methodology.

### State Merging & Response Building (`runner.py`)

The runner is the critical orchestrator:

1. **Initialize state** — populate `GraphState` with config, query, dates, empty accumulators
2. **Stream workflow** — iterate through all node outputs
3. **Merge state** — accumulate ALL node outputs into a single merged dict (not just the final node). Fields with `operator.add` annotation are list-concatenated automatically by LangGraph.
4. **Build response** — extract summary, findings, causal chain, sources from merged state; calculate average confidence; apply tier restrictions (strip `report_markdown` and `causal_chain` for basic tier)

### External Calls

| Destination | Protocol | Purpose |
|-------------|----------|---------|
| GEIA (`api.saia.ai/v1`) | OpenAI-compatible REST | LLM calls via LangChain `ChatOpenAI` (nodes 1,2,5,6) |
| Tavily API | REST | Web search (node 3, default provider) |
| Serper/DuckDuckGo | REST | Alternative search providers (node 3) |

---

## Cross-Component Interaction Diagrams

### Agent Mode — Full Sequence

```mermaid
sequenceDiagram
    participant User
    participant CLI as index.ts
    participant Agent as research-agent.ts
    participant LLM as GEIA LLM
    participant Tools as tools.ts
    participant Budget as budget.ts
    participant X402 as x402-client.ts
    participant GW as Gateway :8200
    participant Pay as x402 Middleware
    participant Fac as x402 Facilitator
    participant Route as research.ts
    participant Audit as audit-store.ts
    participant Eng as engine-client.ts
    participant API as Engine :8100
    participant Runner as runner.py
    participant Pipeline as LangGraph Pipeline

    User->>CLI: buyer agent "Why did USDe TVL drop?"
    CLI->>CLI: loadConfig(), createX402Client()
    CLI->>Agent: runResearchAgent(goal, config, client)

    Note over Agent: Turn 1: List available tiers
    Agent->>LLM: chat.completions.create(messages, tools)
    LLM-->>Agent: tool_call: list_tiers()
    Agent->>Tools: executeTool("list_tiers", {})
    Tools-->>Agent: JSON tier list

    Note over Agent: Turn 2: Check budget
    Agent->>LLM: chat.completions.create(messages + tool_result)
    LLM-->>Agent: tool_call: check_budget("pro")
    Agent->>Tools: executeTool("check_budget", {tier: "pro"})
    Tools->>Budget: checkBudget("pro")
    Budget-->>Tools: { allowed: true }
    Tools-->>Agent: JSON budget status

    Note over Agent: Turn 3: Purchase research
    Agent->>LLM: chat.completions.create(messages + tool_result)
    LLM-->>Agent: tool_call: purchase_research(query, dates, tier)
    Agent->>Tools: executeTool("purchase_research", {...})
    Tools->>Budget: checkBudget("pro")
    Budget-->>Tools: { allowed: true }

    Tools->>X402: purchaseResearch(client, "pro", request)
    X402->>GW: POST /research/pro {query, dates}
    GW->>Pay: x402 middleware check
    Pay-->>X402: 402 Payment Required {price, payTo}

    Note over X402: @x402/axios interceptor:<br/>Sign EIP-3009 authorization

    X402->>GW: POST /research/pro + X-PAYMENT header
    GW->>Pay: x402 middleware check
    Pay->>Fac: Verify payment signature
    Fac-->>Pay: Valid
    Pay->>Route: next() — payment verified

    Route->>Route: Validate tier + body (Zod)
    Route->>Audit: insert(pending record)
    Route->>Eng: runResearch(engineRequest)
    Eng->>API: POST /internal/run-research

    API->>Runner: run_engine(request)
    Runner->>Pipeline: workflow.stream(initial_state)

    Note over Pipeline: Nodes 1-7 execute sequentially<br/>(see pipeline detail below)

    Pipeline-->>Runner: node outputs streamed
    Runner->>Runner: Merge all node outputs
    Runner->>Runner: Build ResearchResponse (tier restrictions)
    Runner-->>API: ResearchResponse

    API-->>Eng: JSON response
    Eng-->>Route: ResearchResponse

    Note over Eng: Retry up to 3x on 5xx<br/>(exponential backoff)

    Route->>Audit: complete(status, latency)
    Route-->>GW: 200 OK + response
    GW->>Fac: Settle payment

    GW-->>X402: ResearchResponse
    X402-->>Tools: ResearchResponse
    Tools->>Budget: recordSpend("pro")
    Tools-->>Agent: JSON result

    Note over Agent: Turn 4: Summarize
    Agent->>LLM: chat.completions.create(messages + result)
    LLM-->>Agent: finish_reason: "stop" (final summary)
    Agent-->>CLI: AgentResult
    CLI->>User: Display formatted results
```

### Direct Mode — Simplified Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as index.ts
    participant Budget as budget.ts
    participant X402 as x402-client.ts
    participant GW as Gateway :8200
    participant Engine as Engine :8100

    User->>CLI: buyer direct --query "..." --tier pro --start-date ... --end-date ...
    CLI->>Budget: checkBudget("pro")
    Budget-->>CLI: { allowed: true }
    CLI->>X402: purchaseResearch(client, "pro", request)

    X402->>GW: POST /research/pro
    Note over X402,GW: 402 → sign → retry (same as agent mode)
    GW->>Engine: POST /internal/run-research
    Engine-->>GW: ResearchResponse
    GW-->>X402: 200 OK + response

    X402-->>CLI: ResearchResponse
    CLI->>Budget: recordSpend("pro")
    CLI->>User: Display formatted results
```

### Research Engine Pipeline — Internal Data Flow

```mermaid
graph TD
    subgraph "GraphState (shared across all nodes)"
        direction LR
        S1["research_context<br/>research_date_range"]
        S2["research_parsed_context"]
        S3["search_queries<br/>research_search_batches"]
        S4["research_search_results<br/>raw_articles<br/>search_metadata"]
        S5["clustered_events<br/>research_search_results (filtered)"]
        S6["research_article_scores<br/>research_search_results (scored)"]
        S7["research_analysis_result"]
        S8["final_report"]
    end

    N1["Node 1: context_parser<br/><i>Regex + optional LLM (Flash)</i>"]
    N2["Node 2: query_generator<br/><i>LLM (Flash) → 15-25 queries</i>"]
    N3["Node 3: date_range_searcher<br/><i>Tavily/Serper/DuckDuckGo</i>"]
    N4["Node 4: research_correlator<br/><i>Filter + DBSCAN clustering</i>"]
    N5["Node 5: article_scorer<br/><i>LLM (Flash) batch scoring</i>"]
    N6["Node 6: research_analyzer<br/><i>3-step: Flash → Flash → Pro</i>"]
    N7["Node 7: report_generator<br/><i>Jinja2 template rendering</i>"]

    S1 --> N1
    N1 --> S2
    S2 --> N2
    N2 --> S3
    S3 --> N3
    N3 --> S4
    S4 --> N4
    N4 --> S5
    S5 --> N5
    N5 --> S6
    S6 --> N6
    N6 --> S7
    S7 --> N7
    N7 --> S8

    style S1 fill:#e1f5fe
    style S2 fill:#e1f5fe
    style S3 fill:#e1f5fe
    style S4 fill:#e1f5fe
    style S5 fill:#e1f5fe
    style S6 fill:#e1f5fe
    style S7 fill:#e1f5fe
    style S8 fill:#e1f5fe
```

### Gateway Middleware Pipeline

```mermaid
graph LR
    REQ["Incoming<br/>Request"]
    JSON["express.json()<br/><i>Parse body</i>"]
    RID["requestIdMiddleware<br/><i>Assign UUID</i>"]
    X402["x402 middleware<br/><i>Payment gate</i>"]
    ROUTE["Route handler<br/><i>Validate + proxy</i>"]
    ERR["errorHandler<br/><i>Catch-all</i>"]
    RES["Response"]

    REQ --> JSON --> RID --> X402
    X402 -->|"402 (no payment)"| RES
    X402 -->|"paid ✓"| ROUTE
    ROUTE --> RES
    ROUTE -->|"error"| ERR --> RES
```

---

## Summary: Where Key Logic Lives

| Concern | File(s) | Component |
|---------|---------|-----------|
| CLI parsing | `buyer-agent/src/index.ts` | Buyer Agent |
| LLM agent orchestration | `buyer-agent/src/agent/research-agent.ts` | Buyer Agent |
| Tool execution | `buyer-agent/src/agent/tools.ts` | Buyer Agent |
| Automatic 402 payment | `buyer-agent/src/client/x402-client.ts` | Buyer Agent |
| Budget enforcement | `buyer-agent/src/client/budget.ts` | Buyer Agent |
| Payment middleware | `provider-gateway/src/middleware/x402.ts` | Gateway |
| Request validation | `provider-gateway/src/schemas/research.ts` | Gateway |
| Engine proxy + retry | `provider-gateway/src/services/engine-client.ts` | Gateway |
| Audit trail | `provider-gateway/src/services/audit-store.ts` | Gateway |
| Pipeline orchestration | `research-engine/src/engine/runner.py` | Engine |
| Pipeline DAG definition | `research-engine/src/engine/workflow.py` | Engine |
| Shared pipeline state | `research-engine/src/engine/state.py` | Engine |
| Search execution | `research-engine/src/engine/search/unified_search_engine.py` | Engine |
| Article clustering | `research-engine/src/engine/clustering/clustering_node.py` | Engine |
| Causal analysis | `research-engine/src/engine/nodes/research_analyzer.py` | Engine |
| Report rendering | `research-engine/src/engine/nodes/report_generator.py` | Engine |
| LLM model creation | `research-engine/src/engine/utils/model_factory.py` | Engine |
| Tier configuration | `research-engine/src/config.py` | Engine |
