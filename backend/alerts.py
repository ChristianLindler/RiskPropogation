from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from backend.config import ALERT_MIN_BAND_RANK, BAND_RANK
from backend.graph import Graph
from backend.propagation import AffectedEntity
from backend.subscriptions import SubscriptionIndex

TriggerKind = Literal["new_entity", "score_update"]


def _should_alert(old_band: str, new_band: str) -> bool:
    return (
        BAND_RANK[new_band] > BAND_RANK[old_band]
        and BAND_RANK[new_band] >= ALERT_MIN_BAND_RANK
    )


def _format_path(graph: Graph, path: list[str]) -> list[str]:
    return [graph.get_entity(eid).name if graph.get_entity(eid) else eid for eid in path]


def _summarize_cause(
    graph: Graph,
    path_ids: list[str],
    trigger_name: str,
    affected_name: str,
    trigger_kind: TriggerKind,
) -> str:
    names = _format_path(graph, path_ids)
    via = [n for n in names[1:-1] if n != affected_name]

    if trigger_kind == "score_update":
        lead = f"Risk score update on {trigger_name} increased risk for {affected_name}"
    else:
        lead = f"New entity {trigger_name} increased risk for {affected_name}"

    if via:
        return f"{lead} via {' → '.join(via)}"
    return lead


def build_alerts(
    graph: Graph,
    subscriptions: SubscriptionIndex,
    affected: list[AffectedEntity],
    source_entity_id: str,
    *,
    trigger_kind: TriggerKind = "new_entity",
    source_change: AffectedEntity | None = None,
) -> list[dict[str, Any]]:
    source = graph.get_entity(source_entity_id)
    trigger_name = source.name if source else source_entity_id
    timestamp = datetime.now(timezone.utc).isoformat()

    alerts: list[dict[str, Any]] = []

    # A watched entity whose score was set directly should notify on itself,
    # regardless of band crossing — the change was a deliberate backend action.
    if source_change is not None:
        for watchlist_id in subscriptions.watchlists_for(source_change.id):
            watchlist = subscriptions.watchlist_by_id(watchlist_id)
            if watchlist is None:
                continue
            alerts.append(
                {
                    "watchlist_id": watchlist_id,
                    "watchlist_name": watchlist.name,
                    "entity_id": source_change.id,
                    "entity_name": source_change.name,
                    "trigger_id": source_change.id,
                    "trigger_name": source_change.name,
                    "trigger_kind": "score_update",
                    "old_band": source_change.old_band,
                    "new_band": source_change.new_band,
                    "old_risk": round(source_change.old_risk, 4),
                    "new_risk": round(source_change.new_risk, 4),
                    "delta": round(source_change.delta, 4),
                    "cause": {
                        "summary": f"Risk score for {source_change.name} was updated directly on the backend"
                    },
                    "timestamp": timestamp,
                }
            )

    for item in affected:
        watching = subscriptions.watchlists_for(item.id)
        for watchlist_id in watching:
            watchlist = subscriptions.watchlist_by_id(watchlist_id)
            if watchlist is None:
                continue
            if not _should_alert(item.old_band, item.new_band):
                continue

            path_ids = item.paths[0] if item.paths else [source_entity_id, item.id]
            summary = _summarize_cause(
                graph, path_ids, trigger_name, item.name, trigger_kind
            )

            alerts.append(
                {
                    "watchlist_id": watchlist_id,
                    "watchlist_name": watchlist.name,
                    "entity_id": item.id,
                    "entity_name": item.name,
                    "trigger_id": source_entity_id,
                    "trigger_name": trigger_name,
                    "trigger_kind": trigger_kind,
                    "old_band": item.old_band,
                    "new_band": item.new_band,
                    "old_risk": round(item.old_risk, 4),
                    "new_risk": round(item.new_risk, 4),
                    "delta": round(item.delta, 4),
                    "cause": {"summary": summary},
                    "timestamp": timestamp,
                }
            )

    return alerts
