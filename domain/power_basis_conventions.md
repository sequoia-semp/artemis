# Power Basis Conventions

Basis is quoted first/second:

```text
FIRST/SECOND = FIRST full LMP - SECOND full LMP
```

Approved edges:

```text
WH/AD = WH - AD
AD/NI = AD - NI
WH/NI = WH - NI
WH/NI = WH/AD + AD/NI
```

Forbidden unless explicitly approved:

```text
AD/WH
NI/AD
NI/WH
```

Encountering a forbidden orientation should produce `NON_CANONICAL_BASIS_ORIENTATION`.
