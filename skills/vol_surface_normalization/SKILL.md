# Skill: Vol Surface Normalization

## Purpose
Normalize WH and HH vol curves/surfaces.

## Rules
- MVP accepts WH and HH only.
- Model convention is Black76.
- ATM is true ATM strike for underlying settle.
- Skew is diff to ATM IV.
- Derive absolute IV, RR, and costless collar metrics.
- Registered option Greeks may use Black76 screening analytics only for WH and HH.
- Non-European exercise styles must be explicitly flagged as screening-only if Black76 is used.

## Required output
- VolSurfacePoint
- derived metrics
- not_in_mvp exception for other locations
