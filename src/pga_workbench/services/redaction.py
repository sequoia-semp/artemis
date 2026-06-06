from __future__ import annotations

from typing import Any

from ..exceptions import WorkbenchException

_ALLOWED_REDACTION_METADATA_KEYS = {
    "contains_secret_values",
    "contains_raw_records",
    "credential_checks",
    "configured",
    "value_redacted",
}
_DISALLOWED_SECRET_FIELD_TOKENS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer_token",
    "client_secret",
    "credential_value",
    "ocp_apim_subscription_key",
    "password",
    "private_key",
    "secret",
    "subscription_key",
    "token",
)


def assert_no_disallowed_secret_fields(value: Any, *, label: str, error_code: str) -> None:
    """Reject evidence shapes that carry secret-bearing fields despite redaction claims."""
    findings = _find_disallowed_secret_fields(value, path=label, inside_credential_checks=False)
    if findings:
        raise WorkbenchException(
            error_code,
            f"{label} evidence includes disallowed secret field(s): {', '.join(findings)}",
        )


def _find_disallowed_secret_fields(value: Any, *, path: str, inside_credential_checks: bool) -> list[str]:
    if isinstance(value, dict):
        findings: list[str] = []
        for raw_key, item in value.items():
            key = str(raw_key)
            key_path = f"{path}.{key}"
            next_inside_credential_checks = inside_credential_checks or key == "credential_checks"
            if _is_disallowed_secret_field(key, inside_credential_checks=inside_credential_checks):
                findings.append(key_path)
            findings.extend(
                _find_disallowed_secret_fields(
                    item,
                    path=key_path,
                    inside_credential_checks=next_inside_credential_checks,
                )
            )
        return findings
    if isinstance(value, list):
        findings = []
        for index, item in enumerate(value):
            findings.extend(
                _find_disallowed_secret_fields(
                    item,
                    path=f"{path}[{index}]",
                    inside_credential_checks=inside_credential_checks,
                )
            )
        return findings
    return []


def _is_disallowed_secret_field(key: str, *, inside_credential_checks: bool) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized in _ALLOWED_REDACTION_METADATA_KEYS:
        return False
    if inside_credential_checks and key.upper() == key:
        return False
    return any(token in normalized for token in _DISALLOWED_SECRET_FIELD_TOKENS)
