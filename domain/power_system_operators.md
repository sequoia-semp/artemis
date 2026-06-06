# Power System Operators

Power system operators are first-class registry objects for ISO/RTO, balancing
authority, and utility BA concepts. Operator identity should be shared by source
catalogs, locations, feed descriptors, calendars, and future topology/outage
services rather than encoded as unrelated strings in each registry.

## Scope

`power_system_operators.yaml` records source-backed operator facts:

- operator ID and market code;
- operator kind;
- balancing authority code;
- settlement timezone;
- primary interconnection;
- approved data access surfaces;
- supported product families; and
- source documents.

The registry is intentionally broader than PJM, but PJM is the first approved
implementation. Other operators such as MISO, ERCOT, NYISO, ISO-NE, CAISO, and
SPP require their own source-backed records before their data can be promoted
into authoritative artifacts.

## Reference Policy

Power source publications, power locations, feed descriptors, and operator
specific calendars must reference a known power system operator. Unknown
operators fail closed during cross-reference validation.

This does not approve non-PJM source ingestion. It creates the shared operator
surface needed to add non-PJM implementations later without copying PJM-specific
semantics into generic power-system services.
