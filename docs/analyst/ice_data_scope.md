# ICE Data Scope

The current ICE scope is descriptor-only. Artemis can validate that ICE
settlement, forward curve, and approved option contract descriptors are declared,
but it does not make live ICE calls without source documentation and credentials.

Registered option descriptors currently include:

- PMI: Option on PJM Western Hub Real-Time Peak (1 MW) Fixed Price Future
- P1X: Option on PJM Western Hub Real-Time Peak Calendar Year One Time Fixed Price Future
- PHE: Option on Henry Penultimate Fixed Price Future

Normal Analyst Mode must not treat fixture or generated ICE-like data as authoritative.
