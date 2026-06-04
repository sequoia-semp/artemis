# Next Agent Start Here

You are working on the Power + Gas Analytics Workbench v0.1.

First read:

1. `AGENTS.md`
2. `docs/BUILD_PACKET_v0.1.md`
3. `docs/CONVENTIONS_LOCKED_v0.1.md`
4. `development/CHANGE_POLICY.md`

Then run:

```bash
python -m pip install -e .[dev]
python -m pytest
```

Do not change any behavior until you understand the locked conventions.

Critical invariants:

- FIRST/SECOND spread notation means FIRST - SECOND.
- Approved power basis edges are WH/AD, AD/NI, WH/NI.
- Power uses full LMP and must show DA or RT.
- Bare power defaults to RT full LMP.
- Recognized gas locations default to GDD.
- One gas contract is `.25/d`, not `1.0/d`.
- ATC is equal MW peak + equal MW offpeak.
- MVP vol surfaces are WH and HH only.

Your next implementation task is Slice 1 completion: strengthen the semantic base, registry validation, position/price normalization, and tests.
