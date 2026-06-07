# Gas Portfolio Local LLM Test

This test surface is a deterministic, synthetic Henry Hub portfolio intended for
local analyst demos and oracle expansion. It is not authoritative market data
and must not be promoted into shared cache.

Build the report:

```bash
artemis analyst gas-portfolio build-sample --output local/gas_portfolio_sample.json
```

Ask a deterministic tool question:

```bash
artemis analyst gas-portfolio query \
  --input local/gas_portfolio_sample.json \
  --question "What was total PnL through time?" \
  --output local/gas_portfolio_answer.json
```

Run the first local-LLM harness in deterministic dry-run mode:

```bash
artemis analyst gas-portfolio ask-local-llm \
  --input local/gas_portfolio_sample.json \
  --question "What was total PnL through time?" \
  --output local/gas_portfolio_local_llm_total_pnl.json \
  --dry-run
```

Run against a local OpenAI-compatible endpoint, such as Ollama at
`http://localhost:11434/v1`:

```bash
ARTEMIS_OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434/v1 \
ARTEMIS_OPENAI_COMPATIBLE_MODEL=deepseek-r1:latest \
artemis analyst gas-portfolio ask-local-llm \
  --input local/gas_portfolio_sample.json \
  --question "What positions did we have on 2026-06-03?" \
  --output local/gas_portfolio_local_llm_positions.json
```

A local LLM may read the query response and narrate it, but the calculation
authority remains the `gas_portfolio_query` tool output. Unsupported questions
return `supported: false`; the LLM must not fill in missing facts.

Starter questions:

- What was total PnL through time?
- What positions did we have on 2026-06-03?
- What was Gas Options book PnL?
- What were the latest option Greeks?
