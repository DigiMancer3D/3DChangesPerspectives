#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from swar.parser import SwarParser
from swar.renderer_html import render_doc_html
from swar.outline import export_outline
from swar.udata import UData
from swar.gui_shell import run_shell


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SWAR v0.7.1-rc1-r3 - Script Writer and Reader")
    parser.add_argument("file", nargs="?", help=".script, .md, .txt, or .arcs file to open")
    parser.add_argument("--reader", action="store_true", help="Launch SWAR shell in reader-only/local-only mode")
    parser.add_argument("--standard", action="store_true", help="Launch SWAR shell in standard reader/editor mode")
    parser.add_argument("--theme", default=None, help="Theme name")
    parser.add_argument("--udata", default="SWAR.udata", help="Path to SWAR.udata")
    parser.add_argument("--render-html", metavar="OUT.html", help="Render file to standalone local HTML preview")
    parser.add_argument("--outline", action="store_true", help="Export outline txt next to input file")
    parser.add_argument("--parse-summary", action="store_true", help="Print parser block summary")
    args = parser.parse_args(argv)

    udata = UData.load(args.udata)
    udata.apply_theme_overrides()
    udata.bump_counter("startup_count")
    udata.save()
    theme_name = args.theme or udata.get_theme_name()

    if args.reader:
        return run_shell(args.file, udata_path=args.udata, reader_only=True)
    if args.standard:
        return run_shell(args.file, udata_path=args.udata, reader_only=False)

    if not args.file:
        parser.print_help()
        return 0

    doc = SwarParser().parse_file(args.file)

    if args.parse_summary:
        print(f"Header: {doc.header_first_line}")
        print(f"Blocks: {len(doc.blocks)}")
        print(f"Sections: {doc.section_count}")
        print(f"Public source links: {len(doc.source_links)}")
        for b in doc.blocks[:100]:
            preview = b.text.replace("\n", " ")[:80]
            print(f"{b.line_start:>4}-{b.line_end:<4} {b.kind:<22} lvl={b.level:<2} {preview}")

    if args.outline:
        out = export_outline(doc, args.file)
        print(f"Exported outline: {out}")

    if args.render_html:
        html = render_doc_html(doc, theme_name, allow_online_links=False)
        out = Path(args.render_html)
        out.write_text(html, encoding="utf-8")
        print(f"Rendered HTML: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
