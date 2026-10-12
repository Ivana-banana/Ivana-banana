"""Обезьянка прыгает по графику контрибуций и съедает его.

Берёт календарь контрибуций через GitHub GraphQL API и собирает два
анимированных SVG (светлый и тёмный) — замена змейке Platane/snk.

    GITHUB_TOKEN=... python monkey.py <user> <out_dir>
    python monkey.py --demo <out_dir>      # случайные данные, без сети
"""

import json
import os
import random
import sys
import urllib.request
from pathlib import Path

CELL, GAP = 11, 3
STEP = CELL + GAP
PAD_X, PAD_TOP, PAD_BOTTOM = 18, 64, 14
JUMP_PAUSE = 0.08  # сек на «поедание» колонки после приземления
RESET_PAUSE = 1.4  # сек на пустой сетке перед новым кругом

THEMES = {
    "monkey.svg": {
        "levels": ["#efece2", "#fff1b8", "#ffe066", "#ffd23f", "#e8a900"],
        "fur": "#8b5a2b",
        "face": "#f2d3a2",
        "ink": "#2b1a0b",
        "shadow": "#16171b",
    },
    "monkey-dark.svg": {
        "levels": ["#161b22", "#3d3511", "#7a6514", "#c9a21c", "#ffd23f"],
        "fur": "#a8692f",
        "face": "#f2d3a2",
        "ink": "#2b1a0b",
        "shadow": "#000000",
    },
}

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { weekday contributionLevel } }
      }
    }
  }
}
"""


def fetch_weeks(user, token):
    """Список недель, каждая — список (weekday, level)."""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "banana-monkey"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(d["weekday"], LEVELS[d["contributionLevel"]]) for d in w["contributionDays"]]
            for w in weeks]


def demo_weeks():
    rnd = random.Random(7)
    return [[(d, rnd.choice([0, 0, 0, 1, 1, 2, 3, 4])) for d in range(7)] for _ in range(53)]


def pct(t, total):
    return f"{100 * t / total:.3f}%"


def build_timeline(weeks, width):
    """Прыжки обезьянки: [(x, t_прилёт, t_вылет, высота_прыжка)] и длина круга."""
    cols = [i for i, w in enumerate(weeks) if any(lvl for _, lvl in w)]
    if not cols:
        cols = list(range(0, len(weeks), 4))
    xs = [-30] + [PAD_X + c * STEP + CELL / 2 for c in cols] + [width + 30]

    stops, t = [], 0.0
    for i, x in enumerate(xs):
        if i:
            dist = abs(x - xs[i - 1]) / STEP
            t += min(0.24 + 0.03 * dist, 0.7)
        pause = JUMP_PAUSE if 0 < i < len(xs) - 1 else 0
        height = min(16 + 3 * (abs(x - xs[i - 1]) / STEP if i else 0), 40)
        stops.append((x, t, t + pause, height))
        t += pause
    return cols, stops, t + RESET_PAUSE


def monkey_css(stops, total):
    """Keyframes: mx — по горизонтали, my — прыжок, sh — тень."""
    mx, my, sh = [], [], []
    for i, (x, arrive, leave, height) in enumerate(stops):
        for t in sorted({arrive, leave}):
            mx.append(f"{pct(t, total)}{{transform:translateX({x:.1f}px)}}")
            my.append(f"{pct(t, total)}{{transform:translateY(0);animation-timing-function:ease-out}}")
            sh.append(f"{pct(t, total)}{{transform:scale(1);opacity:.18;animation-timing-function:ease-out}}")
        if i + 1 < len(stops):
            nxt = stops[i + 1]
            mid = (leave + nxt[1]) / 2
            my.append(f"{pct(mid, total)}{{transform:translateY(-{nxt[3]:.0f}px);animation-timing-function:ease-in}}")
            sh.append(f"{pct(mid, total)}{{transform:scale(.45);opacity:.08;animation-timing-function:ease-in}}")
    last_x = stops[-1][0]
    mx.append(f"100%{{transform:translateX({last_x:.1f}px)}}")
    my.append("100%{transform:translateY(0)}")
    sh.append("100%{transform:scale(1);opacity:.18}")
    return (f"@keyframes mx{{{''.join(mx)}}}"
            f"@keyframes my{{{''.join(my)}}}"
            f"@keyframes sh{{{''.join(sh)}}}")


def eat_css(cols, stops, total):
    """Каждая колонка исчезает в момент приземления и возвращается в конце круга."""
    back = pct(total - 0.5, total)
    rules = []
    for col, (_, arrive, _, _) in zip(cols, stops[1:]):
        a, b = pct(arrive, total), pct(arrive + 0.12, total)
        rules.append(
            f"@keyframes e{col}{{0%,{a}{{opacity:1;transform:scale(1)}}"
            f"{b},{back}{{opacity:0;transform:scale(0)}}100%{{opacity:1;transform:scale(1)}}}}"
            f".e{col}{{animation:e{col} {total:.2f}s linear infinite}}"
        )
    return "".join(rules)


def monkey_svg(theme):
    fur, face, ink = theme["fur"], theme["face"], theme["ink"]
    # Ноги на y=0, центр по x=0. Справа в поднятой лапе — банан.
    return f"""
<path d="M-6 -7C-17 -6 -19 -19 -12 -22C-8 -23.5 -6 -19 -9 -18" fill="none" stroke="{fur}" stroke-width="2.4" stroke-linecap="round"/>
<ellipse cx="0" cy="-9" rx="7" ry="8" fill="{fur}"/>
<ellipse cx="1" cy="-8" rx="4.2" ry="5.4" fill="{face}"/>
<ellipse cx="-4" cy="-1.6" rx="3.2" ry="2" fill="{fur}"/>
<ellipse cx="4" cy="-1.6" rx="3.2" ry="2" fill="{fur}"/>
<path d="M-5 -12L-9 -6" stroke="{fur}" stroke-width="2.6" stroke-linecap="round"/>
<path d="M5 -13L10 -20" stroke="{fur}" stroke-width="2.6" stroke-linecap="round"/>
<g transform="translate(6,-33) scale(.2)">
<path d="M49 9c8.5 21 .5 45.5-27.5 50.5-6.5 1.2-12-.6-14.5-4.5 20-4 31.5-19.5 31-45z" fill="#ffd23f"/>
<path d="M38 10.5 39.2 3l6.2.6L49 9z" fill="#7a5f1a"/>
</g>
<circle cx="-8" cy="-23" r="3.3" fill="{fur}"/><circle cx="-8" cy="-23" r="1.8" fill="{face}"/>
<circle cx="8" cy="-23" r="3.3" fill="{fur}"/><circle cx="8" cy="-23" r="1.8" fill="{face}"/>
<circle cx="0" cy="-22" r="8" fill="{fur}"/>
<ellipse cx="0" cy="-19.8" rx="5.8" ry="4.6" fill="{face}"/>
<circle cx="-2.6" cy="-23.4" r="2.9" fill="{face}"/><circle cx="2.6" cy="-23.4" r="2.9" fill="{face}"/>
<circle cx="-2.4" cy="-23.2" r="1.1" fill="{ink}"/><circle cx="2.4" cy="-23.2" r="1.1" fill="{ink}"/>
<path d="M-2 -18.6Q0 -16.6 2 -18.6" fill="none" stroke="{ink}" stroke-width=".9" stroke-linecap="round"/>
"""


def render(weeks, theme):
    width = PAD_X * 2 + len(weeks) * STEP - GAP
    height = PAD_TOP + 7 * STEP - GAP + PAD_BOTTOM
    cols, stops, total = build_timeline(weeks, width)
    ground = PAD_TOP - 3

    empty, filled = [], []
    for c, week in enumerate(weeks):
        for day, lvl in week:
            x, y = PAD_X + c * STEP, PAD_TOP + day * STEP
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2"/>')
            if lvl:
                filled.append(f'<rect class="e{c}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                              f'rx="2" fill="{theme["levels"][lvl]}"/>')

    css = (
        "rect{transform-box:fill-box;transform-origin:center}"
        f".mx{{animation:mx {total:.2f}s linear infinite}}"
        f".my{{animation:my {total:.2f}s linear infinite}}"
        f".sh{{transform-box:fill-box;transform-origin:center;animation:sh {total:.2f}s linear infinite}}"
        + monkey_css(stops, total)
        + eat_css(cols, stops, total)
        + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        "<title>Обезьянка ест контрибуции</title>"
        f"<style>{css}</style>"
        f'<g fill="{theme["levels"][0]}">{"".join(empty)}</g>'
        f'<g>{"".join(filled)}</g>'
        f'<g transform="translate(0,{ground})"><g class="mx">'
        f'<ellipse class="sh" cx="0" cy="0" rx="9" ry="2.2" fill="{theme["shadow"]}" opacity=".18"/>'
        f'<g class="my">{monkey_svg(theme)}</g>'
        "</g></g></svg>"
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    who, out = sys.argv[1:]
    weeks = demo_weeks() if who == "--demo" else fetch_weeks(who, os.environ["GITHUB_TOKEN"])
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (out_dir / name).write_text(render(weeks, theme), encoding="utf-8")
        print(f"{out_dir / name}")


if __name__ == "__main__":
    main()
