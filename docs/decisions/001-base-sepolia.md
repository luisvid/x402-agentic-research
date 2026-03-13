# ADR 001: Base Sepolia as Target Network

## Status
Accepted

## Context
We need a blockchain network for x402 payment validation. Options include Ethereum mainnet, various L2s, and their testnets.

## Decision
Use **Base Sepolia** (testnet) as the target network.

## Rationale
- x402 has first-class support for Base (Coinbase L2)
- Base Sepolia has free USDC faucets for testing
- Low-cost transactions make iteration fast
- Base mainnet migration requires only a network config change
- The x402 facilitator at `x402.org` supports Base Sepolia out of the box
