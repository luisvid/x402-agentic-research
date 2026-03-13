# ADR 003: HTTP Endpoint Before MCP

## Status
Accepted

## Context
The system could expose research via HTTP REST or via MCP (Model Context Protocol) for direct LLM integration.

## Decision
Build **HTTP REST first**, consider MCP as a future addition.

## Rationale
- HTTP is universally debuggable (curl, Postman, browser)
- x402 payment protocol is designed around HTTP 402 responses
- CLI demo is easier to record and present in a portfolio
- MCP can be layered on top later without architectural changes
- The buyer agent already demonstrates LLM-driven orchestration via Anthropic tool-calling
