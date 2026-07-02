"""FastAPI app"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.alerts import build_alerts
from backend.config import risk_band
from backend.graph import Edge, Entity, Graph
from backend.propagation import propagate
from backend.subscriptions import SubscriptionIndex

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "graph.json"
FRONTEND_PATH = Path(__file__).resolve().parent.parent / "frontend"

graph = Graph()
subscriptions = SubscriptionIndex(graph)
sse_queues: list[asyncio.Queue] = []


@asynccontextmanager
async def lifespan(_app: FastAPI):
    graph.load(DATA_PATH)
    subscriptions.rebuild()
    yield


app = FastAPI(title="Risk Propogation Notification Demo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RelationshipIn(BaseModel):
    target: str
    type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class IngestEntityIn(BaseModel):
    id: str
    name: str
    base_risk: float = 0.0
    attributes: dict[str, Any] = Field(default_factory=dict)
    relationships: list[RelationshipIn] = Field(default_factory=list)


@app.get("/graph")
def get_graph() -> JSONResponse:
    graph.reload_watchlists(DATA_PATH)
    subscriptions.rebuild()
    return JSONResponse(
        {
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "current_risk": e.current_risk,
                    "attributes": e.attributes,
                    "band": risk_band(e.current_risk),
                }
                for e in graph.entities.values()
            ],
            "watchlists": [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "entities": w.entities,
                }
                for w in graph.watchlists
            ],
        },
        headers={"Cache-Control": "no-store"},
    )


@app.post("/reset")
def reset_graph() -> dict[str, str]:
    graph.load(DATA_PATH)
    subscriptions.rebuild()
    return {"status": "ok"}


@app.post("/ingest-entity")
async def ingest_entity(body: IngestEntityIn) -> dict[str, Any]:
    for rel in body.relationships:
        if rel.target not in graph.entities:
            raise HTTPException(status_code=400, detail=f"Unknown target: {rel.target}")

    entity = Entity(body.id, body.name, body.base_risk, body.base_risk, body.attributes)
    edges = [
        Edge(body.id, rel.target, rel.type, rel.attributes) for rel in body.relationships
    ]
    is_update = body.id in graph.entities
    try:
        graph.add_entity(entity, edges, upsert=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    affected = propagate(graph, body.id)
    alerts = build_alerts(
        graph,
        subscriptions,
        affected,
        body.id,
        trigger_kind="score_update" if is_update else "new_entity",
    )
    for alert in alerts:
        for queue in sse_queues:
            await queue.put(alert)

    return {
        "ingested": body.id,
        "affected_entities": len(affected),
        "alerts_dispatched": len(alerts),
    }


@app.get("/events")
async def events_stream(request: Request) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue()
    sse_queues.append(queue)

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    alert = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(alert)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            sse_queues.remove(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.mount("/", StaticFiles(directory=str(FRONTEND_PATH), html=True), name="frontend")
