"""Render styled vocabulary/verb cards to PNG via headless Chrome.

Telegram does not support custom CSS in messages, so for fully designed cards
(colors, fonts, gradients) we render real HTML/CSS to an image with Playwright
driving the system Chrome, then send the result as a photo.

Note: each call launches a browser (~1-2s). For high traffic, switch to a
long-lived browser instance or pre-render and cache the PNGs.
"""

from __future__ import annotations

from typing import TypedDict

from playwright.async_api import async_playwright


class VerbCard(TypedDict):
    """Data needed to render a separable-verb card."""

    word: str
    meaning: str
    pron: str
    particle: str
    base: str
    present: list[tuple[str, str, str]]  # (pronoun, stem, particle)
    principal: tuple[str, str, str]  # infinitief, verleden tijd, voltooid
    examples: list[tuple[str, str]]  # (dutch_html, persian)


_TEMPLATE = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif; background: transparent; padding: 28px; }}
  .card {{ width: 700px; background: #fff; border-radius: 28px; overflow: hidden;
           box-shadow: 0 24px 60px rgba(20, 30, 80, 0.18); }}
  .header {{ background: linear-gradient(135deg, #FF7A18 0%, #AF002D 60%, #6A0136 100%);
             color: #fff; padding: 34px 36px 30px; position: relative; }}
  .brand {{ position: absolute; top: 22px; left: 28px; font-size: 15px; font-weight: 700;
            opacity: .85; letter-spacing: .3px; }}
  .word {{ font-size: 52px; font-weight: 900; direction: ltr; text-align: left; }}
  .meaning {{ font-size: 26px; font-weight: 700; margin-top: 8px; }}
  .pron {{ font-size: 17px; opacity: .9; margin-top: 6px; }}
  .struct {{ display: inline-block; margin-top: 16px; direction: ltr; background: rgba(255,255,255,.18);
             border: 1px solid rgba(255,255,255,.35); padding: 7px 14px; border-radius: 12px;
             font-size: 17px; font-weight: 700; }}
  .struct .plus {{ opacity: .7; margin: 0 6px; }}
  .body {{ padding: 26px 36px 30px; }}
  .section-title {{ font-size: 19px; font-weight: 800; color: #AF002D; margin: 4px 0 14px;
                    display: flex; align-items: center; gap: 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 26px; }}
  td, th {{ padding: 11px 16px; font-size: 19px; }}
  tbody tr:nth-child(odd) {{ background: #FBF3F1; }}
  td.pron {{ color: #8a8a8a; font-weight: 600; }}
  td.verb {{ direction: ltr; text-align: left; }}
  .stem {{ font-weight: 800; color: #1f2937; }}
  .part {{ background: #FFE2B0; color: #9a3b00; font-weight: 800; padding: 1px 8px; border-radius: 7px; }}
  .three {{ display: flex; gap: 12px; direction: ltr; margin-bottom: 26px; }}
  .three .col {{ flex: 1; background: #F3F5FA; border-radius: 16px; padding: 14px 10px; text-align: center; }}
  .three .lbl {{ font-size: 12px; color: #6b7280; font-weight: 700; margin-bottom: 6px; }}
  .three .val {{ font-size: 19px; font-weight: 800; color: #1f2937; }}
  .ex {{ border-right: 4px solid #FF7A18; background: #FFF8F2; border-radius: 0 14px 14px 0;
         padding: 12px 16px; margin-bottom: 12px; }}
  .ex .nl {{ direction: ltr; text-align: left; font-size: 18px; color: #1f2937; }}
  .ex .nl em {{ font-style: normal; background: #FFE2B0; color: #9a3b00; padding: 0 6px;
                border-radius: 6px; font-weight: 700; }}
  .ex .fa {{ font-size: 16px; color: #6b7280; margin-top: 4px; }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="brand">🇳🇱 NLern</div>
      <div class="word">{word}</div>
      <div class="meaning">{meaning}</div>
      <div class="pron">🗣 {pron}</div>
      <div class="struct">{particle}<span class="plus">+</span>{base}</div>
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


def _build_html(v: VerbCard) -> str:
    present_rows = "".join(
        f"<tr><td class='pron'>{p}</td>"
        f"<td class='verb'><span class='stem'>{stem}</span> "
        f"<span class='part'>{part}</span></td></tr>"
        for p, stem, part in v["present"]
    )
    inf, past, perf = v["principal"]
    examples = "".join(
        f"<div class='ex'><div class='nl'>{nl}</div><div class='fa'>{fa}</div></div>"
        for nl, fa in v["examples"]
    )
    return _TEMPLATE.format(
        word=v["word"],
        meaning=v["meaning"],
        pron=v["pron"],
        particle=v["particle"],
        base=v["base"],
        present_rows=present_rows,
        inf=inf,
        past=past,
        perf=perf,
        examples=examples,
    )


async def _render_html_to_png(html: str, *, selector: str = ".card") -> bytes:
    """Render an HTML document and screenshot one element to PNG bytes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", args=["--no-sandbox"])
        try:
            page = await browser.new_page(device_scale_factor=2)
            await page.set_content(html, wait_until="networkidle")
            await page.evaluate("document.fonts.ready")
            element = await page.query_selector(selector)
            if element is None:
                raise RuntimeError(f"selector {selector!r} not found in rendered HTML")
            return await element.screenshot(omit_background=True)
        finally:
            await browser.close()


async def render_verb_card(verb: VerbCard) -> bytes:
    """Render a separable-verb card to PNG bytes ready to send as a photo."""
    return await _render_html_to_png(_build_html(verb))
