from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .power_system_artifact_products import load_power_system_artifact_products
from .power_system_operators import load_power_system_operators
from .source_query_plans import load_power_system_source_query_plans

POWER_SYSTEM_RETENTION_ERROR = "POWER_SYSTEM_RETENTION_ERROR"


def load_power_system_artifact_retention_policies(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_system_artifact_retention_policies.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(POWER_SYSTEM_RETENTION_ERROR, "power_system_artifact_retention_policies.yaml must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def validate_power_system_artifact_retention_references(registry_dir: Path) -> dict[str, Any]:
    policies = load_power_system_artifact_retention_policies(registry_dir)
    products = load_power_system_artifact_products(registry_dir)
    operators = load_power_system_operators(registry_dir)

    missing_policies = sorted(set(products) - set(policies))
    unknown_products = sorted(set(policies) - set(products))
    if missing_policies:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            f"Artifact products missing retention policies: {', '.join(missing_policies)}",
        )
    if unknown_products:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            f"Retention policies reference unknown artifact products: {', '.join(unknown_products)}",
        )

    missing_operators = sorted({str(record.get("operator_id")) for record in policies.values()} - set(operators))
    if missing_operators:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            f"Retention policies reference unknown operators: {', '.join(missing_operators)}",
        )

    publish_allowed: list[str] = []
    candidate_publish: list[str] = []
    missing_lineage: list[str] = []
    mismatches: list[str] = []
    source_specific_violations: list[str] = []

    for artifact_key, product in products.items():
        policy = policies[artifact_key]
        if policy.get("operator_id") != product.get("operator_id"):
            mismatches.append(f"{artifact_key}:operator_id")
        if policy.get("commodity") != product.get("commodity"):
            mismatches.append(f"{artifact_key}:commodity")
        if policy.get("product_family") != product.get("product_family"):
            mismatches.append(f"{artifact_key}:product_family")

        is_publishable = product.get("state_pack_publish_status") == "approved_core"
        if bool(policy.get("state_pack_publish_allowed")) != is_publishable:
            mismatches.append(f"{artifact_key}:state_pack_publish_allowed")
        if policy.get("state_pack_publish_allowed") is True:
            publish_allowed.append(artifact_key)
        if product.get("status") == "candidate" and policy.get("state_pack_publish_allowed") is True:
            candidate_publish.append(artifact_key)
        if product.get("state_pack_publish_status") != "approved_core" and policy.get("state_pack_publish_allowed") is True:
            candidate_publish.append(artifact_key)
        if is_publishable and policy.get("lineage_required") is not True:
            missing_lineage.append(artifact_key)
        if product.get("source_product") is True and product.get("state_pack_publish_status") == "approved_core":
            if policy.get("source_specific_required") is not True:
                source_specific_violations.append(artifact_key)

    if mismatches:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            f"Retention policy fields do not match artifact products: {', '.join(sorted(mismatches))}",
        )
    if candidate_publish:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            f"Candidate or non-approved artifact policies cannot allow state-pack publish: {', '.join(sorted(set(candidate_publish)))}",
        )
    if missing_lineage:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            f"Publishable artifact policies must require lineage: {', '.join(sorted(missing_lineage))}",
        )
    if source_specific_violations:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            f"Publishable source-product policies must require source-specific separation: {', '.join(sorted(source_specific_violations))}",
        )

    _validate_load_forecast_retention(policies)
    _validate_historical_source_policies(registry_dir, policies)

    return {
        "retention_policy_count": len(policies),
        "covered_artifact_products": sorted(policies),
        "state_pack_publish_allowed": sorted(publish_allowed),
        "historical_source_policies": {
            artifact_key: dict(policy.get("historical_source_policy") or {})
            for artifact_key, policy in sorted(policies.items())
        },
    }


def _validate_load_forecast_retention(policies: dict[str, dict[str, Any]]) -> None:
    policy = policies.get("pjm_load_fundamentals")
    if not policy:
        return
    if policy.get("forecast_revision_policy") != "latest_curve_hot_revision_history_separate":
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            "pjm_load_fundamentals must keep latest forecast curves and revision history separate",
        )
    tiers = dict(policy.get("retention_tiers") or {})
    if dict(tiers.get("hot") or {}).get("tier") != "hot":
        raise WorkbenchException(POWER_SYSTEM_RETENTION_ERROR, "pjm_load_fundamentals latest curve must be hot")
    if dict(tiers.get("warm") or {}).get("tier") != "hot_warm":
        raise WorkbenchException(POWER_SYSTEM_RETENTION_ERROR, "pjm_load_fundamentals revision history must retain hot/warm policy")


def _validate_historical_source_policies(registry_dir: Path, policies: dict[str, dict[str, Any]]) -> None:
    query_plans = load_power_system_source_query_plans(registry_dir)
    for artifact_key, policy in policies.items():
        historical = dict(policy.get("historical_source_policy") or {})
        plan_ids = [str(item) for item in historical.get("approved_query_plan_ids") or []]
        missing_plans = [plan_id for plan_id in plan_ids if plan_id not in query_plans]
        if missing_plans:
            raise WorkbenchException(
                POWER_SYSTEM_RETENTION_ERROR,
                f"{artifact_key} historical source policy references unknown query plans: {', '.join(missing_plans)}",
            )
        if historical.get("source_restorable") is True and not plan_ids:
            raise WorkbenchException(
                POWER_SYSTEM_RETENTION_ERROR,
                f"{artifact_key} historical source policy is source-restorable but has no approved query plans",
            )
        max_hot_days = historical.get("max_hot_history_days")
        view_windows = [int(item) for item in historical.get("derived_view_windows_days") or []]
        if max_hot_days is not None and view_windows and max(view_windows) > int(max_hot_days):
            raise WorkbenchException(
                POWER_SYSTEM_RETENTION_ERROR,
                f"{artifact_key} derived view windows exceed max_hot_history_days",
            )
        hot_tier = dict(dict(policy.get("retention_tiers") or {}).get("hot") or {})
        hot_max_age = hot_tier.get("max_age_days")
        if max_hot_days is not None and hot_max_age is not None and int(max_hot_days) > int(hot_max_age):
            raise WorkbenchException(
                POWER_SYSTEM_RETENTION_ERROR,
                f"{artifact_key} max_hot_history_days exceeds hot retention tier",
            )
    _validate_pjm_power_price_history_policy(policies)


def _validate_pjm_power_price_history_policy(policies: dict[str, dict[str, Any]]) -> None:
    policy = policies.get("pjm_power_prices")
    if not policy:
        return
    historical = dict(policy.get("historical_source_policy") or {})
    if historical.get("source_restorable") is not True:
        raise WorkbenchException(POWER_SYSTEM_RETENTION_ERROR, "pjm_power_prices hourly LMP history must be source-restorable")
    if historical.get("approved_query_plan_ids") != ["PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS"]:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            "pjm_power_prices hourly LMP history must use the approved hourly LMP query plan",
        )
    if historical.get("derived_view_windows_days") != [1, 5, 10, 30]:
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            "pjm_power_prices must retain explicit 1d, 5d, 10d, and 30d derived view windows",
        )
    if historical.get("row_version_policy") != "current_row_filter_required":
        raise WorkbenchException(
            POWER_SYSTEM_RETENTION_ERROR,
            "pjm_power_prices hourly LMP history must retain current-row version filtering",
        )
