# Power System Artifact Products

Power system artifact products define the state-pack artifact keys that are
approved or candidate within the direct-source data spine. They sit above
source feed descriptors and below analyst views.

`power_system_artifact_products.yaml` records:

- artifact key;
- operator;
- product family;
- whether the artifact is a source product, derived product, or candidate
  descriptor;
- whether it participates in composition product-key metadata; and
- state-pack publish status.

This registry keeps composed state metadata aligned with explicit product
governance. The artifact composition service must only report composition
product keys that match approved registry entries. Composition product keys may
include true source products and approved derived products, so they should not
be described as source-product keys.

Candidate descriptor products, such as operational event descriptors, are not
approved for authoritative state-pack publish unless a future ticket adds
normalization contracts, fixtures, retention policy, and publish safety tests.

State-pack validation enforces `state_pack_publish_status` for registered
artifact products. Registered candidate-only or deferred products fail candidate
validation before publish. Unregistered legacy artifact keys are left to their
existing schema and delivery-window checks so older non-power fixtures continue
to work.
