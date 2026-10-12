"""Циклоп с корзиной идёт по графику контрибуций и собирает бананы.

Берёт календарь контрибуций через GitHub GraphQL API и собирает два
анимированных SVG (светлый и тёмный) — замена змейке Platane/snk.
Персонаж нарисован по мотивам аватарки: круглая голова, один глаз, улыбка.

    GITHUB_TOKEN=... python runner.py <user> <out_dir>
    python runner.py --demo <out_dir>      # случайные данные, без сети
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
SPEED = 48  # px/с
START, FINISH = -40, 40  # откуда выходит и куда уходит за край
BASKET = (14, -14)  # центр корзины относительно ног персонажа
FLY = 0.45  # сек полёта банана из клетки в корзину
RESET_PAUSE = 1.4  # сек на пустой сетке перед новым кругом

BANANA = ('<path d="M49 9c8.5 21 .5 45.5-27.5 50.5-6.5 1.2-12-.6-14.5-4.5 20-4 31.5-19.5 31-45z" '
          'fill="#ffd23f"/><path d="M38 10.5 39.2 3l6.2.6L49 9z" fill="#7a5f1a"/>')

THEMES = {
    "runner.svg": {
        "levels": ["#efece2", "#fff1b8", "#ffe066", "#ffd23f", "#e8a900"],
        "shadow": "#16171b",
    },
    "runner-dark.svg": {
        "levels": ["#161b22", "#3d3511", "#7a6514", "#c9a21c", "#ffd23f"],
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
        headers={"Authorization": f"bearer {token}", "User-Agent": "banana-runner"},
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


def character():
    """Ноги на y=0, смотрит вправо, корзина впереди."""
    skin, skin_dark, hair = "#7b4a2b", "#5e3720", "#1d1510"
    leg = '<path d="M0 0V9" stroke="#2b2f3a" stroke-width="3.2" stroke-linecap="round"/>'
    return f"""
<g transform="translate(-2,-9)"><g class="l1">{leg}</g></g>
<g transform="translate(2,-9)"><g class="l2">{leg}</g></g>
<g class="bob">
<path d="M-3 -19L-6 -12" stroke="{skin}" stroke-width="2.6" stroke-linecap="round"/>
<rect x="-6.5" y="-21" width="13" height="13" rx="4.5" fill="#ffd23f"/>
<path d="M-6.5 -10.5h13" stroke="#e8a900" stroke-width="1.6"/>
<path d="M4 -18L11 -14" stroke="{skin}" stroke-width="2.6" stroke-linecap="round"/>
<g transform="translate({BASKET[0]},{BASKET[1]})">
<g class="p1" transform="translate(-6,-9) scale(.13)">{BANANA}</g>
<g class="p2" transform="translate(-1,-10) scale(.13)">{BANANA}</g>
<g class="p3" transform="translate(-3.5,-12) scale(.13)">{BANANA}</g>
<path d="M-7 -4H7L5 4H-5Z" fill="#a0703c"/>
<path d="M-7.5 -4.5H7.5" stroke="#6e4a22" stroke-width="1.8" stroke-linecap="round"/>
<path d="M-4 -2L-3 3M0 -2V3M4 -2L3 3" stroke="#6e4a22" stroke-width=".8"/>
</g>
<circle cx="-8.6" cy="-30" r="2.2" fill="{skin_dark}"/>
<circle cx="0" cy="-30" r="9.5" fill="{skin}"/>
<path d="M-9.4 -31C-10 -40 9 -42 9.4 -32C7 -36 -6 -37 -9.4 -31Z" fill="{hair}"/>
<ellipse cx="2" cy="-31.6" rx="4" ry="3.1" fill="#fff"/>
<circle cx="2.8" cy="-31.6" r="2" fill="#4a2c16"/>
<circle cx="3" cy="-31.6" r="1" fill="#111"/>
<circle cx="3.6" cy="-32.3" r=".55" fill="#fff"/>
<path d="M-2.2 -35.4Q2 -37.2 6.2 -35.2" fill="none" stroke="{hair}" stroke-width="1.1" stroke-linecap="round"/>
<path d="M-4 -26.4H8.2Q7.6 -21.2 2.1 -21.2Q-3.4 -21.2 -4 -26.4Z" fill="#5a1f1a"/>
<path d="M-3.6 -26.4H7.8V-24.6H-3.2Z" fill="#f3e7c0"/>
<path d="M-.6 -26.4V-24.6M1.6 -26.4V-24.6M3.8 -26.4V-24.6M6 -26.4V-24.6" stroke="#cdb98a" stroke-width=".45"/>
</g>
"""


def render(weeks, theme):
    width = PAD_X * 2 + len(weeks) * STEP - GAP
    height = PAD_TOP + 7 * STEP - GAP + PAD_BOTTOM
    ground = PAD_TOP - 3
    x0, x1 = START, width + FINISH
    walk = (x1 - x0) / SPEED
    total = walk + RESET_PAUSE
    back = pct(total - 0.5, total)

    empty, filled, flying, css = [], [], [], []
    picked = []  # моменты, когда банан долетает до корзины
    for c, week in enumerate(weeks):
        days = [(d, lvl) for d, lvl in week if lvl]
        for day, lvl in week:
            x, y = PAD_X + c * STEP, PAD_TOP + day * STEP
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2"/>')
            if lvl:
                filled.append(f'<rect class="e{c}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                              f'rx="2" fill="{theme["levels"][lvl]}"/>')
        if not days:
            continue

        # Клетки съедаются, когда корзина над колонкой; из колонки вылетает банан.
        cx = PAD_X + c * STEP + CELL / 2
        t = (cx - BASKET[0] - x0) / SPEED
        picked.append(t + FLY)
        top_y = PAD_TOP + min(d for d, _ in days) * STEP + CELL / 2
        dx = SPEED * FLY
        dy = ground + BASKET[1] - 6 - top_y
        a, b, m, e = (pct(t, total), pct(t + 0.12, total),
                      pct(t + FLY * 0.5, total), pct(t + FLY, total))
        css.append(
            f"@keyframes e{c}{{0%,{a}{{opacity:1;transform:scale(1)}}"
            f"{b},{back}{{opacity:0;transform:scale(0)}}100%{{opacity:1;transform:scale(1)}}}}"
            f".e{c}{{animation:e{c} {total:.2f}s linear infinite}}"
            f"@keyframes f{c}{{0%,{a}{{opacity:0;transform:translate(0,0)}}"
            f"{pct(t + 0.01, total)}{{opacity:1;transform:translate(0,0);animation-timing-function:ease-out}}"
            f"{m}{{opacity:1;transform:translate({dx * 0.5:.1f}px,{dy - 14:.1f}px);animation-timing-function:ease-in}}"
            f"{e}{{opacity:1;transform:translate({dx:.1f}px,{dy:.1f}px)}}"
            f"{pct(t + FLY + 0.01, total)},100%{{opacity:0;transform:translate({dx:.1f}px,{dy:.1f}px)}}}}"
            f".f{c}{{opacity:0;animation:f{c} {total:.2f}s linear infinite}}"
        )
        flying.append(f'<g transform="translate({cx - 4:.1f},{top_y - 5:.1f})">'
                      f'<g class="f{c}"><g transform="scale(.15)">{BANANA}</g></g></g>')

    # Корзина наполняется в три приёма по мере сбора.
    for i in range(3):
        if picked:
            t = picked[-(-len(picked) * (i + 1) // 3) - 1]
            css.append(f"@keyframes p{i + 1}{{0%,{pct(t - 0.01, total)}{{opacity:0}}"
                       f"{pct(t, total)},{back}{{opacity:1}}100%{{opacity:0}}}}"
                       f".p{i + 1}{{opacity:0;animation:p{i + 1} {total:.2f}s linear infinite}}")
        else:
            css.append(f".p{i + 1}{{opacity:0}}")

    walk_pct = pct(walk, total)
    css.append(
        f"@keyframes mx{{0%{{transform:translateX({x0}px)}}{walk_pct},100%{{transform:translateX({x1}px)}}}}"
        f".mx{{animation:mx {total:.2f}s linear infinite}}"
        "@keyframes leg{0%{transform:rotate(28deg)}100%{transform:rotate(-28deg)}}"
        ".l1{animation:leg .32s ease-in-out infinite alternate}"
        ".l2{animation:leg .32s ease-in-out -.32s infinite alternate}"
        "@keyframes bob{0%{transform:translateY(0)}100%{transform:translateY(-1.3px)}}"
        ".bob{animation:bob .16s ease-in-out infinite alternate}"
    )

    style = ("rect{transform-box:fill-box;transform-origin:center}" + "".join(css)
             + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        "<title>Циклоп собирает бананы из контрибуций</title>"
        f"<style>{style}</style>"
        f'<g fill="{theme["levels"][0]}">{"".join(empty)}</g>'
        f'<g>{"".join(filled)}</g>'
        f'<g transform="translate(0,{ground})"><g class="mx">'
        f'<ellipse cx="2" cy="0" rx="10" ry="2.2" fill="{theme["shadow"]}" opacity=".18"/>'
        f"{character()}"
        "</g></g>"
        f'<g>{"".join(flying)}</g>'
        "</svg>"
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
