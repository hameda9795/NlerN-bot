"""Build the aggregated ``jomelat`` table of Dutch example sentences.

Collects every Dutch example sentence from the vocabulary library into one flat
table so the bot can pull a random sentence cheaply, instead of querying many
scattered tables. Sources:

* Verb tables (clean, separate columns):
    - vajegan_nl.scheidbarwerkworden        (separable, 2 examples/row)
    - "vajegan-nl"."Hoofdwerkwoord"          (main, 2 examples/row)
    - "vajegan-nl"."Regelmatige_Werkwoorden" (regular, 3 examples/row)
    - "vajegan-nl"."Onregelmatige_Werkwoorden" (irregular, 3 examples/row)
* Chapter vocabulary (worden.fasl_*): both examples live in one ``examples``
  text column formatted like
  ``1. Dutch. (persian)<br>2. Dutch. (persian)`` — parsed here.

The target table is created in the same remote database (``VOCAB_DATABASE_URL``)
in the ``public`` schema. The script is idempotent: it (re)creates the table and
truncates before inserting, so it is safe to re-run.

Run with::

    uv run python scripts/build_jomelat.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

# Allow running as a plain script (add project root to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from bot.config import get_settings  # noqa: E402

TABLE = "public.jomelat"

# (source label, qualified source table, [(nl_col, fa_col, tense), ...])
VERB_SOURCES: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    (
        "separable_verb",
        "vajegan_nl.scheidbarwerkworden",
        [("example_1_nl", "example_1_fa", "example_1"),
         ("example_2_nl", "example_2_fa", "example_2")],
    ),
    (
        "main_verb",
        '"vajegan-nl"."Hoofdwerkwoord"',
        [("example_1_nl", "example_1_fa", "example_1"),
         ("example_2_nl", "example_2_fa", "example_2")],
    ),
    (
        "regular_verb",
        '"vajegan-nl"."Regelmatige_Werkwoorden"',
        [("example_present_nl", "example_present_fa", "present"),
         ("example_past_nl", "example_past_fa", "past"),
         ("example_perfect_nl", "example_perfect_fa", "perfect")],
    ),
    (
        "irregular_verb",
        '"vajegan-nl"."Onregelmatige_Werkwoorden"',
        [("example_present_nl", "example_present_fa", "present"),
         ("example_past_nl", "example_past_fa", "past"),
         ("example_perfect_nl", "example_perfect_fa", "perfect")],
    ),
]

_FASL_RE = re.compile(r"^fasl_(\d{2,})_+([a-z0-9_]+)$")
_NUM_RE = re.compile(r"^\s*\d+\s*[.)]\s*")  # leading "1." / "2)" numbering
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
# Persian translation sits in the final parentheses; capture it as group 2.
_PAREN_RE = re.compile(r"^(.*)[(（]([^()（）]*)[)）]\s*$", re.S)


def parse_examples(raw: str | None) -> list[tuple[str, str | None]]:
    """Parse a worden ``examples`` cell into [(dutch, persian|None), ...]."""
    if not raw:
        return []
    out: list[tuple[str, str | None]] = []
    for part in _BR_RE.split(raw):
        part = _NUM_RE.sub("", part.strip()).strip()
        if not part:
            continue
        m = _PAREN_RE.match(part)
        if m:
            dutch, persian = m.group(1).strip(), m.group(2).strip() or None
        else:
            dutch, persian = part, None
        if dutch:
            out.append((dutch, persian))
    return out


CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id           SERIAL PRIMARY KEY,
    dutch        TEXT NOT NULL,
    persian      TEXT,
    source       TEXT NOT NULL,
    source_table TEXT,
    source_id    INTEGER,
    tense        TEXT
)
"""


async def main() -> None:
    url = get_settings().database.vocab_database_url
    if not url:
        print("❌ VOCAB_DATABASE_URL is not configured.")
        return
    engine = create_async_engine(url, pool_pre_ping=True)

    async with engine.begin() as conn:
        await conn.execute(text(CREATE_SQL))
        await conn.execute(text(f"TRUNCATE {TABLE} RESTART IDENTITY"))

        # --- Verb tables: server-side INSERT ... SELECT (fast) ---------------
        verb_total = 0
        for source, tbl, columns in VERB_SOURCES:
            for nl_col, fa_col, tense in columns:
                res = await conn.execute(
                    text(
                        f"INSERT INTO {TABLE} (dutch, persian, source, source_table, source_id, tense) "
                        f"SELECT {nl_col}, {fa_col}, :src, :tbl, id, :tense "
                        f"FROM {tbl} WHERE {nl_col} IS NOT NULL AND btrim({nl_col}) <> ''"
                    ),
                    {"src": source, "tbl": tbl, "tense": tense},
                )
                verb_total += res.rowcount or 0
            print(f"  ✓ {source}: {verb_total} (cumulative)")

        # --- Worden chapter vocabulary: parse in Python ----------------------
        tables = [
            r[0]
            for r in (
                await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'worden'"
                    )
                )
            ).all()
        ]
        fasl = sorted(t for t in tables if _FASL_RE.match(t))

        worden_total = 0
        batch: list[dict[str, object]] = []
        insert_sql = text(
            f"INSERT INTO {TABLE} (dutch, persian, source, source_table, source_id, tense) "
            "VALUES (:dutch, :persian, 'worden', :tbl, :sid, NULL)"
        )
        for t in fasl:
            cols = [
                c[0]
                for c in (
                    await conn.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema='worden' AND table_name=:t"
                        ),
                        {"t": t},
                    )
                ).all()
            ]
            if "examples" not in cols:
                continue
            rows = (
                await conn.execute(text(f'SELECT id, examples FROM worden."{t}"'))
            ).all()
            for row_id, raw in rows:
                for dutch, persian in parse_examples(raw):
                    batch.append(
                        {"dutch": dutch, "persian": persian, "tbl": t, "sid": row_id}
                    )
                    worden_total += 1
            if len(batch) >= 1000:
                await conn.execute(insert_sql, batch)
                batch.clear()
        if batch:
            await conn.execute(insert_sql, batch)

        grand = await conn.scalar(text(f"SELECT count(*) FROM {TABLE}"))

    print(f"  ✓ worden: {worden_total}")
    print("-" * 40)
    print(f"✅ {TABLE} built. total sentences: {grand}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
