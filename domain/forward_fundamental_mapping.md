# Contract To Index Mapping

Exchange contract prices may map to fundamental market indices only when the
mapping is deterministic, source-backed, and explicit in
`registries/forward_fundamental_mappings.yaml`.

## Storage Model

The core price/index model is intentionally split into four layers:

1. `MarketIndex`: compact canonical identity for analytics, for example
   `PJM.AD.RT.FULL_LMP.OFFPEAK`.
2. `ExchangeContract`: verbose exchange metadata, contract symbol, contract
   size, settlement rule, source documents, and official-spec status.
3. `ForwardFundamentalMapping`: deterministic bridge from a source contract to
   a canonical market index, PJM pnode/feed/shape rule for power, or published
   gas index/formula semantics for gas.
4. `PriceSurfacePoint`: source-specific observed price for a period/vintage with
   lineage back to the raw source and, where applicable, the mapping ID.

This keeps stored prices concise while preserving enough semantic detail to
audit exactly why an ICE forward mark maps to a PJM fundamental LMP series or a
published gas index/formula family.

Do not duplicate exchange metadata on every price point. Store contract details
in `registries/exchange_contracts.yaml`, store mapping details in
`registries/forward_fundamental_mappings.yaml`, and store only compact IDs plus
lineage on normalized price records.

## PJM Hub Monthly Contract Grid

The approved v0.1 monthly grid maps ICE PJM hub peak/offpeak contracts to
canonical PJM full-LMP market indices:

```text
PJC -> PJM.WH.DA.FULL_LMP.PEAK
PJD -> PJM.WH.DA.FULL_LMP.OFFPEAK
PMI -> PJM.WH.RT.FULL_LMP.PEAK
OPJ -> PJM.WH.RT.FULL_LMP.OFFPEAK

ADB -> PJM.AD.DA.FULL_LMP.PEAK
ADD -> PJM.AD.DA.FULL_LMP.OFFPEAK
MSO -> PJM.AD.RT.FULL_LMP.PEAK
AOD -> PJM.AD.RT.FULL_LMP.OFFPEAK

NIB -> PJM.NI.DA.FULL_LMP.PEAK
NID -> PJM.NI.DA.FULL_LMP.OFFPEAK
PNL -> PJM.NI.RT.FULL_LMP.PEAK
NIO -> PJM.NI.RT.FULL_LMP.OFFPEAK
```

The target PJM pnodes are:

```text
WH = 51288 = WESTERN HUB
AD = 34497127 = AEP-DAYTON HUB
NI = 33092315 = N ILLINOIS HUB
```

ICE contract mechanics are verified from official ICE product specifications.
PJM pnode identities are verified by the committed PJM Data Miner pnode fixture.

## PJM Western Hub RT Peak Demo

The approved v0.1 demo maps ICE PJM Western Hub real-time peak contracts to the
canonical PJM Western Hub RT full-LMP peak market index:

```text
PMI -> PJM.WH.RT.FULL_LMP.PEAK
PDP -> PJM.WH.RT.FULL_LMP.PEAK
```

The target PJM node is:

```text
pnode_id = 51288
pnode_name = WESTERN HUB
pnode_type = HUB
```

ICE contract mechanics are verified from official ICE product specifications.
The `51288 = WESTERN HUB` pnode mapping is verified by the committed PJM Data Miner pnode fixture.

## ICE Gas Contract Demo Grid

The approved v0.1 gas grid maps a focused set of official ICE natural gas
futures contracts to canonical gas index families:

```text
H   -> GAS.HH.LD1

BM1 -> GAS.TETCO_M2.IFERC
BM2 -> GAS.TETCO_M2.BASIS_TO_LD1
BM3 -> GAS.TETCO_M2.GDD
MB4 -> GAS.TETCO_M2.GDD_INDEX_TO_IFERC
TMT -> GAS.TETCO_M3.BASIS_TO_LD1
MTI -> GAS.TETCO_M3.GDD_INDEX_TO_IFERC

TZ6 -> GAS.TRANSCO_Z6_NY.IFERC
ZSS -> GAS.TRANSCO_Z6_NY.GDD
TZS -> GAS.TRANSCO_Z6_NY.BASIS_TO_LD1
TPH -> GAS.TRANSCO_Z6_NNY.IFERC
TPB -> GAS.TRANSCO_Z6_NNY.BASIS_TO_LD1
TPS -> GAS.TRANSCO_Z6_NNY.GDD
TPI -> GAS.TRANSCO_Z6_NNY.GDD_INDEX_TO_IFERC

TZ5 -> GAS.TRANSCO_Z5.IFERC
DKR -> GAS.TRANSCO_Z5.BASIS_TO_LD1
DKS -> GAS.TRANSCO_Z5.GDD
DKT -> GAS.TRANSCO_Z5.GDD_INDEX_TO_IFERC
T5Z -> GAS.TRANSCO_Z5_SOUTH.IFERC
T5B -> GAS.TRANSCO_Z5_SOUTH.BASIS_TO_LD1
T5C -> GAS.TRANSCO_Z5_SOUTH.GDD
T5I -> GAS.TRANSCO_Z5_SOUTH.GDD_INDEX_TO_IFERC

DOM -> GAS.EASTERN_GAS_SOUTH.BASIS_TO_LD1
DIS -> GAS.EASTERN_GAS_SOUTH.GDD_INDEX_TO_IFERC
```

Gas contract mappings preserve the ICE settlement semantics:

```text
gas_contract_to_index:
  Reference Price A maps directly to a canonical published index family.

gas_basis_contract_to_formula:
  Reference Price A minus Reference Price B maps to BASIS_TO_LD1.
  A = regional Inside FERC monthly index.
  B = NYMEX Henry Hub natural gas settlement / Henry LD1.

gas_index_contract_to_formula:
  Average of Reference Price A prices minus Reference Price B maps to
  GDD_INDEX_TO_IFERC.
  A = Gas Daily midpoint values across the contract period.
  B = regional Inside FERC monthly index.
```

Formula targets are stored as compact `MarketIndex` identities with explicit
formula legs in the mapping registry. They are not flattened into outright
regional gas prices. This keeps basis marks, Gas Daily/IFERC index-difference
marks, and physical daily/monthly index marks semantically distinct.

## Rule

Do not infer contract-to-index mappings from symbol similarity, product names,
or LLM confidence. If an ICE, ISO, or vendor product is not registered in
`forward_fundamental_mappings.yaml`, it must fail closed as an unknown product.
