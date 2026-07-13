"""Render a sample verb card to PNG for design iteration.

Run:  uv run python scripts/render_card_test.py
Output: scripts/_card_sample.png
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).with_name("_card_sample.png")

# --- sample data ----------------------------------------------------------
VERB = {
    "word": "opstaan",
    "meaning": "بلند شدن، بیدار شدن",
    "pron": "اوپ‌ستان",
    "particle": "op",
    "base": "staan",
    "present": [
        ("ik", "sta", "op"),
        ("jij / u", "staat", "op"),
        ("hij / zij", "staat", "op"),
        ("wij / jullie", "staan", "op"),
        ("zij", "staan", "op"),
    ],
    "principal": ("opstaan", "stond op", "opgestaan"),
    "examples": [
        ("Ik <b>sta</b> om zeven uur <em>op</em>.", "ساعت هفت بیدار می‌شوم."),
        ("We <b>staan</b> vroeg <em>op</em> in het weekend.", "آخر هفته زود بیدار می‌شویم."),
    ],
}


def build_html(v: dict) -> str:
    present_rows = "".join(
        f"<tr><td class='pron'>{p}</td>"
        f"<td class='verb'><span class='stem'>{stem}</span> "
        f"<span class='part'>{part}</span></td></tr>"
        for p, stem, part in v["present"]
    )
    inf, past, perf = v["principal"]
    examples = "".join(
        f"<div class='ex'><div class='nl'>{nl}</div>"
        f"<div class='fa'>{fa}</div></div>"
        for nl, fa in v["examples"]
    )
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif;
    background: transparent;
    padding: 28px;
  }}
  .card {{
    width: 700px;
    background: #ffffff;
    border-radius: 28px;
    overflow: hidden;
    box-shadow: 0 24px 60px rgba(20, 30, 80, 0.18);
  }}
  .header {{
    background: linear-gradient(135deg, #FF7A18 0%, #AF002D 60%, #6A0136 100%);
    color: #fff;
    padding: 34px 36px 30px;
    position: relative;
  }}
  .brand {{
    position: absolute; top: 22px; left: 28px;
    font-size: 15px; font-weight: 700; opacity: .85; letter-spacing: .3px;
  }}
  .word {{ font-size: 52px; font-weight: 900; direction: ltr; text-align: left; }}
  .meaning {{ font-size: 26px; font-weight: 700; margin-top: 8px; }}
  .pron {{ font-size: 17px; opacity: .9; margin-top: 6px; }}
  .struct {{
    display: inline-block; margin-top: 16px; direction: ltr;
    background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35);
    padding: 7px 14px; border-radius: 12px; font-size: 17px; font-weight: 700;
  }}
  .struct .plus {{ opacity: .7; margin: 0 6px; }}
  .body {{ padding: 26px 36px 30px; }}
  .section-title {{
    font-size: 19px; font-weight: 800; color: #AF002D;
    margin: 4px 0 14px; display: flex; align-items: center; gap: 8px;
  }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 26px; }}
  td, th {{ padding: 11px 16px; font-size: 19px; }}
  tbody tr:nth-child(odd) {{ background: #FBF3F1; }}
  td.pron {{ color: #8a8a8a; font-weight: 600; }}
  td.verb {{ direction: ltr; text-align: left; }}
  .stem {{ font-weight: 800; color: #1f2937; }}
  .part {{
    background: #FFE2B0; color: #9a3b00; font-weight: 800;
    padding: 1px 8px; border-radius: 7px;
  }}
  .three {{ display: flex; gap: 12px; direction: ltr; margin-bottom: 26px; }}
  .three .col {{
    flex: 1; background: #F3F5FA; border-radius: 16px; padding: 14px 10px;
    text-align: center;
  }}
  .three .lbl {{ font-size: 12px; color: #6b7280; font-weight: 700; margin-bottom: 6px; }}
  .three .val {{ font-size: 19px; font-weight: 800; color: #1f2937; }}
  .ex {{
    border-right: 4px solid #FF7A18; background: #FFF8F2;
    border-radius: 0 14px 14px 0; padding: 12px 16px; margin-bottom: 12px;
  }}
  .ex .nl {{ direction: ltr; text-align: left; font-size: 18px; color: #1f2937; }}
  .ex .nl em {{ font-style: normal; background: #FFE2B0; color: #9a3b00;
               padding: 0 6px; border-radius: 6px; font-weight: 700; }}
  .ex .fa {{ font-size: 16px; color: #6b7280; margin-top: 4px; }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="brand">🇳🇱 NLern</div>
      <div class="word">{v['word']}</div>
      <div class="meaning">{v['meaning']}</div>
      <div class="pron">🗣 {v['pron']}</div>
      <div class="struct">{v['particle']}<span class="plus">+</span>{v['base']}</div>
    </div>
    <div class="body">
      <div class="section-title">⏱ صرف زمان حال</div>
      <table><tbody>{present_rows}</tbody></table>
      <div class="section-title">🔑 سه‌جزء اصلی فعل</div>
      <div class="three">
        <div class="col"><div class="lbl">infinitief</div><div class="val">{inf}</div></div>
        <div class="col"><div class="lbl">verleden tijd</div><div class="val">{past}</div></div>
        <div class="col"><div class="lbl">voltooid</div><div class="val">{perf}</div></div>
      </div>
      <div class="section-title">💬 مثال‌ها</div>
      {examples}
    </div>
  </div>
</body>
</html>"""


async def main() -> None:
    html = build_html(VERB)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", args=["--no-sandbox"])
        page = await browser.new_page(device_scale_factor=2)
        await page.set_content(html, wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        el = await page.query_selector(".card")
        await el.screenshot(path=str(OUT), omit_background=True)
        await browser.close()
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
