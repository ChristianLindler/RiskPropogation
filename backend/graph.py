"""Graph data structure"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Entity:
    id: str
    name: str
    base_risk: float = 0.0
    current_risk: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    type: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Watchlist:
    id: str
    name: str
    description: str
    entities: list[str]


class Graph:
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.out_edges: dict[str, list[Edge]] = {}
        self.in_edges: dict[str, list[Edge]] = {}
        self.watchlists: list[Watchlist] = []

    def load(self, path: Path | str) -> None:
        data = json.loads(Path(path).read_text())
        self.entities.clear()
        self.out_edges.clear()
        self.in_edges.clear()
        self.watchlists.clear()

        for raw in data["entities"]:
            entity = Entity(
                id=raw["id"],
                name=raw["name"],
                base_risk=raw.get("base_risk", 0.0),
                current_risk=raw.get("base_risk", 0.0),
                attributes=raw.get("attributes", {}),
            )
            self.entities[entity.id] = entity
            self.out_edges.setdefault(entity.id, [])
            self.in_edges.setdefault(entity.id, [])

        for raw in data["relationships"]:
            edge = Edge(
                source=raw["source"],
                target=raw["target"],
                type=raw["type"],
                attributes=raw.get("attributes", {}),
            )
            self.out_edges.setdefault(edge.source, []).append(edge)
            self.in_edges.setdefault(edge.target, []).append(edge)

        for raw in data["watchlists"]:
            self.watchlists.append(
                Watchlist(
                    id=raw["id"],
                    name=raw["name"],
                    description=raw.get("description", ""),
                    entities=raw["entities"],
                )
            )

    def reload_watchlists(self, path: Path | str) -> None:
        data = json.loads(Path(path).read_text())
        self.watchlists = [
            Watchlist(
                id=raw["id"],
                name=raw["name"],
                description=raw.get("description", ""),
                entities=raw["entities"],
            )
            for raw in data["watchlists"]
        ]

    def get_entity(self, entity_id: str) -> Entity | None:
        return self.entities.get(entity_id)

    def neighbors(self, entity_id: str) -> list[tuple[str, Edge]]:
        results: list[tuple[str, Edge]] = []
        for edge in self.out_edges.get(entity_id, []):
            results.append((edge.target, edge))
        for edge in self.in_edges.get(entity_id, []):
            results.append((edge.source, edge))
        return results

    def reset_risk(self) -> None:
        for entity in self.entities.values():
            entity.current_risk = entity.base_risk

    def add_entity(
        self,
        entity: Entity,
        relationships: list[Edge],
        *,
        upsert: bool = True,
    ) -> None:
        if entity.id in self.entities and upsert:
            existing = self.entities[entity.id]
            existing.name = entity.name
            existing.base_risk = entity.base_risk
            existing.attributes = entity.attributes
            existing.current_risk = max(existing.current_risk, entity.base_risk)
            stored = existing
        elif entity.id not in self.entities:
            self.entities[entity.id] = entity
            self.out_edges.setdefault(entity.id, [])
            self.in_edges.setdefault(entity.id, [])
            stored = entity
        else:
            raise ValueError(f"Entity {entity.id} already exists")

        if stored is entity:
            stored.current_risk = entity.base_risk

        seen = {
            (e.source, e.target, e.type)
            for edges in self.out_edges.values()
            for e in edges
        }
        for edge in relationships:
            if edge.target not in self.entities:
                raise ValueError(f"Unknown target entity: {edge.target}")
            if edge.source != entity.id:
                edge = Edge(entity.id, edge.target, edge.type, edge.attributes)
            key = (edge.source, edge.target, edge.type)
            if key in seen:
                continue
            seen.add(key)
            self.out_edges.setdefault(edge.source, []).append(edge)
            self.in_edges.setdefault(edge.target, []).append(edge)

    def snapshot_risks(self) -> dict[str, float]:
        return {eid: entity.current_risk for eid, entity in self.entities.items()}
