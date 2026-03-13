# ADR 002: Node.js Gateway + Python Research Engine

## Status
Accepted

## Context
The research pipeline was originally built in Python using LangGraph. The x402 payment protocol has mature SDKs in TypeScript/JavaScript.

## Decision
Use a **polyglot architecture**: Node.js/TypeScript for the payment gateway and buyer agent, Python for the research engine.

## Rationale
- LangGraph ecosystem is Python-native (LangChain, sentence-transformers, scikit-learn)
- x402 SDKs (@x402/express, @x402/axios, @x402/evm) are TypeScript-only
- The gateway is a thin HTTP layer — no reason to rewrite 7 research nodes in TypeScript
- Internal HTTP boundary between gateway and engine keeps concerns cleanly separated
- Each service can be tested and deployed independently
