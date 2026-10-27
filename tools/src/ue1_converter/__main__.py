"""Local source inspection and source-space coordinate validation commands."""

import argparse
import json
from pathlib import Path
import sys

from .brush_audit import audit_brushes
from .inspection import inspect_document
from .geometry import extract_geometry,write_bundle
from .t3d import parse_t3d


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and validate local UE1 exports without importing them")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect-t3d", help="inventory a UE1 map export and flag ambiguities")
    inspect.add_argument("--encoding", default="utf-8", help="explicit source text codec (default: utf-8)")
    validate = commands.add_parser("validate-brushes", help="bind binary numeric evidence and audit source brush transforms")
    extract = commands.add_parser("extract-bsp", help="extract the original compiled BSP into a private geometry bundle")
    extract.add_argument("--output-dir",type=Path,required=True,help="new destination directory; existing paths are refused")
    extract.set_defaults(output=None,force=False)
    for command in (validate,extract):
        command.add_argument("--package", type=Path, required=True, help="original binary map, read only")
        command.add_argument("--baseline", type=Path, help="original-map hash sidecar; defaults beside source")
        command.add_argument("--export-summary", type=Path, help="export hash sidecar; defaults beside source")
    for command in (inspect, validate, extract):
        command.add_argument("source", type=Path)
        if command is not extract:
            command.add_argument("--output", "-o", type=Path, help="write private JSON; otherwise print JSON")
            command.add_argument("--force", action="store_true", help="replace an existing report")
    args = parser.parse_args(argv)
    try:
        protected = [args.source]
        if args.command != "inspect-t3d":
            args.baseline = args.baseline or args.source.with_suffix(".source-baseline.json")
            args.export_summary = args.export_summary or args.source.with_suffix(".export-summary.json")
            protected += [args.package, args.baseline, args.export_summary]
        if args.output and any(args.output.resolve() == path.resolve() or
                               (args.output.exists() and path.exists() and args.output.samefile(path))
                               for path in protected):
            raise ValueError("output must not overwrite the source export or another input")
        data = args.source.read_bytes()
        if args.command == "inspect-t3d":
            report = inspect_document(parse_t3d(data.decode(args.encoding)), args.source.name, data, args.encoding)
        else:
            baseline = json.loads(args.baseline.read_text())
            summary = json.loads(args.export_summary.read_text())
            package_path = str(args.package.resolve())
            if not isinstance(baseline, dict) or not isinstance(baseline.get(package_path), str):
                raise ValueError("baseline does not identify the selected original map path")
            if not isinstance(summary, dict) or not isinstance(summary.get("sha256"), str):
                raise ValueError("export summary does not contain a source checksum")
            operation = audit_brushes if args.command == "validate-brushes" else extract_geometry
            report = operation(data, args.package.read_bytes(), args.source.name,
                               summary["sha256"], baseline[package_path])
            if args.command == "extract-bsp":
                write_bundle(report,args.output_dir)
                print(f"Wrote {args.output_dir}: {report['diagnostics']['reachable_nodes']} native BSP nodes, "
                      f"{report['diagnostics']['render_triangles']} untextured render triangles; no UE5 import.")
                return 0
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("w" if args.force else "x", encoding="utf-8") as output:
                output.write(payload)
            if args.command == "inspect-t3d":
                print(f"Wrote {args.output}: {report['counts']['actors']} actors, "
                      f"{report['counts']['source_polygons']} source polygons, "
                      f"{len(report['diagnostics'])} warnings; CSG and camera behavior not evaluated.")
            else:
                print(f"Wrote {args.output}: {report['counts']['brush_instances']} coordinate audits, "
                      f"{report['counts']['corrected_components']} binary-backed components; no evaluated BSP or mesh.")
        else:
            print(payload, end="")
    except (OSError, ValueError, LookupError) as error:
        print(f"{args.command}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
