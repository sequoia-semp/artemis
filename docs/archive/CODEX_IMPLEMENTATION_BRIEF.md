# Legacy Codex Implementation Brief

This document is retained as a historical design record for the original v0.1
semantic-base scaffold. It is no longer the primary coding-agent entrypoint.

Current entrypoint:

1. `AGENTS.md`
2. `artemis.yaml`
3. `README.md`
4. `docs/README.md`
5. `work/backlog/pjm_workbench_mvp_backlog.yaml`

Run:

```bash
make validate
artemis capabilities
```

The rules from the original brief still matter where they match current
authority: do not invent market conventions, do not reverse quoted spread
orientation, do not silently normalize unknown products, treat LLM inference as
candidate-only, and use deterministic code for calculations.
