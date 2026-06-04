from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

from .agent.runtime import collect_artemis_capabilities, dump_config_yaml, load_artemis_config, validate_artemis_config
from .analyst.view_engine import build_view, validate_view_manifest
from .core.time import utc_now_iso
from .data.sources import credential_env_names, validate_data_sources
from .dev.coding_backend import validate_coding_backends
from .dev.patch_context import collect_development_context
from .dev.release import build_release_candidate
from .models import RunManifest
from .periods import parse_period
from .registry import validate_registries
from .serialization import read_json, to_plain, write_json
from .services.greeks import read_option_rows, run_black76_greeks
from .services.normalization import normalize_marks, normalize_positions, read_csv_rows
from .services.pnl import run_pnl_attribution
from .services.risk import read_historical_returns, run_historical_var
from .state.packs import build_candidate_state_pack, publish_candidate_state_pack
from .agent_runtime.capabilities import collect_agent_capabilities, collect_agent_doctor
from .agent_runtime.kb_validator import validate_knowledge_base
from .agent_runtime.release_workflow import collect_release_readiness
from .agent_runtime.vcs_workflow import collect_vcs_readiness
from .agent_runtime.work_item_loader import validate_work_items
from .skills.validator import validate_skill_manifest


def _cmd_validate_registries(args: argparse.Namespace) -> int:
    result = validate_registries(Path(args.registries), Path(args.schemas))
    print(f"validated {len(result.validated_files)} registry files; checked {result.checked_records} records")
    for warning in result.warnings:
        print(f"warning: {warning}")
    return 0


def _cmd_parse_period(args: argparse.Namespace) -> int:
    print(to_plain(parse_period(args.label, args.commodity)))
    return 0


def _cmd_normalize_prices(args: argparse.Namespace) -> int:
    points = normalize_marks(read_csv_rows(Path(args.input)))
    write_json(Path(args.output), points)
    print(f"wrote {len(points)} price points to {args.output}")
    return 0


def _cmd_normalize_positions(args: argparse.Namespace) -> int:
    marks = []
    if args.marks:
        for item in read_json(Path(args.marks)):
            from .models import PriceSurfacePoint

            marks.append(PriceSurfacePoint(**item))
    positions = normalize_positions(read_csv_rows(Path(args.positions)), marks)
    write_json(Path(args.output), positions)
    print(f"wrote {len(positions)} normalized positions to {args.output}")
    return 0


def _load_positions(path: Path):
    from .models import NormalizedPosition

    return [NormalizedPosition(**item) for item in read_json(path)]


def _cmd_run_pnl(args: argparse.Namespace) -> int:
    report = run_pnl_attribution(_load_positions(Path(args.prior)), _load_positions(Path(args.current)), args.run_id)
    write_json(Path(args.output), report)
    print(f"wrote PnL attribution to {args.output}")
    return 0


def _cmd_run_var(args: argparse.Namespace) -> int:
    report = run_historical_var(_load_positions(Path(args.positions)), read_historical_returns(Path(args.returns)), args.as_of, args.run_id)
    write_json(Path(args.output), report)
    print(f"wrote historical VaR to {args.output}")
    return 0


def _cmd_run_greeks(args: argparse.Namespace) -> int:
    report = run_black76_greeks(read_option_rows(Path(args.input)), args.run_id)
    write_json(Path(args.output), report)
    print(f"wrote Greeks to {args.output}")
    return 0


def _cmd_build_state_pack(args: argparse.Namespace) -> int:
    artifacts = read_json(Path(args.artifacts))
    manifest = RunManifest(run_id=args.run_id, created_at=utc_now_iso(), agent_pack_version="0.1.0", inputs=[{"path": args.artifacts}])
    build_candidate_state_pack(Path(args.state_root), args.run_id, args.as_of, artifacts, manifest, synthetic=args.synthetic)
    if args.publish:
        publish_candidate_state_pack(Path(args.state_root), args.run_id, shared_readonly=args.shared_readonly)
        print(f"published state pack {args.run_id}")
    else:
        print(f"built candidate state pack {args.run_id}")
    return 0


def _cmd_work_context(args: argparse.Namespace) -> int:
    context = collect_development_context(Path(args.repo_root), args.ticket, Path(args.config) if args.config else None)
    context["compatibility_command"] = "pga work-context"
    if args.output:
        write_json(Path(args.output), context)
        print(f"wrote work context for {args.ticket} to {args.output}")
    else:
        import json

        print(json.dumps(context, indent=2, sort_keys=True))
    return 0


def _cmd_validate_work_items(args: argparse.Namespace) -> int:
    validated = validate_work_items(Path(args.work_root), Path(args.schemas))
    print(f"validated {len(validated)} work items")
    return 0


def _cmd_validate_kb(args: argparse.Namespace) -> int:
    result = validate_knowledge_base(Path(args.kb_root), Path(args.schemas))
    print(f"validated knowledge base manifest with {result['entries']} entries")
    return 0


def _cmd_agent_capabilities(args: argparse.Namespace) -> int:
    capabilities = collect_agent_capabilities(Path(args.repo_root), check_network=args.check_network)
    if args.json:
        print(json.dumps(capabilities, indent=2, sort_keys=True))
    else:
        print(f"recommended_mode: {capabilities['recommended_mode']}")
        for name, item in sorted((capabilities.get("core") or {}).items()):
            status = "available" if item.get("available") else "missing"
            print(f"core.{name}: {status}")
        for name, item in sorted((capabilities.get("wrappers") or {}).items()):
            status = "available" if item.get("available") else "missing"
            suffix = ""
            if "reachable" in item:
                suffix = f", reachable={bool(item.get('reachable'))}"
            print(f"wrapper.{name}: {status}, required={bool(item.get('required'))}{suffix}")
    return 0 if (capabilities.get("core") or {}).get("pga", {}).get("available") else 1


def _cmd_agent_doctor(args: argparse.Namespace) -> int:
    result = collect_agent_doctor(Path(args.repo_root), check_network=args.check_network, skip_tests=args.skip_tests)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for check in result["checks"]:
            status = "skipped" if check.get("skipped") else "passed" if check.get("passed") else "failed"
            print(f"{check['name']}: {status}")
        print(f"recommended_mode: {result['capabilities']['recommended_mode']}")
    return 0 if result["passed"] else 1


def _cmd_vcs_ready(args: argparse.Namespace) -> int:
    result = collect_vcs_readiness(
        Path(args.repo_root),
        args.ticket,
        target_branch=args.target_branch,
        remote=args.remote,
        skip_tests=args.skip_tests,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"ticket: {result['ticket_id']} ({result['ticket_status']})")
        print(f"branch: {result['current_branch']}")
        print(f"expected_branch: {result['expected_branch']}")
        print(f"target_branch: {result['target_branch']}")
        print(f"validation_passed: {result['validation_passed']}")
        print(f"ready_for_commit: {result['ready_for_commit']}")
        print(f"ready_for_merge: {result['ready_for_merge']}")
        for warning in result["warnings"]:
            print(f"warning: {warning}")
        print("standard_commands:")
        for command in result["standard_commands"]:
            print(f"- {command}")
    return 0 if result["ready_for_commit"] else 1


def _cmd_release_check(args: argparse.Namespace) -> int:
    result = collect_release_readiness(Path(args.repo_root), ticket_id=args.ticket, skip_tests=args.skip_tests)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        package = result["package"]
        print(f"package: {package.get('name')} {package.get('version')}")
        print(f"requires_python: {package.get('requires_python')}")
        print(f"validation_passed: {result['validation_passed']}")
        print(f"ready_for_release_prep: {result['ready_for_release_prep']}")
        print("validation_commands:")
        for item in result.get("validation_results") or []:
            status = "skipped" if item.get("skipped") else "passed" if item.get("passed") else "failed"
            print(f"- {item['command']}: {status}")
        print("planning_bridge:")
        for path, exists in result["planning_bridge"].items():
            print(f"- {path}: {'present' if exists else 'missing'}")
        regression = result["regression_report"]
        print(f"regression_report: {regression.get('path')} ({regression.get('test_count')} tests)")
        print("required_release_note_fields:")
        for field in result["required_release_note_fields"]:
            print(f"- {field}")
    return 0 if result["ready_for_release_prep"] else 1


def _cmd_artemis_config_show(args: argparse.Namespace) -> int:
    config = load_artemis_config(Path(args.repo_root), Path(args.config) if args.config else None)
    if args.json:
        print(json.dumps(config, indent=2, sort_keys=True))
    else:
        print(dump_config_yaml(config))
    return 0


def _cmd_artemis_config_validate(args: argparse.Namespace) -> int:
    config = validate_artemis_config(Path(args.repo_root), Path(args.config) if args.config else None)
    print(f"validated artemis config {config['name']} {config['version']}")
    return 0


def _cmd_artemis_capabilities(args: argparse.Namespace) -> int:
    capabilities = collect_artemis_capabilities(
        Path(args.repo_root),
        check_network=args.check_network,
        config_path=Path(args.config) if args.config else None,
    )
    if args.json:
        print(json.dumps(capabilities, indent=2, sort_keys=True))
    else:
        print(f"artemis: {capabilities['version']}")
        print(f"recommended_mode: {capabilities['recommended_mode']}")
        print("modes:")
        for mode_name in sorted(capabilities.get("modes") or {}):
            mode = capabilities["modes"][mode_name]
            print(f"- {mode_name}: can_modify_repo={bool(mode.get('can_modify_repo'))}")
        print(f"tools: {capabilities['tools']['count']}")
        for tool_id, policy in sorted((capabilities["tools"].get("policy") or {}).items()):
            print(f"- {tool_id}: risk={policy['risk']}, modes={','.join(policy['modes'])}")
    return 0


def _cmd_analyst_view_build(args: argparse.Namespace) -> int:
    payload = read_json(Path(args.input))
    view = build_view(
        Path(args.repo_root),
        args.template,
        payload,
        as_of=args.as_of,
        allow_fixture=args.allow_fixture,
    )
    write_json(Path(args.output), view)
    print(f"wrote {view['view_type']} view to {args.output}")
    return 0


def _cmd_data_sources_list(args: argparse.Namespace) -> int:
    payload = validate_data_sources(Path(args.registry), Path(args.schemas))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for source_id, item in sorted((payload.get("data_sources") or {}).items()):
            print(f"{source_id}: kind={item['kind']}, required={bool(item['required'])}")
    return 0


def _cmd_data_sources_validate(args: argparse.Namespace) -> int:
    payload = validate_data_sources(Path(args.registry), Path(args.schemas))
    env_names = credential_env_names(payload)
    print(f"validated {len(payload.get('data_sources') or {})} data sources; credential_env_names={len(env_names)}")
    return 0


def _cmd_skill_validate(args: argparse.Namespace) -> int:
    result = validate_skill_manifest(Path(args.repo_root), Path(args.schemas))
    print(f"validated {result['skills']} skills")
    return 0


def _cmd_views_validate(args: argparse.Namespace) -> int:
    result = validate_view_manifest(Path(args.repo_root), Path(args.schemas))
    print(f"validated {result['templates']} view templates")
    return 0


def _cmd_dev_context(args: argparse.Namespace) -> int:
    context = collect_development_context(Path(args.repo_root), args.ticket, Path(args.config) if args.config else None)
    if args.output:
        write_json(Path(args.output), context)
        print(f"wrote development context for {args.ticket} to {args.output}")
    else:
        print(json.dumps(context, indent=2, sort_keys=True))
    return 0


def _cmd_dev_plan(args: argparse.Namespace) -> int:
    context = collect_development_context(Path(args.repo_root), args.ticket, Path(args.config) if args.config else None)
    ticket = context["ticket"]
    print(f"ticket: {ticket['id']}")
    print(f"title: {ticket['title']}")
    print("tasks:")
    for task in ticket.get("tasks") or []:
        print(f"- {task}")
    return 0


def _cmd_dev_propose(args: argparse.Namespace) -> int:
    validate_coding_backends(Path(args.repo_root))
    print(f"proposal request accepted for {args.ticket}; backend={args.backend}; repo mutation remains approval-gated")
    return 0


def _cmd_release_candidate(args: argparse.Namespace) -> int:
    candidate = build_release_candidate(Path(args.repo_root), args.ticket, target_version=args.target_version)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml.safe_dump(candidate, sort_keys=False), encoding="utf-8")
        print(f"wrote release candidate to {args.output}")
    else:
        print(yaml.safe_dump(candidate, sort_keys=False))
    return 0


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog or Path(sys.argv[0]).name or "artemis")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-registries")
    p.add_argument("--registries", default="registries")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_validate_registries)

    p = sub.add_parser("parse-period")
    p.add_argument("label")
    p.add_argument("--commodity", default="generic", choices=["generic", "power", "gas"])
    p.set_defaults(func=_cmd_parse_period)

    p = sub.add_parser("normalize-prices")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=_cmd_normalize_prices)

    p = sub.add_parser("normalize-positions")
    p.add_argument("--positions", required=True)
    p.add_argument("--marks")
    p.add_argument("--output", required=True)
    p.set_defaults(func=_cmd_normalize_positions)

    p = sub.add_parser("run-pnl-attribution")
    p.add_argument("--prior", required=True)
    p.add_argument("--current", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--run-id", default="pnl-run")
    p.set_defaults(func=_cmd_run_pnl)

    p = sub.add_parser("run-var")
    p.add_argument("--positions", required=True)
    p.add_argument("--returns", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--run-id", default="var-run")
    p.set_defaults(func=_cmd_run_var)

    p = sub.add_parser("run-greeks")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--run-id", default="greeks-run")
    p.set_defaults(func=_cmd_run_greeks)

    p = sub.add_parser("build-state-pack")
    p.add_argument("--state-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--artifacts", required=True)
    p.add_argument("--publish", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--shared-readonly", action="store_true")
    p.set_defaults(func=_cmd_build_state_pack)

    p = sub.add_parser("work-context")
    p.add_argument("--ticket", required=True)
    p.add_argument("--config")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output")
    p.set_defaults(func=_cmd_work_context)

    p = sub.add_parser("validate-work-items")
    p.add_argument("--work-root", default="work")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_validate_work_items)

    p = sub.add_parser("validate-kb")
    p.add_argument("--kb-root", default="knowledge_base")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_validate_kb)

    p = sub.add_parser("agent-capabilities")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--check-network", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_agent_capabilities)

    p = sub.add_parser("agent-doctor")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--check-network", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--skip-tests", action="store_true")
    p.set_defaults(func=_cmd_agent_doctor)

    p = sub.add_parser("vcs-ready")
    p.add_argument("--ticket", required=True)
    p.add_argument("--repo-root", default=".")
    p.add_argument("--target-branch", default="main")
    p.add_argument("--remote", default="origin")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_vcs_ready)

    p = sub.add_parser("release-check")
    p.add_argument("--ticket")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_release_check)

    p = sub.add_parser("capabilities")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--config")
    p.add_argument("--check-network", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_artemis_capabilities)

    p = sub.add_parser("config")
    config_sub = p.add_subparsers(dest="config_command", required=True)
    c = config_sub.add_parser("show")
    c.add_argument("--repo-root", default=".")
    c.add_argument("--config")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=_cmd_artemis_config_show)
    c = config_sub.add_parser("validate")
    c.add_argument("--repo-root", default=".")
    c.add_argument("--config")
    c.set_defaults(func=_cmd_artemis_config_validate)

    p = sub.add_parser("analyst")
    analyst_sub = p.add_subparsers(dest="analyst_command", required=True)
    view = analyst_sub.add_parser("view")
    view_sub = view.add_subparsers(dest="view_command", required=True)
    b = view_sub.add_parser("build")
    b.add_argument("--template", required=True)
    b.add_argument("--as-of")
    b.add_argument("--input", required=True)
    b.add_argument("--output", required=True)
    b.add_argument("--repo-root", default=".")
    b.add_argument("--allow-fixture", action="store_true")
    b.set_defaults(func=_cmd_analyst_view_build)

    p = sub.add_parser("data-sources")
    ds_sub = p.add_subparsers(dest="data_sources_command", required=True)
    d = ds_sub.add_parser("list")
    d.add_argument("--registry", default="registries/data_sources.yaml")
    d.add_argument("--schemas", default="schemas")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_data_sources_list)
    d = ds_sub.add_parser("validate")
    d.add_argument("--registry", default="registries/data_sources.yaml")
    d.add_argument("--schemas", default="schemas")
    d.set_defaults(func=_cmd_data_sources_validate)

    p = sub.add_parser("skill")
    skill_sub = p.add_subparsers(dest="skill_command", required=True)
    s = skill_sub.add_parser("validate")
    s.add_argument("--repo-root", default=".")
    s.add_argument("--schemas", default="schemas")
    s.set_defaults(func=_cmd_skill_validate)

    p = sub.add_parser("views")
    views_sub = p.add_subparsers(dest="views_command", required=True)
    v = views_sub.add_parser("validate")
    v.add_argument("--repo-root", default=".")
    v.add_argument("--schemas", default="schemas")
    v.set_defaults(func=_cmd_views_validate)

    p = sub.add_parser("dev")
    dev_sub = p.add_subparsers(dest="dev_command", required=True)
    d = dev_sub.add_parser("context")
    d.add_argument("--ticket", required=True)
    d.add_argument("--repo-root", default=".")
    d.add_argument("--config")
    d.add_argument("--output")
    d.set_defaults(func=_cmd_dev_context)
    d = dev_sub.add_parser("plan")
    d.add_argument("--ticket", required=True)
    d.add_argument("--repo-root", default=".")
    d.add_argument("--config")
    d.set_defaults(func=_cmd_dev_plan)
    d = dev_sub.add_parser("propose")
    d.add_argument("--ticket", required=True)
    d.add_argument("--backend", default="human")
    d.add_argument("--repo-root", default=".")
    d.set_defaults(func=_cmd_dev_propose)

    p = sub.add_parser("release")
    release_sub = p.add_subparsers(dest="release_command", required=True)
    r = release_sub.add_parser("check")
    r.add_argument("--ticket")
    r.add_argument("--repo-root", default=".")
    r.add_argument("--skip-tests", action="store_true")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_cmd_release_check)
    r = release_sub.add_parser("candidate")
    r.add_argument("--ticket", required=True)
    r.add_argument("--repo-root", default=".")
    r.add_argument("--target-version", default="0.2.0")
    r.add_argument("--output")
    r.set_defaults(func=_cmd_release_candidate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
