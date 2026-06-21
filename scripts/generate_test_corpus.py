#!/usr/bin/env python3
"""Generate a local document corpus for scale and memory testing."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import fitz

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "eval" / "corpus" / "generated"

LEGAL_PARAGRAPH = (
    "Master service agreement between the parties. This contract defines jurisdiction, "
    "liability, and indemnification clauses. Contact privacy@example.com or call "
    "(617) 555-0142 for legal notices. Employee Jane Doe signed on behalf of Acme Corp."
)

FINANCE_PARAGRAPH = (
    "Quarterly invoice summary with payment totals, tax lines, and ledger balance "
    "adjustments. Account holder John Smith, SSN 123-45-6789, billing ref INV-2024-991."
)

POLICY_PARAGRAPH = (
    "Written information security plan covering access control, incident response, "
    "and data retention. Systems in Massachusetts store customer records under 201 CMR 17.00."
)


def _write_text(path: Path, paragraphs: int) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = [LEGAL_PARAGRAPH, FINANCE_PARAGRAPH, POLICY_PARAGRAPH]
    body = "\n\n".join(blocks[i % len(blocks)] for i in range(paragraphs))
    path.write_text(body, encoding="utf-8")
    return len(body.encode("utf-8"))


def _write_pdf(path: Path, pages: int) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    blocks = [LEGAL_PARAGRAPH, FINANCE_PARAGRAPH, POLICY_PARAGRAPH]
    for page_index in range(pages):
        page = doc.new_page()
        text = f"Page {page_index + 1}\n\n{blocks[page_index % len(blocks)]}"
        page.insert_text((72, 72), text)
    doc.save(path)
    size_bytes = path.stat().st_size
    doc.close()
    return size_bytes


def build_corpus(output_dir: Path) -> dict:
    specs: list[tuple[str, str, int]] = [
        ("text/tiny-1p.txt", "text", 1),
        ("text/small-3p.txt", "text", 3),
        ("text/medium-10p.txt", "text", 10),
        ("text/large-30p.txt", "text", 30),
        ("pdf/tiny-1p.pdf", "pdf", 1),
        ("pdf/small-5p.pdf", "pdf", 5),
        ("pdf/medium-10p.pdf", "pdf", 10),
        ("pdf/large-17p.pdf", "pdf", 17),
        ("pdf/xlarge-50p.pdf", "pdf", 50),
    ]

    entries: list[dict] = []
    for relative_path, kind, units in specs:
        target = output_dir / relative_path
        if kind == "text":
            size_bytes = _write_text(target, units)
            pages = units
        else:
            size_bytes = _write_pdf(target, units)
            pages = units
        entries.append(
            {
                "path": relative_path,
                "kind": kind,
                "pages": pages,
                "size_bytes": size_bytes,
            }
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(output_dir),
        "file_count": len(entries),
        "files": entries,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    manifest = build_corpus(args.output.resolve())
    print(json.dumps(manifest, indent=2))
    print(f"\nWrote {manifest['file_count']} files under {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
