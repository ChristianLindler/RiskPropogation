from __future__ import annotations

from backend.graph import Graph, Watchlist


class SubscriptionIndex:
    def __init__(self, graph: Graph) -> None:
        self._graph = graph
        self._index: dict[str, set[str]] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self._index.clear()
        for watchlist in self._graph.watchlists:
            for entity_id in watchlist.entities:
                self._index.setdefault(entity_id, set()).add(watchlist.id)

    def watchlists_for(self, entity_id: str) -> set[str]:
        return set(self._index.get(entity_id, set()))

    def watchlist_by_id(self, watchlist_id: str) -> Watchlist | None:
        for watchlist in self._graph.watchlists:
            if watchlist.id == watchlist_id:
                return watchlist
        return None
