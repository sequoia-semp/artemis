# Official Source Register

This file is a pointer register, not a guarantee that all listed specs have been fully ingested. Do not promote a product into canonical v1 scope solely because a source URL exists.

## Allowed source classes

- User-approved convention
- Official exchange documentation
- Official ISO/RTO documentation
- User-provided API/source documentation
- Deterministic derivation from approved rules

## Official sources to ingest or verify

### Power

- ICE PJM Western Hub Day-Ahead Peak Fixed Price Future
- ICE PJM Western Hub Day-Ahead Off-Peak Fixed Price Future
- ICE PJM Western Hub Real-Time Peak Fixed Price Future
- ICE PJM Western Hub Real-Time Peak (1 MW) Fixed Price Future (`PMI`)
- ICE Option on PJM Western Hub Real-Time Peak (1 MW) Fixed Price Future (`PMI`)
- ICE Option on PJM Western Hub Real-Time Peak Calendar Year One Time Fixed Price Future (`P1X`)
- ICE PJM Western Hub Real-Time Peak Daily Fixed Price Future (`PDP`)
- ICE PJM Western Hub Real-Time Off-Peak Fixed Price Future
- ICE PJM Western Hub Day-Ahead Peak/Off-Peak Fixed Price Futures (`PJC`, `PJD`)
- ICE PJM AEP Dayton Hub Day-Ahead and Real-Time Peak/Off-Peak Fixed Price Futures (`ADB`, `ADD`, `MSO`, `AOD`)
- ICE PJM Northern Illinois Hub Day-Ahead and Real-Time Peak/Off-Peak Fixed Price Futures (`NIB`, `NID`, `PNL`, `NIO`)
- PJM Data Miner / PJM official data sources
- PJM Data Miner pnode and real-time hourly LMP feeds for Western Hub RT LMP
  mapping. Current core demo uses user-approved `51288 = WESTERN HUB`; commit a
  PJM pnode export fixture before changing the source status to fully
  official-ISO-verified.
- GridStatus public PJM LMP examples are used as secondary evidence for hub pnode
  IDs in this mapping slice; they do not replace a committed PJM pnode export
  fixture.

### Gas

- ICE Henry LD1 / NYMEX Henry Hub reference (`H`)
- ICE Option on Henry Penultimate Fixed Price Future (`PHE`)
- ICE TETCO M2 fixed/basis/swing/index products (`BM1`, `BM2`, `BM3`, `MB4`)
- ICE TETCO M3 basis and index products (`TMT`, `MTI`)
- ICE Transco Z6 NY fixed/basis/swing products (`TZ6`, `TZS`, `ZSS`)
- ICE Transco Z6 non-NY fixed/basis/swing/index products (`TPH`, `TPB`, `TPS`, `TPI`)
- ICE Eastern Gas South basis and index products (`DOM`, `DIS`)
- ICE Transco Z5 fixed/basis/swing/index products (`TZ5`, `DKR`, `DKS`, `DKT`)
- ICE Transco Z5 South fixed/basis/swing/index products (`T5Z`, `T5B`, `T5C`, `T5I`)

## Scope rule

Official source existence is not sufficient for v1 inclusion. Product scope must be approved separately.
