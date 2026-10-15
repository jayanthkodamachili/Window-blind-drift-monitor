"""Render the committed architecture SVG.

Hand written rather than produced by a diagramming library, for the reasons in ADR-004: a
committed SVG with intrinsic dimensions and an explicit light background renders the same
on GitHub in either theme, which a Mermaid fence does not reliably do.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture.svg"

W, H = 960, 500
INK = "#1b1f23"
MUTED = "#57606a"
BAD = "#b42318"
GOOD = "#116329"
LINE = "#8c959f"


def box(x, y, w, h, title, subtitle="", stroke=MUTED, fill="#ffffff", bold=False):
    weight = "600" if bold else "400"
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.5"/>',
        f'<text x="{x + w / 2}" y="{y + (20 if subtitle else h / 2 + 4)}" '
        f'text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="13" '
        f'font-weight="{weight}" fill="{INK}">{title}</text>',
    ]
    if subtitle:
        for index, line in enumerate(subtitle.split("|")):
            parts.append(
                f'<text x="{x + w / 2}" y="{y + 38 + index * 14}" text-anchor="middle" '
                f'font-family="Helvetica,Arial,sans-serif" font-size="11" '
                f'fill="{MUTED}">{line}</text>'
            )
    return "".join(parts)


def arrow(x1, y1, x2, y2, dashed=False):
    dash = ' stroke-dasharray="4 3"' if dashed else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" '
        f'stroke-width="1.5" marker-end="url(#a)"{dash}/>'
    )


def label(x, y, text, fill=MUTED, size=11, anchor="middle", weight="400"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{text}</text>'
    )


def render() -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Architecture of window-blind-drift-monitor">',
        '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
        f'markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/>'
        "</marker></defs>",
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        label(
            W / 2, 26,
            "Two paths from one window: what fired, and what could have fired",
            INK, 14, weight="600",
        ),
    ]

    parts.append(box(24, 56, 196, 54, "reference window", "the stable baseline"))
    parts.append(box(24, 134, 196, 54, "detection window",
                     "n rows, and n decides|everything below", bold=True))
    parts.append(arrow(122, 110, 122, 134))

    # Upper path: the ordinary drift report.
    parts.append(box(286, 70, 290, 56, "run a detector per feature",
                     "KS, chi-square or PSI"))
    parts.append(box(286, 150, 290, 56, "apply a multiplicity correction",
                     "lowers alpha, raises the floor"))
    parts.append(arrow(220, 150, 286, 98))
    parts.append(arrow(576, 126, 431, 150))

    # Lower path: the thing an ordinary report omits.
    parts.append(box(286, 258, 290, 68, "bisect on shift size until power hits target",
                     "what is the smallest shift|this window could have seen?",
                     stroke=GOOD, fill="#f2fbf4", bold=True))
    parts.append(arrow(220, 178, 286, 282))

    parts.append(box(646, 70, 180, 56, "fired", "an alarm to read"))
    parts.append(box(646, 150, 180, 56, "did not fire", "two meanings",
                     stroke=BAD, fill="#fff5f4", bold=True))
    parts.append(box(646, 258, 180, 68, "detection floor",
                     "vs what would matter", stroke=GOOD, fill="#f2fbf4"))
    parts.append(arrow(576, 90, 646, 90))
    parts.append(arrow(576, 186, 646, 178))
    parts.append(arrow(576, 292, 646, 292))

    parts.append(
        box(150, 392, 660, 78,
            "silence means nothing until the floor is known",
            "floor below what matters: nothing moved|"
            "floor above what matters: the monitor could not have seen it either way",
            bold=True)
    )
    parts.append(arrow(736, 206, 600, 392))
    parts.append(arrow(736, 326, 480, 392))

    parts.append(label(253, 128, "same", MUTED, 10))
    parts.append(label(253, 140, "window", MUTED, 10))

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render() + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
