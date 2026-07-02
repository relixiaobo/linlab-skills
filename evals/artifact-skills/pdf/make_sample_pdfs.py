#!/usr/bin/env python3
"""Create deterministic PDF samples for pdf skill evals."""

from pathlib import Path

from pypdf import PdfWriter


BASE = Path(__file__).resolve().parent / "source"


def write_blank(path: Path, pages: int, title: str) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=200)
    writer.add_metadata({"/Title": title, "/Producer": "linlab pdf eval generator"})
    with path.open("wb") as fh:
        writer.write(fh)


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    write_blank(BASE / "one_page.pdf", 1, "One Page Eval PDF")
    write_blank(BASE / "two_page.pdf", 2, "Two Page Eval PDF")
    write_blank(BASE / "source_report.pdf", 2, "Source Report Eval PDF")


if __name__ == "__main__":
    main()
