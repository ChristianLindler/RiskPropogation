"""Bounded BFS risk propagation

Given a risky entity, compute how much additional risk
reaches nearby nodes and why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.config import EPSILON, HOP_DECAY, MAX_HOPS, risk_band, transmission_factor
from backend.graph import Edge, Graph


@dataclass
class PathEdge:
    type: str
    justification: str
    from_id: str
    to_id: str


@dataclass
class AffectedEntity:
    id: str
    name: str
    old_risk: float
    new_risk: float
    old_band: str
    new_band: str
    paths: list[list[str]] = field(default_factory=list)
    path_edges: list[list[PathEdge]] = field(default_factory=list)

    @property
    def delta(self) -> float:
        return self.new_risk - self.old_risk


def _edge_for_traversal(from_id: str, to_id: str, incident: Edge) -> Edge:
    if incident.source == from_id and incident.target == to_id:
        return incident
    return Edge(
        source=from_id,
        target=to_id,
        type=incident.type,
        attributes=incident.attributes,
    )


def propagate(graph: Graph, risky_entity_id: str) -> list[AffectedEntity]:
    source_entity = graph.get_entity(risky_entity_id)
    if source_entity is None:
        return []

    old_risks = graph.snapshot_risks()
    working_risks = dict(old_risks)

    best_paths: dict[str, list[str]] = {}
    best_path_edges: dict[str, list[PathEdge]] = {}
    best_delta: dict[str, float] = {}

    queue: list[tuple[str, int, list[str], list[PathEdge]]] = [
        (risky_entity_id, 0, [risky_entity_id], [])
    ]
    enqueued: set[str] = {risky_entity_id}

    while queue:
        node_id, depth, path, path_edges = queue.pop(0)
        if depth >= MAX_HOPS:
            continue

        if graph.get_entity(node_id) is None:
            continue

        best_steps: dict[str, tuple[Edge, float, str]] = {}

        for neighbor_id, incident in graph.neighbors(node_id):
            if neighbor_id in path:
                continue

            step_edge = _edge_for_traversal(node_id, neighbor_id, incident)
            if graph.get_entity(neighbor_id) is None:
                continue

            factor, justification = transmission_factor(step_edge.type)
            hop_contribution = working_risks[node_id] * factor * HOP_DECAY
            if hop_contribution < EPSILON:
                continue

            prev = best_steps.get(neighbor_id)
            if prev is None or hop_contribution > prev[1]:
                best_steps[neighbor_id] = (step_edge, hop_contribution, justification)

        for neighbor_id, (step_edge, hop_contribution, justification) in best_steps.items():
            before = working_risks[neighbor_id]
            working_risks[neighbor_id] = min(1.0, before + hop_contribution)
            delta = working_risks[neighbor_id] - old_risks[neighbor_id]

            new_path = path + [neighbor_id]
            new_path_edges = path_edges + [
                PathEdge(
                    type=step_edge.type,
                    justification=justification,
                    from_id=node_id,
                    to_id=neighbor_id,
                )
            ]

            if delta > best_delta.get(neighbor_id, 0.0):
                best_delta[neighbor_id] = delta
                best_paths[neighbor_id] = new_path
                best_path_edges[neighbor_id] = new_path_edges

            if neighbor_id not in enqueued:
                enqueued.add(neighbor_id)
                queue.append((neighbor_id, depth + 1, new_path, new_path_edges))

    results: list[AffectedEntity] = []
    for entity_id, delta in best_delta.items():
        if delta <= 0:
            continue
        entity = graph.get_entity(entity_id)
        if entity is None:
            continue

        old = old_risks[entity_id]
        new = working_risks[entity_id]
        entity.current_risk = new
        results.append(
            AffectedEntity(
                id=entity_id,
                name=entity.name,
                old_risk=old,
                new_risk=new,
                old_band=risk_band(old),
                new_band=risk_band(new),
                paths=[best_paths.get(entity_id, [])],
                path_edges=[best_path_edges.get(entity_id, [])],
            )
        )

    return results
