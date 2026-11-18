"""Failure triage step: run after pytest, before ``allure generate``.

    python -m allure_magic.triage allure-results [--llm] [--max-groups 20]

Reads ``*-result.json``, groups similar failures, classifies each group and writes
  * ``categories.json``  - Allure categories so the report buckets failures
  * ``global-info.json`` - summary rows for the Global Info widget (rows written by
                           previous triage runs are replaced, hand-written rows kept)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from .classify import Classifier, LLMClassifier, Verdict, classify_by_rules
from .global_info import GlobalInfoItem, load_global_info, write_global_info
from .results import FailureGroup, group_failures, load_failures

TRIAGE_PREFIX = "Triage: "
CATEGORY_TITLES = {
    "product_defect": "Product defects",
    "test_defect": "Test defects",
    "environment": "Environment issues",
    "unknown": "Unclassified failures",
}


def triage(
    results_dir: Path, classifier: Classifier = classify_by_rules, max_groups: int = 20
) -> List[Tuple[FailureGroup, Verdict]]:
    groups = group_failures(load_failures(results_dir))
    out = []
    for i, group in enumerate(groups):
        # groups are sorted by size, so the budget is spent on the biggest ones first
        verdict = classifier(group) if i < max_groups else classify_by_rules(group)
        out.append((group, verdict))
    return out


def build_categories(triaged: List[Tuple[FailureGroup, Verdict]]) -> list:
    categories = []
    for group, verdict in triaged:
        first = group.representative.message.strip().splitlines()
        regex = re.escape(first[0][:120]) + ".*" if first else ".*"
        categories.append(
            {
                "name": f"{CATEGORY_TITLES[verdict.category]}: {first[0][:60] if first else group.fingerprint}",
                "matchedStatuses": ["failed", "broken"],
                "messageRegex": regex,
            }
        )
    return categories


def build_global_info(triaged: List[Tuple[FailureGroup, Verdict]]) -> List[GlobalInfoItem]:
    if not triaged:
        return [GlobalInfoItem(TRIAGE_PREFIX + "summary", "No failures in this run")]
    counts: dict = {}
    for group, verdict in triaged:
        counts[verdict.category] = counts.get(verdict.category, 0) + group.size
    summary = ", ".join(f"{CATEGORY_TITLES[c]}: {n}" for c, n in sorted(counts.items()))
    items = [GlobalInfoItem(TRIAGE_PREFIX + "summary", summary)]
    for group, verdict in triaged:
        names = ", ".join(m.name for m in group.members[:3])
        more = f" (+{group.size - 3} more)" if group.size > 3 else ""
        items.append(
            GlobalInfoItem(
                f"{TRIAGE_PREFIX}{CATEGORY_TITLES[verdict.category]} x{group.size}",
                f"{verdict.reason} [{verdict.source}, {verdict.confidence:.0%}]\n{names}{more}",
            )
        )
    return items


def run(results_dir: Path, classifier: Classifier, max_groups: int, dry_run: bool) -> int:
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        print(f"error: {results_dir} is not a directory", file=sys.stderr)
        return 2
    triaged = triage(results_dir, classifier, max_groups)
    categories = build_categories(triaged)
    gi_path = results_dir / "global-info.json"
    kept = [i for i in load_global_info(gi_path) if not i.name.startswith(TRIAGE_PREFIX)]
    items = kept + build_global_info(triaged)
    if dry_run:
        print(json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2))
        return 0
    (results_dir / "categories.json").write_text(
        json.dumps(categories, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_global_info(items, gi_path)
    print(f"triaged {sum(g.size for g, _ in triaged)} failures in {len(triaged)} groups")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results_dir", nargs="?", default="allure-results")
    p.add_argument("--llm", action="store_true", help="classify with an LLM (needs `anthropic` + ANTHROPIC_API_KEY)")
    p.add_argument("--max-groups", type=int, default=20, help="cap on LLM calls per run (cost control)")
    p.add_argument("--dry-run", action="store_true", help="print global-info.json instead of writing files")
    args = p.parse_args(argv)
    classifier: Classifier = classify_by_rules
    if args.llm:
        try:
            classifier = LLMClassifier()
        except Exception as e:  # missing package / API key
            print(f"warning: LLM unavailable ({e}); using rules only", file=sys.stderr)
    return run(Path(args.results_dir), classifier, args.max_groups, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
