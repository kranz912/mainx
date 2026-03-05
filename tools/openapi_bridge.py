from __future__ import annotations

import argparse

from maix.openapi_bridge import (
    export_maix_to_openapi,
    import_openapi_to_maix_config,
    load_api_document,
    write_api_document,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="MAIX OpenAPI bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import OpenAPI to MAIX YAML format")
    import_parser.add_argument("--input", required=True, help="OpenAPI file path (.yaml/.yml/.json)")
    import_parser.add_argument("--output", required=True, help="MAIX config output path (.yaml/.yml/.json)")

    export_parser = subparsers.add_parser("export", help="Export MAIX config to OpenAPI subset")
    export_parser.add_argument("--input", required=True, help="MAIX config file path")
    export_parser.add_argument("--output", required=True, help="OpenAPI output path (.yaml/.yml/.json)")
    export_parser.add_argument("--title", default="MAIX Export", help="OpenAPI info.title")
    export_parser.add_argument("--version", default="1.0.0", help="OpenAPI info.version")

    args = parser.parse_args()

    source = load_api_document(args.input)
    if args.command == "import":
        output = import_openapi_to_maix_config(source)
    else:
        output = export_maix_to_openapi(source, title=args.title, version=args.version)

    write_api_document(args.output, output)


if __name__ == "__main__":
    main()
