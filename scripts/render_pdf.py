"""Render a Markdown document to a print-ready PDF, with its figures embedded.

    uv run python scripts/render_pdf.py DATASET_DESCRIPTION.md

Writes the PDF next to the source unless -o is given. This exists because the manuscript
sections are drafted in Markdown but circulated to co-authors and reviewers as PDF, and because
a document whose whole argument rests on eight figures is useless if they do not travel with it.

Pipeline: Markdown -> HTML (python-markdown, with the table and footnote extensions) -> PDF
(headless Chrome). Chrome is used rather than pandoc/LaTeX because neither is installed here,
and rather than a pure-Python writer because the text is full of typographic characters the
analysis produces -- W/m^2 with a superscript, en dashes in ranges, minus signs, Greek theta,
Turkish diacritics -- and a browser engine gets all of them right with the fonts already on the
machine.

Images are inlined as data URIs rather than linked. That makes the intermediate HTML
self-contained, so it does not matter what working directory Chrome is launched from and the
file can be mailed to a co-author as-is.
"""
import argparse
import base64
import mimetypes
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Chrome's own binary name varies by install; these are the ones seen on Linux and macOS.
CHROME_CANDIDATES = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

# Body is serif (a manuscript convention) and headings sans, both from families that ship with
# the machine and cover Latin Extended-A, so "Türkiye" and "θ_z" render rather than tofu.
STYLE = """
@page { size: A4; margin: 20mm 18mm 18mm 18mm; }
body {
  font-family: "DejaVu Serif", "Liberation Serif", Georgia, serif;
  font-size: 10.5pt; line-height: 1.5; color: #111; max-width: 100%;
  hyphens: auto; text-align: justify;
}
h1, h2, h3 {
  font-family: "DejaVu Sans", "Liberation Sans", Helvetica, sans-serif;
  color: #000; line-height: 1.25; break-after: avoid; page-break-after: avoid;
}
h1 { font-size: 20pt; margin: 0 0 1.2em 0; border-bottom: 2px solid #111; padding-bottom: 0.3em; }
h2 { font-size: 13pt; margin: 1.8em 0 0.6em 0; }
h3 { font-size: 11pt; margin: 1.4em 0 0.5em 0; }
p { margin: 0 0 0.7em 0; orphans: 3; widows: 3; }
strong { color: #000; }

/* Figures: never split an image from the caption that explains it. */
img { max-width: 100%; height: auto; display: block; margin: 1.0em auto 0.4em auto; }
p > img { break-inside: avoid; page-break-inside: avoid; }
p:has(img) { break-inside: avoid; page-break-inside: avoid; break-after: avoid; }

table {
  border-collapse: collapse; width: 100%; margin: 0.8em 0 1.2em 0;
  font-family: "DejaVu Sans", "Liberation Sans", sans-serif; font-size: 8.5pt;
}
/* A long table may span pages -- forbidding it strands half a page of white space -- but a
   ROW must never split, and the header repeats on each page it continues onto. */
tr { break-inside: avoid; page-break-inside: avoid; }
thead { display: table-header-group; }
th, td { border: 0.5pt solid #b8b8b8; padding: 3.5pt 5pt; text-align: left; vertical-align: top; }
th { background: #eeeeee; font-weight: 600; }
/* Alignment is decided per column from the content, not by position: right for numeric
   columns, left for prose. See _align_numeric_columns. */
td.num, th.num { text-align: right; }
tbody tr:nth-child(even) { background: #fafafa; }

blockquote {
  margin: 0.8em 0 0.8em 1.2em; padding-left: 0.9em; border-left: 2.5pt solid #bbb;
  color: #333; font-style: italic;
}
ol, ul { margin: 0 0 0.8em 0; padding-left: 1.4em; }
li { margin-bottom: 0.3em; }
hr { border: none; border-top: 0.5pt solid #ccc; margin: 1.6em 0; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; }
"""

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>{style}</style></head><body>{body}</body></html>
"""


def _find_chrome() -> str:
    for name in CHROME_CANDIDATES:
        found = shutil.which(name) or (name if Path(name).exists() else None)
        if found:
            return found
    raise SystemExit(
        "No Chrome/Chromium binary found. Tried: " + ", ".join(CHROME_CANDIDATES)
    )


def _inline_images(html: str, base_dir: Path) -> str:
    """Replace every local <img src> with a data URI, so the HTML stands alone."""
    missing = []

    def repl(match: "re.Match") -> str:
        src = match.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return match.group(0)
        path = (base_dir / src).resolve()
        if not path.exists():
            missing.append(src)
            return match.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'src="data:{mime};base64,{payload}"'

    out = re.sub(r'src="([^"]+)"', repl, html)
    if missing:
        raise SystemExit(
            "These images are referenced but do not exist:\n  " + "\n  ".join(missing)
        )
    return out


NUMERIC = re.compile(r"^[−\-+]?[\d,]+(?:\.\d+)?\s*%?$")


def _align_numeric_columns(html: str) -> str:
    """Right-align a table column only when its body cells are actually numbers.

    Aligning every column but the first, which is the usual shortcut, right-aligns prose: in the
    variable table the "Description" column is text and came out ragged-left against the border.
    Deciding per column from the content keeps numbers aligned on the decimal and leaves
    sentences alone.
    """

    def fix_table(table: str) -> str:
        rows = re.findall(r"<tr>(.*?)</tr>", table, flags=re.S)
        body = rows[1:] if len(rows) > 1 else []
        cells = [re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S) for r in body]
        if not cells:
            return table
        width = max(len(c) for c in cells)
        numeric = []
        for col in range(width):
            values = [re.sub(r"<[^>]+>", "", c[col]).strip()
                      for c in cells if len(c) > col]
            values = [v for v in values if v and v != "—"]
            numeric.append(bool(values) and all(NUMERIC.match(v) for v in values))

        def fix_row(match: "re.Match") -> str:
            inner, col = match.group(1), 0
            def tag(m: "re.Match") -> str:
                nonlocal col
                name, rest, content = m.group(1), m.group(2), m.group(3)
                cls = ' class="num"' if col < width and numeric[col] else ""
                col += 1
                return f"<{name}{rest}{cls}>{content}</{name}>"
            return "<tr>" + re.sub(r"<(t[dh])([^>]*)>(.*?)</\1>", tag, inner, flags=re.S) + "</tr>"

        return re.sub(r"<tr>(.*?)</tr>", fix_row, table, flags=re.S)

    return re.sub(r"<table>.*?</table>", lambda m: fix_table(m.group(0)), html, flags=re.S)


def render(source: Path, output: Path) -> None:
    import markdown

    text = source.read_text(encoding="utf-8")
    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "footnotes", "attr_list", "sane_lists"]
    )
    n_images = body.count("<img ")
    body = _align_numeric_columns(body)
    body = _inline_images(body, source.parent)

    title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("# ")),
                 source.stem)
    html = HTML.format(title=title, style=STYLE, body=body)

    chrome = _find_chrome()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "document.html"
        html_path.write_text(html, encoding="utf-8")
        # --no-pdf-header-footer drops Chrome's URL/date furniture, which has no place on a
        # manuscript page. A throwaway profile dir keeps this from touching the user's browser.
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={tmp}/profile", "--no-pdf-header-footer",
             "--virtual-time-budget=10000",
             f"--print-to-pdf={output}", html_path.as_uri()],
            check=True, capture_output=True, timeout=180,
        )
    if not output.exists():
        raise SystemExit(f"Chrome reported success but {output} was not written.")
    size_kb = output.stat().st_size / 1024
    print(f"{output}  ({size_kb:,.0f} KB, {n_images} figures embedded)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="Markdown file to render")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output PDF (default: alongside the source)")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.exists():
        raise SystemExit(f"No such file: {source}")
    render(source, (args.output or source.with_suffix(".pdf")).resolve())


if __name__ == "__main__":
    main()
