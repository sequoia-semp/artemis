# Power Locations

Initial v0.1 power locations:

- WH: PJM Western Hub
- AD: AEP-Dayton Hub
- NI: Northern Illinois Hub

All are modeled as PJM power hubs for v0.1. All power price indices use full
LMP. Every normalized power index must explicitly indicate DA or RT. Bare
shorthand defaults to RT.

PJM pnode identities for WH, AD, and NI are verified by the committed PJM Data
Miner pnode fixture. This verifies source identity only; it does not expand
price-component, shape, or product scope.

Approved power locations must carry enough source identity metadata for their
operator-specific price source. For PJM locations this means an official Data
Miner pnode ID, name, type, and `official_pjm_data_miner_verified` source status.
Strict validation rejects duplicate PJM pnode mappings or approved PJM locations
without verified pnode identity. Candidate locations may be cataloged without
promotion to the approved price-location universe.
