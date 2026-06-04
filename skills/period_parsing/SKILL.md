# Skill: Period Parsing

## Purpose
Parse trader/exchange period labels into canonical PeriodExpression records.

## Locked rules
- PY = June-May.
- XH = gas winter Nov-Mar.
- JV = gas summer Apr-Oct.
- FG = Jan-Feb.
- NQ = Jul-Aug.
- BALMO excludes next-day product.

## Required output
- PeriodExpression
- months
- strip weighting rule
- exception if unsupported
