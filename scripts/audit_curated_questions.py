"""Read-only audit of the curated Questions/ JSON tree before DB import.

Prints per-(level, section) coverage and every anomaly found (invalid JSON,
folder/internal-field mismatches, duplicate files in one topic folder). Makes
no DB connection and writes nothing — safe to run repeatedly while curating.

Usage::

    uv run python -m scripts.audit_curated_questions
"""

from __future__ import annotations

from scripts.curated_questions_loader import load_all, summarize


def main() -> None:
    buckets, anomalies = load_all()
    total_questions = sum(len(b.questions) for b in buckets)
    populated = [b for b in buckets if b.questions]
    empty = [b for b in buckets if not b.questions]

    print(f"Scanned {len(buckets)} topic folders")
    print(f"  populated: {len(populated)} topics, {total_questions} questions total")
    print(f"  empty/unauthored: {len(empty)} topics")
    print()

    print("Per (level, section):")
    for (level, section), stats in sorted(summarize(buckets).items()):
        print(
            f"  {level}/{section}: {stats['topics_ok']} topics with content "
            f"({stats['questions']} questions), {stats['topics_empty']} still empty"
        )

    if anomalies:
        from collections import Counter

        counts = Counter((a.path, a.reason) for a in anomalies)
        print(f"\nAnomalies ({len(counts)} unique, {len(anomalies)} total):")
        for (path, reason), count in counts.items():
            suffix = f"  [x{count}]" if count > 1 else ""
            print(f"  - {path}\n      {reason}{suffix}")
    else:
        print("\nNo anomalies found.")


if __name__ == "__main__":
    main()
