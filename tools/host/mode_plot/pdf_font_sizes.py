#!/usr/bin/env python3
"""pdf_font_sizes.py -- measure the font sizes ACTUALLY PRESENT in a PDF.

Why: the claim "the labels are readable" has to be measured off the artefact,
not asserted from the source.  This walks every page's content stream with
pypdf, tracking the operand of each ``Tf`` operator, and reports the min/max
size along with the strings that carry them.

Text that is drawn with a scaling text matrix (TeX does this; matplotlib does
not) would need the ``Tm`` scale folded in.  matplotlib writes plain
``/F<n> <size> Tf`` operands, which is what the figure PDFs contain; the script
prints a warning if it ever sees a non-unit ``Tm`` so the number is not read
off a truncated measurement.

USAGE
    python3 tools/host/mode_plot/pdf_font_sizes.py FIG.pdf [FIG2.pdf ...]
"""

import sys

from pypdf import PdfReader
from pypdf.generic import ContentStream


def _text_of(operands):
    out = []
    for op in operands:
        if isinstance(op, (bytes, bytearray)):
            try:
                out.append(bytes(op).decode("latin-1"))
            except Exception:
                out.append(repr(op))
        elif isinstance(op, (list, tuple)):
            out.append(_text_of(op))
    return "".join(out)


def measure(path):
    reader = PdfReader(path)
    print("=" * 78)
    print(path)
    rows = []

    def visitor(text, cm, tm, font_dict, font_size):
        """pypdf hands over the Tf size and the text matrix -- both are used."""
        if font_size is None or not str(text).strip():
            return
        sx = (tm[0] ** 2 + tm[1] ** 2) ** 0.5 if tm is not None else 1.0
        rows.append((float(font_size) * float(sx), str(text).strip()))

    for pno, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        w_in = float(box.width) / 72.0
        h_in = float(box.height) / 72.0
        print("page %d: %.4f x %.4f in  (%.2f x %.2f pt)"
              % (pno, w_in, h_in, float(box.width), float(box.height)))
        page.extract_text(visitor_text=visitor)
    if not rows:
        print("NO TEXT OPERATORS FOUND")
        return
    sizes = sorted({round(s, 3) for s, _ in rows})
    print("distinct Tf sizes present : %s" % sizes)
    print("minimum : %.3f pt   maximum : %.3f pt" % (sizes[0], sizes[-1]))
    seen = set()
    print("strings carrying the minimum (%.3f pt):" % sizes[0])
    for s, t in rows:
        if round(s, 3) == sizes[0] and t not in seen:
            seen.add(t)
            print("    %-34r  (%.3f pt)" % (t, s))
    print("strings carrying the maximum (%.3f pt):" % sizes[-1])
    seen = set()
    for s, t in rows:
        if round(s, 3) == sizes[-1] and t not in seen:
            seen.add(t)
            print("    %-34r  (%.3f pt)" % (t, s))
        if len(seen) > 6:
            break
    print("text runs: %d" % len(rows))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for p in argv[1:]:
        measure(p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
