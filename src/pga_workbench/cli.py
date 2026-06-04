from __future__ import annotations

import argparse
from pathlib import Path

from .core.time import utc_now_iso
from .models import RunManifest
from .periods import parse_period
from .registry import validate_registries
from .serialization import read_json, to_plain, write_json
from .services.greeks import read_option_rows, run_black76_greeks
from .services.normalization import normalize_marks, normalize_positions, read_csv_rows
from .services.pnl import run_pnl_attribution
from .services.risk import read_historical_returns, run_historical_var
from .state.packs import build_candidate_state_pack, publish_candidate_state_pack
from .agent_runtime.context_loader import collect_context
from .agent_runtime.work_item_loader import validate_work_items


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
    context = collect_context(Path(args.repo_root), args.ticket, Path(args.config))
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pga")
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
    p.add_argument("--config", default="local/llm_config.example.yaml")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output")
    p.set_defaults(func=_cmd_work_context)

    p = sub.add_parser("validate-work-items")
    p.add_argument("--work-root", default="work")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_validate_work_items)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
