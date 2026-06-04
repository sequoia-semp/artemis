# Source Policy

## Authority classes

```yaml
USER_APPROVED_CONVENTION:
  can_define_convention: true
  can_define_scope: true

OFFICIAL_EXCHANGE_SPEC:
  can_define_contract_metadata: true
  can_define_scope: false

OFFICIAL_ISO_DATA:
  can_define_settlement_truth: true
  can_define_trader_semantics: false

USER_DATA_FILE:
  can_show_observed_usage: true
  can_define_convention: requires_approval

PUBLIC_COMMENTARY:
  can_define_convention: false
  allowed_use: context_only

LLM_INFERENCE:
  can_define_convention: false
  allowed_use: candidate_unverified_only
```

## Fail-closed policy

If a product, index, orientation, period, quantity unit, delivery window, or vol surface is not recognized, create a structured exception. Do not guess.
