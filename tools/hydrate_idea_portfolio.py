#!/usr/bin/env python3
"""Validate or apply an IdeaOS portfolio hydration envelope to CEG.

Dry-run is the default. ``--apply`` is required for graph mutation.

Examples:
    python tools/hydrate_idea_portfolio.py hydration.json
    python tools/hydrate_idea_portfolio.py hydration.json --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.config.loader import DomainPackLoader
from engine.graph.driver import GraphDriver
from engine.sync.idea_portfolio import (
    DOMAIN_ID,
    IdeaPortfolioHydrationEnvelope,
    IdeaPortfolioHydrator,
    compile_hydration_plan,
)


def _load_envelope(path: Path) -> IdeaPortfolioHydrationEnvelope:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return IdeaPortfolioHydrationEnvelope.model_validate(raw)


def _dry_run(envelope: IdeaPortfolioHydrationEnvelope) -> dict[str, object]:
    plan = compile_hydration_plan(envelope)
    return {
        "schema": "ceg.idea-portfolio-hydration-plan/v1",
        "status": "validated",
        "domain": DOMAIN_ID,
        "source_snapshot_ref": envelope.source_snapshot_ref,
        "source_snapshot_digest": envelope.source_snapshot_digest,
        "expected_graph_revision": envelope.expected_graph_revision,
        "batch_digest": plan.batch_digest,
        "graph_revision": plan.graph_revision,
        "records": [
            {"idea_id": record.resolved_idea_id, "operation": record.operation}
            for record in envelope.records
        ],
    }


async def _apply(envelope: IdeaPortfolioHydrationEnvelope) -> dict[str, object]:
    # Loading through the production loader proves the folder-shaped domain pack
    # is discoverable and validates against the current DomainSpec before writes.
    DomainPackLoader(config_path=str(ROOT / "domains")).load_domain(DOMAIN_ID)

    driver = GraphDriver()
    await driver.connect()
    try:
        return await IdeaPortfolioHydrator(driver).apply(envelope)
    finally:
        await driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or apply an IdeaOS -> CEG portfolio hydration envelope")
    parser.add_argument("envelope", type=Path, help="Path to ceg.idea-portfolio-hydration/v1 JSON")
    parser.add_argument("--apply", action="store_true", help="Mutate the CEG idea-portfolio graph")
    args = parser.parse_args()

    envelope = _load_envelope(args.envelope)
    result = asyncio.run(_apply(envelope)) if args.apply else _dry_run(envelope)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
