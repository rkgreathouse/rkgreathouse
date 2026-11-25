#!/usr/bin/env python3
"""Builds the figures in the profile README.

Usage: python3 scripts/build_figures.py

Writes assets/<figure>-dark.svg and assets/<figure>-light.svg. The colours are
Glacier Night Vivid, from the setup repo; light keeps the same hues, deepened
until they read on a white page. Figures have no background, so they sit
straight on GitHub's page in either theme.

Everything is plain SVG + SMIL so it animates inside an <img>: no scripts, no
external requests, fonts subset and inlined. Each figure opens as a skeleton
and settles into its content; the name types itself once.

The contributions figure is only built when data/contributions.json exists
(see fetch_contributions.py), and the README section for it is filled in then.
"""
import base64
import datetime
import io
import json
import pathlib
import re

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "scripts" / "fonts"
ASSETS = ROOT / "assets"
DATA = ROOT / "data" / "contributions.json"
README = ROOT / "README.md"

ICONS = json.loads((ROOT / "scripts" / "icons.json").read_text())
BRANDS, LINES = ICONS["brands"], ICONS["lines"]

# role: (variable font file, axis values, CSS family, CSS weight)
FONTS = {
    "display": ("BricolageGrotesque[opsz,wdth,wght].ttf", dict(wght=700, opsz=40, wdth=100), "RG Display", 700),
    "text": ("HankenGrotesk[wght].ttf", dict(wght=400), "RG Text", 400),
    "strong": ("HankenGrotesk[wght].ttf", dict(wght=600), "RG Text", 600),
    "mono": ("JetBrainsMono[wght].ttf", dict(wght=400), "RG Mono", 400),
}

SANS = "'RG Text',-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
DISPLAY = "'RG Display'," + SANS
MONO = "'RG Mono',ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

MODES = {
    "dark": dict(
        page="#0d1117", bright="#f6f8fc", fg="#dbe2ef", soft="#c3cbdc", muted="#939eb5",
        sk="#242a3b", skhi="#34405e", empty="#1f2535",
        orange="#f7884a", blue="#8ec5f5", cyan="#3fd3c4", green="#7fd09c", yellow="#e8b874",
        red="#f06f8c", pink="#e283c6", purple="#a98af0",
    ),
    "light": dict(
        page="#ffffff", bright="#10141f", fg="#2a3144", soft="#3d4660", muted="#5b6680",
        sk="#e6eaf2", skhi="#f5f7fb", empty="#e9edf5",
        orange="#b84c0a", blue="#1f6fb5", cyan="#0b857b", green="#27794c", yellow="#8f6410",
        red="#c2334f", pink="#aa3f90", purple="#6447c9",
    ),
}
C = MODES["dark"]
W, X0 = 880, 2
EASE_OUT = "0.16 1 0.3 1"


def _instance(filename, axes):
    """Pin a variable font to one weight, as bytes. Timestamps stay fixed so
    the output is identical from run to run."""
    font = instancer.instantiateVariableFont(TTFont(FONT_DIR / filename, recalcTimestamp=False), axes)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


_bytes = {role: _instance(filename, axes) for role, (filename, axes, _, _) in FONTS.items()}
_loaded = {role: TTFont(io.BytesIO(data)) for role, data in _bytes.items()}


def measure(text, size, font="text"):
    f = _loaded[font]
    cmap, hmtx = f.getBestCmap(), f["hmtx"]
    return sum(hmtx[cmap.get(ord(ch), cmap[ord("x")])][0] for ch in text) / f["head"].unitsPerEm * size


def font_faces(used):
    """@font-face rules holding only the glyphs a figure uses."""
    css = ""
    for role, chars in used.items():
        if not chars:
            continue
        _, _, family, weight = FONTS[role]
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern"]
        opts.desubroutinize = True
        opts.drop_tables += ["meta"]
        font = TTFont(io.BytesIO(_bytes[role]), recalcTimestamp=False)
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(set(chars))))
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        css += (f"@font-face{{font-family:'{family}';font-weight:{weight};font-display:swap;"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return css


def n(v):
    """Short number formatting for SVG attributes."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mix(a, b, t):
    """Blend hex colours: t=0 gives a, t=1 gives b."""
    pa, pb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


class Figure:
    """One SVG. Tracks the text it sets so it embeds only those glyphs, and
    the shapes it draws so the skeleton matches the content."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.used = {role: "" for role in FONTS}
        self.bars = []

    def text(self, x, y, s, cls, font="text", size=14, anchor="start", bar=True):
        self.used[font] += s
        width = measure(s, size, font)
        if bar:
            left = x - width if anchor == "end" else x
            self.bars.append((left, y - size * 0.72, width, size * 0.78))
        extra = f' text-anchor="{anchor}"' if anchor != "start" else ""
        return f'<text x="{n(x)}" y="{n(y)}" class="{cls}"{extra}>{esc(s)}</text>'

    def mono(self, x, y, s, cls, size=12, anchor="start", bar=True):
        """Monospace text with a fixed advance, so it lines up on every platform."""
        self.used["mono"] += s
        width = len(s) * size * 0.6
        if bar:
            left = x - width if anchor == "end" else x
            self.bars.append((left, y - size * 0.72, width, size * 0.78))
        extra = f' text-anchor="{anchor}"' if anchor != "start" else ""
        return f'<text x="{n(x)}" y="{n(y)}" class="{cls}" textLength="{n(width)}"{extra}>{esc(s)}</text>'

    def icon(self, name, x, y, color, size=17):
        """An outline icon."""
        self.bars.append((x, y, size, size, 4))
        return (f'<g transform="translate({n(x)} {n(y)}) scale({size / 24:.4f})" fill="none" stroke="{color}" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round">{LINES[name]}</g>')

    def logo(self, name, x, y, color, size=16):
        """A brand logo; nothing when the brand has none."""
        if name not in BRANDS:
            return ""
        self.bars.append((x, y, size, size, 4))
        return f'<path transform="translate({n(x)} {n(y)}) scale({size / 24:.4f})" fill="{color}" d="{BRANDS[name]}"/>'

    def render(self, label, style, body, defs=""):
        base = (
            f".body{{font:400 14px {SANS};fill:{C['fg']}}}"
            f".name{{font:600 14px {SANS};fill:{C['bright']}}}"
            f".label{{font:400 13px {SANS};fill:{C['muted']}}}"
            f".note{{font:400 13px {SANS};fill:{C['muted']}}}"
            f".num{{font:400 12px {MONO};fill:{C['muted']}}}"
        )
        gradient = (
            f'<linearGradient id="sk" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{self.w}" y2="0">'
            f'<stop offset=".35" stop-color="{C["sk"]}"/><stop offset=".5" stop-color="{C["skhi"]}"/><stop offset=".65" stop-color="{C["sk"]}"/>'
            f'<animateTransform attributeName="gradientTransform" type="translate" values="{n(-self.w * .7)} 0;{n(self.w * .7)} 0" '
            'dur="0.9s" repeatCount="2"/></linearGradient>'
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {n(self.h)}" width="{self.w}" height="{n(self.h)}" '
            f'role="img" aria-label="{esc(label)}">\n<defs><style>{font_faces(self.used)}{base}{style}</style>'
            f"{gradient}{defs}</defs>\n{body}\n</svg>\n"
        )


def skeleton(bars, intro):
    """Placeholder bars that shimmer, then fade out as the content arrives."""
    total = intro + 0.3
    rects = "".join(
        f'<rect x="{n(b[0])}" y="{n(b[1])}" width="{n(b[2])}" height="{n(b[3])}" rx="{n(b[4] if len(b) > 4 else 4)}" fill="url(#sk)"/>'
        for b in bars
    )
    return (
        f'<g opacity="0">{rects}<animate attributeName="opacity" values="1;1;0" '
        f'keyTimes="0;{intro / total:.3f};1" dur="{n(total)}s" fill="freeze"/></g>'
    )


def settle(content, delay, rise=6, dur=0.7):
    """Fade content up into place once. Without animation it is simply visible."""
    total = delay + dur
    key = f"{delay / total:.3f}"
    return (
        f"<g>{content}"
        f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{key};1" dur="{n(total)}s" calcMode="spline" '
        f'keySplines="0 0 1 1;{EASE_OUT}" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="translate" values="0 {rise};0 {rise};0 0" keyTimes="0;{key};1" '
        f'dur="{n(total)}s" calcMode="spline" keySplines="0 0 1 1;{EASE_OUT}" fill="freeze"/></g>'
    )


def write(name, mode, svg):
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / f"{name}-{mode}.svg").write_text(svg, encoding="utf-8")


# --------------------------------------------------------------------------
# 1. Profile
# --------------------------------------------------------------------------

NAME = "Robert Greathouse"
ABOUT = ["Software engineer at Waystar. I build backend services, streaming data",
         "pipelines, and the tools around them."]
FACTS = [
    ("briefcase", "green", "Now", "Software Engineer Co-Op, Waystar", "Jun 2026"),
    ("map-pin", "blue", "Based in", "Lehi, Utah", ""),
    ("workflow", "cyan", "Working on", "Internal web apps, Spring Boot APIs, Kafka and Storm pipelines", ""),
    ("smartphone", "orange", "On the side", "Keyframe, an anime tracker for iPhone", "Sep 2026"),
    ("graduation-cap", "purple", "Education", "BS Computer Science, Machine Learning emphasis, BYU", "2026"),
]


def profile(mode):
    size, intro, top, step = 40, 1.1, 160, 34
    fig = Figure(W, top + step * (len(FACTS) - 1) + 14)
    fig.used["display"] += NAME
    style = (
        f".title{{font:700 {size}px {DISPLAY};fill:{C['bright']};letter-spacing:-.6px}}"
        f".about{{font:400 15px {SANS};fill:{C['soft']}}}"
    )

    # The one authored moment: the name types itself, and the cursor stays.
    advances = [measure(NAME[:k], size, "display") - 0.6 * k for k in range(len(NAME) + 1)]
    per_char = 0.055
    end = intro + per_char * len(NAME)
    times = [0, intro] + [intro + per_char * k for k in range(1, len(NAME) + 1)]
    widths = [0, 0] + [advances[k] + 3 for k in range(1, len(NAME))] + [advances[-1] + 30]
    xs = [X0, X0] + [X0 + advances[k] + 6 for k in range(1, len(NAME) + 1)]
    key_times = ";".join(n(t / end) if t in (0, end) else f"{t / end:.4f}" for t in times)
    typed = (
        f'<clipPath id="typed"><rect x="0" y="0" height="62" width="{n(advances[-1] + 30)}">'
        f'<animate attributeName="width" values="{";".join(n(v) for v in widths)}" keyTimes="{key_times}" dur="{n(end)}s" '
        f'calcMode="discrete" fill="freeze"/></rect></clipPath>'
        f'<text x="{X0}" y="46" class="title" clip-path="url(#typed)">{NAME}</text>'
        f'<rect x="{n(X0 + advances[-1] + 6)}" y="16" width="3" height="32" fill="{C["orange"]}">'
        f'<animate attributeName="x" values="{";".join(n(v) for v in xs)}" keyTimes="{key_times}" dur="{n(end)}s" '
        f'calcMode="discrete" fill="freeze"/>'
        f'<animate attributeName="opacity" values="1;0" keyTimes="0;0.55" dur="1.1s" calcMode="discrete" repeatCount="indefinite"/></rect>'
    )
    fig.bars.append((X0, 16, advances[-1], 32, 6))

    lead = "".join(fig.text(X0, 84 + i * 23, line, "about", size=15) for i, line in enumerate(ABOUT))
    rows = []
    for i, (icon, color, label, value, since) in enumerate(FACTS):
        y = top + i * step
        row = fig.icon(icon, X0, y - 13, C[color]) + fig.text(X0 + 30, y, label, "label", size=13) + fig.text(X0 + 150, y, value, "body")
        if since:
            row += fig.mono(W - X0, y, since, "num", anchor="end")
        rows.append(row)
    label = f"{NAME}. {' '.join(ABOUT)} " + " ".join(f"{k}: {v}." for _, _, k, v, _ in FACTS)
    body = skeleton(fig.bars, intro) + typed + settle(lead, end + 0.05)
    body += "".join(settle(row, end + 0.2 + i * 0.06) for i, row in enumerate(rows))
    write("profile", mode, fig.render(label, style, body))


# --------------------------------------------------------------------------
# 2. Languages and tools
# --------------------------------------------------------------------------

# (name, logo, colour, used for, where)
LANGUAGES = [
    ("Java", "Java", "orange", "Spring Boot APIs and stream services", "Waystar, Keyframe"),
    ("TypeScript", "TypeScript", "blue", "React front ends", "Waystar, portfolio site"),
    ("Python", "Python", "yellow", "CLIs, ML research, course tooling", "MDXCanvas, code-cleanup"),
    ("Swift", "Swift", "red", "SwiftUI iPhone app and widgets", "Keyframe"),
    ("SQL", "PostgreSQL", "cyan", "PostgreSQL queries and dashboards", "Waystar, Keyframe"),
    ("JavaScript", "JavaScript", "green", "Web apps and course sites", "BYU, side projects"),
    ("C++", "C++", "purple", "Coursework", "BYU"),
]
TOOLS = [
    ("Frameworks", [("Spring Boot", "green"), ("React", "cyan"), ("SwiftUI", "orange"), ("Next.js", "bright")]),
    ("Data", [("PostgreSQL", "blue"), ("Kafka", "soft"), ("Apache Storm", "yellow"), ("Pandas", "purple"), ("scikit-learn", "orange")]),
    ("Delivery", [("Docker", "blue"), ("GitHub Actions", "cyan"), ("Linux", "yellow"), ("Splunk", "pink"), ("Harness", "green")]),
]


def languages(mode):
    intro, top, step = 1.2, 20, 34
    tools_top = top + step * len(LANGUAGES) + 18
    fig = Figure(W, tools_top + step * (len(TOOLS) - 1) + 12)
    c1, c2, c3 = X0 + 30, X0 + 170, 600
    rows = []
    for i, (name, mark, color, used, where) in enumerate(LANGUAGES):
        y = top + i * step
        rows.append(fig.logo(mark, X0, y - 13, C[color], 17) + fig.text(c1, y, name, "name", "strong") + fig.text(c2, y, used, "body")
                    + fig.text(c3, y, where, "note", size=13))
    for i, (label, items) in enumerate(TOOLS):
        y = tools_top + i * step
        row, x = fig.text(X0, y, label, "label", size=13), c2
        for item, color in items:
            mark = fig.logo(item, x, y - 12, C[color], 15)
            if not mark:
                mark = f'<circle cx="{n(x + 7.5)}" cy="{n(y - 4.5)}" r="4.5" fill="none" stroke="{C[color]}" stroke-width="1.8"/>'
            row += mark + fig.text(x + 23, y, item, "body")
            x += 23 + measure(item, 14) + 26
        rows.append(row)
    body = skeleton(fig.bars, intro) + "".join(settle(row, intro + i * 0.05) for i, row in enumerate(rows))
    label = "Languages: " + "; ".join(f"{nm} for {u.lower()} ({w})" for nm, _, _, u, w in LANGUAGES) + ". " + " ".join(
        f"{k}: {', '.join(i for i, _ in v)}." for k, v in TOOLS)
    write("languages", mode, fig.render(label, "", body))


# --------------------------------------------------------------------------
# 3. Things to check out: one linked row each
# --------------------------------------------------------------------------

# (slug, icon, colour, title, about, kind)
WORK = [
    ("keyframe", "sparkles", "orange", "Keyframe", "Anime tracker for iPhone. In development.", "Swift"),
    ("setup", "terminal", "cyan", "setup", "My terminal and editor setup in one palette.", "Dotfiles"),
    ("code-cleanup", "package", "green", "code-cleanup", "One house style for every file in a repo.", "Python"),
    ("mdx-canvas", "book-marked", "purple", "mdx-canvas", "CLI that builds Canvas courses from XML.", "Python"),
    ("pitchers-dilemma", "file-text", "pink", "The Pitcher’s Dilemma", "Game-theory model of pickoffs and stolen bases.", "Paper"),
]


def work_row(mode, slug, icon, color, title, about, kind, index):
    intro, h = 1.2 + index * 0.08, 40
    fig = Figure(W, h)
    y = h / 2 + 5
    style = f".repo{{font:700 16px {DISPLAY};fill:{C['bright']};letter-spacing:-.1px}}"
    row = fig.icon(icon, X0, y - 14, C[color], 18) + fig.text(X0 + 30, y, title, "repo", "display", 16)
    row += fig.text(X0 + 258, y, about, "body") + fig.text(W - X0 - 30, y, kind, "note", size=13, anchor="end")
    ax, ay = W - X0 - 15, h / 2
    row += (f'<path d="M{ax} {ay + 6}l12-12m-9 0h9v9" fill="none" stroke="{C[color]}" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round"/>')
    fig.bars.append((ax, ay - 7, 14, 14, 4))
    write(f"work-{slug}", mode, fig.render(f"{title}: {about} {kind}.", style, skeleton(fig.bars, intro) + settle(row, intro, rise=4)))


# --------------------------------------------------------------------------
# 4. Contributions, from GitHub's contribution calendar
# --------------------------------------------------------------------------

def contributions(mode, days):
    """days: [(date, count, level 0-4), ...] oldest first, starting on a Sunday."""
    intro, sweep = 1.2, 1.6
    cell, pitch = 13, 16.5
    x0, y0 = X0, 28
    fig = Figure(W, y0 + 7 * pitch + 40)
    start = days[0][0]
    week = lambda d: (d - start).days // 7
    weeks = week(days[-1][0]) + 1
    top_shade = C["cyan"] if mode == "dark" else mix(C["blue"], "#000000", 0.35)
    shades = [C["empty"], mix(C["page"], C["blue"], 0.34), mix(C["page"], C["blue"], 0.64), C["blue"], top_shade]
    total = sum(count for _, count, _ in days)
    best = run = 0
    for _, count, _ in days:
        run = run + 1 if count else 0
        best = max(best, run)

    frame, last = "", -9
    for col in range(weeks):
        first = start + datetime.timedelta(days=col * 7)
        if first.day <= 7 and col - last > 3 and col < weeks - 1:
            frame += fig.mono(x0 + col * pitch, 12, first.strftime("%b"), "num", bar=False)
            last = col
    r = cell - 3
    squares = "".join(
        f"M{n(x0 + week(d) * pitch + 1.5)} {n(y0 + ((d.weekday() + 1) % 7) * pitch + 1.5)}h{r}v{r}h-{r}z" for d, _, _ in days
    )
    grid = f'<path d="{squares}" fill="url(#sk)" stroke="url(#sk)" stroke-width="3" stroke-linejoin="round"/>'
    columns = ""
    for col in range(weeks):
        t0 = intro + sweep * col / max(weeks - 1, 1)
        cells = "".join(
            f'<use href="#c" y="{n(y0 + ((d.weekday() + 1) % 7) * pitch)}" fill="{shades[lvl]}"/>'
            for d, _, lvl in days if week(d) == col
        )
        total_t = t0 + 0.3
        columns += (
            f'<g transform="translate({n(x0 + col * pitch)} 0)">{cells}'
            f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{t0 / total_t:.3f};1" dur="{n(total_t)}s" fill="freeze"/></g>'
        )
    fy = fig.h - 10
    line = f"{total:,} contributions in the last year"
    footer = fig.text(x0, fy, line, "body") + fig.text(x0 + measure(line, 14) + 20, fy, f"Longest streak {best} days", "note", size=13)
    lx = W - X0 - 5 * pitch + 3
    legend = "".join(f'<rect x="{n(lx + i * pitch)}" y="{fy - 11}" width="{cell}" height="{cell}" rx="3" fill="{s}"/>' for i, s in enumerate(shades))
    legend += fig.text(lx - 10, fy, "Less", "note", size=13, anchor="end", bar=False)
    body = frame + grid + columns + skeleton(fig.bars, intro) + settle(footer + legend, intro + sweep, rise=0)
    defs = f'<rect id="c" width="{cell}" height="{cell}" rx="3"/>'
    write("contributions", mode, fig.render(f"{line}. Longest streak {best} days.", "", body, defs))
    return line


def load_days():
    if not DATA.exists():
        return None
    days = json.loads(DATA.read_text())["days"]
    return [(datetime.date.fromisoformat(d["date"]), d["count"], d["level"]) for d in days] or None


CONTRIBUTIONS_BLOCK = """### Contributions

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/contributions-dark.svg">
  <img src="assets/contributions-light.svg" alt="{alt}">
</picture>
"""


def update_readme(alt):
    """Fill the contributions section of the README once there is data for it."""
    text = README.read_text()
    block = CONTRIBUTIONS_BLOCK.format(alt=alt) if alt else ""
    new = re.sub(r"(<!-- contributions:start -->\n).*?(<!-- contributions:end -->)", lambda m: m.group(1) + block + m.group(2), text, flags=re.S)
    if new != text:
        README.write_text(new)


def main():
    global C
    days = load_days()
    alt = None
    for mode, palette in MODES.items():
        C = palette
        profile(mode)
        languages(mode)
        for i, row in enumerate(WORK):
            work_row(mode, *row, i)
        if days:
            alt = contributions(mode, days)
    update_readme(f"Contribution calendar: {alt}." if alt else None)


if __name__ == "__main__":
    main()
