# Regression Report: T-0153

## Ticket

T-0153 - Valuation ports and local LLM portfolio harness

## Summary

Implemented deterministic pricing/risk ports and a model-agnostic local LLM
harness for the gas portfolio user test. The harness calls
`gas_portfolio_query` first, embeds the deterministic response into the prompt,
and treats the local LLM as non-authoritative narration only.

The local model is supplied by `--model` or `ARTEMIS_OPENAI_COMPATIBLE_MODEL`.
No model name is hardcoded into the harness. OpenCode/Ollama examples now use a
replaceable `your-local-model` placeholder.

## Files Changed

- `artemis.yaml`
- `development/change_requests/CR-0104-valuation-ports-local-llm-harness.yaml`
- `development/regression_reports/REGRESSION_REPORT_T-0153.md`
- `docs/analyst/gas_portfolio_local_llm_test.md`
- `docs/architecture/power_gas_trading_agent_workbench.md`
- `docs/user/setup.md`
- `integrations/coding_backends/opencode/README.md`
- `integrations/coding_backends/opencode/opencode.ollama.example.jsonc`
- `local/artemis.local.example.yaml`
- `registries/tools.yaml`
- `src/pga_workbench/agent_runtime/adapters/ollama.py`
- `src/pga_workbench/cli.py`
- `src/pga_workbench/services/gas_portfolio.py`
- `src/pga_workbench/services/local_llm_portfolio.py`
- `src/pga_workbench/services/ports.py`
- `tests/test_valuation_ports_local_llm.py`
- `work/tickets/T-0153-valuation-ports-local-llm-harness.yaml`

## Tests Run

```bash
.venv/bin/python -m pytest tests/test_gas_portfolio.py tests/test_valuation_ports_local_llm.py -q
.venv/bin/python -m pytest tests/golden tests/test_price_instrument_spine.py -q
.venv/bin/pga validate-work-items
.venv/bin/pga validate-registries
.venv/bin/artemis validate --strict --ticket T-0153 --output development/validation_reports/T-0153/latest.json
```

All commands passed.

## Local LLM User-Test Evidence

Detected Ollama OpenAI-compatible endpoint at `http://localhost:11434/v1` and
ran:

```bash
.venv/bin/artemis analyst gas-portfolio ask-local-llm \
  --input local/gas_portfolio_sample.json \
  --question 'What was total PnL through time?' \
  --output local/gas_portfolio_local_llm_total_pnl_live.json \
  --model 'qwen3.5:35b' \
  --timeout-seconds 180
```

The output records `tool_first: true`, `authority:
deterministic_tool_response`, `provider.kind: openai_compatible`, and
`provider.model: qwen3.5:35b`. The narration restates the deterministic tool
facts for total PnL through time.

Dry-run artifacts were also generated for CI-stable verification:

- `local/gas_portfolio_local_llm_total_pnl_dry_run.json`
- `local/gas_portfolio_local_llm_unsupported_dry_run.json`

## Cache/State Contract

No accepted state-pack, shared cache, or cache promotion contract changed.
Synthetic fixture outputs remain local-test artifacts only.
