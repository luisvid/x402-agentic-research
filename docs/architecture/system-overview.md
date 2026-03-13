# System Overview

## Design Principles

1. **Separation of concerns** — Payment validation is middleware, never coupled to research logic.
2. **Language-appropriate services** — Python for ML/NLP pipeline (LangGraph), TypeScript for HTTP + payments.
3. **Deterministic demo** — Mock mode enables full-flow testing without API keys or funded wallets.
4. **Tier-based productization** — Same research pipeline, configurable depth per tier.

## Service Architecture

```mermaid
graph TB
    subgraph Buyer["Buyer Agent (Node.js) — CLI only"]
        direction TB
        AgentMode["agent &lt;goal&gt; — LLM tool-calling"]
        DirectMode["direct --query --tier — manual purchase"]
        X402Client["@x402/axios interceptor"]
        BudgetTracker["Budget tracker"]
    end

    subgraph Gateway["Provider Gateway :8200 (Node.js / Express)"]
        direction TB
        X402MW["x402 payment middleware"]
        ResearchRoute["POST /research/:tier"]
        AdminRoute["GET /admin/records"]
        AuditDB[("SQLite audit.db")]
        ResearchRoute --> AuditDB
        AdminRoute --> AuditDB
    end

    subgraph Engine["Research Engine :8100 (Python / FastAPI)"]
        direction TB
        LG["LangGraph 7-node pipeline"]
        Mock["Mock engine (deterministic)"]
    end

    subgraph External["External Services"]
        Facilitator["x402 Facilitator\nx402.org"]
        Tavily["Tavily Search API"]
        Claude["Anthropic Claude API"]
    end

    Buyer -->|"HTTP POST\n+ X-PAYMENT header"| X402MW
    X402MW -->|"verify"| Facilitator
    X402MW -->|"paid ✓"| ResearchRoute
    ResearchRoute -->|"HTTP POST\n/internal/run-research"| Engine
    LG -->|"search queries"| Tavily
    LG -->|"analysis"| Claude
    AgentMode -->|"tool-calling"| Claude
```

## Data Flow

```mermaid
sequenceDiagram
    participant B as Buyer Agent
    participant G as Gateway (:8200)
    participant F as x402 Facilitator
    participant E as Engine (:8100)

    B->>G: POST /research/pro {query, dates}
    G-->>B: 402 Payment Required {price, payTo, network}

    Note over B: Sign EIP-3009 authorization<br/>with buyer private key

    B->>G: POST /research/pro + X-PAYMENT header
    G->>F: Verify payment signature
    F-->>G: Valid

    Note over G: Zod schema validation<br/>Record in audit store (pending)

    G->>E: POST /internal/run-research {query, tier, dates}

    Note over E: LangGraph pipeline executes<br/>(parse → query → search →<br/>correlate → score → analyze → report)

    E-->>G: ResearchResponse {summary, findings, report}

    Note over G: Update audit store (completed + latency)

    G-->>B: 200 OK + research result
    G->>F: Settle payment
```

## Service Boundaries

### Buyer Agent (`apps/buyer-agent`)
- **Role**: Consumer of the paid research API
- **Modes**: LLM agent (Anthropic tool-calling) or direct CLI purchase
- **Payment**: `@x402/axios` interceptor handles 402 → sign → retry transparently
- **Budget**: Per-request and daily spending limits enforced before purchase
- **Port**: N/A (CLI only)

### Provider Gateway (`apps/provider-gateway`)
- **Role**: Public HTTP API, payment enforcer, request router
- **Payment**: `@x402/express` middleware returns 402 for unpaid requests, validates payment headers
- **Audit**: SQLite `run_records` table tracks every request with payment status and latency
- **Port**: 8200

### Research Engine (`services/research-engine`)
- **Role**: Internal research pipeline, never exposed publicly
- **Pipeline**: 7-node LangGraph graph (parse → query → search → correlate → score → analyze → report)
- **Tiers**: basic (8 queries, no report), pro (15 queries, full), deep (25 queries, full)
- **Port**: 8100

## LangGraph Pipeline Detail

```mermaid
graph LR
    A["1. parse_research_context<br/><i>Extract topics, entities, keywords</i>"]
    B["2. generate_research_queries<br/><i>Create search queries from context</i>"]
    C["3. search_date_range<br/><i>Retrieve articles via Tavily</i>"]
    D["4. correlate_research<br/><i>Cluster and deduplicate</i>"]
    E["5. score_articles<br/><i>Rank by relevance</i>"]
    F["6. llm_analyze_research<br/><i>LLM-based analysis</i>"]
    G["7. generate_research_report<br/><i>Markdown report generation</i>"]
    X["Empty result"]

    A --> B --> C --> D
    D -->|"results exist"| E --> F --> G
    D -->|"no results"| X
```

## Network & Payment

- **Chain**: Base Sepolia (CAIP-2: `eip155:84532`)
- **Asset**: USDC testnet (6 decimals)
- **Facilitator**: `https://x402.org/facilitator` (verifies + settles payments)
- **Scheme**: `exact` (ExactEvmScheme — EIP-3009 transferWithAuthorization)

## Mock Mode

When `MOCK_MODE=true`:
- **Research engine** returns deterministic canned responses (no Tavily/LLM calls)
- **Provider gateway** skips x402 payment middleware (no wallet needed)
- **Buyer agent** still runs the full HTTP flow, just without real payment signing

This enables the full demo to run with zero external dependencies.
