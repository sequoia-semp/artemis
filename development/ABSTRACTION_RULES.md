# Abstraction Rules

Do not patch one-off symptoms. Convert repeated issues into the right durable layer:

- convention -> domain file + registry + tests
- product/index mapping -> registry + schema validation + tests
- parser behavior -> parser code + tests
- valuation logic -> deterministic code + tests
- explanation behavior -> skill update + examples + evals

Every improvement should reduce future ambiguity.
