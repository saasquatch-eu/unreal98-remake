"""Run with python -m ue1_converter inspect-t3d <original-name.t3d>."""

import argparse
import json
from pathlib import Path
import sys

from .inspection import inspect_document
from .t3d import parse_t3d


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect local UE1 source exports without converting them")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect-t3d", help="inventory a UE1 map export and flag ambiguities")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--encoding", default="utf-8", help="explicit source text codec (default: utf-8)")
    inspect.add_argument("--output", "-o", type=Path, help="write private JSON; otherwise print JSON")
    inspect.add_argument("--force", action="store_true", help="replace an existing report")
    args = parser.parse_args(argv)
    try:
        if args.output and (args.output.resolve() == args.source.resolve() or
                            (args.output.exists() and args.output.samefile(args.source))):
            raise ValueError("output must not overwrite the source export")
        data = args.source.read_bytes()
        document = parse_t3d(data.decode(args.encoding))
        report = inspect_document(document, args.source.name, data, args.encoding)
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            # Parse first, then open exclusively unless replacement was requested.
            with args.output.open("w" if args.force else "x", encoding="utf-8") as output:
                output.write(payload)
            print(f"Wrote {args.output}: {report['counts']['actors']} actors, "
                  f"{report['counts']['source_polygons']} source polygons, "
                  f"{len(report['diagnostics'])} warnings; CSG and camera behavior not evaluated.")
        else:
            print(payload, end="")
    except (OSError, ValueError, LookupError) as error:
        print(f"inspect-t3d: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
