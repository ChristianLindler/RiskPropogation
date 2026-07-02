# Risk Propagation Notification Demo

A small demo of risk propagating through a knowledge graph and watchlist-based alerts.

Ingest a new entity or update an existing one's risk. The engine walks the graph, updates scores on connected nodes, and pushes notifications when a **watched** entity crosses into medium or high risk.

Open **http://localhost:8000** for the UI. Run scenarios from a second terminal (reset between each). Slide graphics: [`docs/demo-graph.html`](docs/demo-graph.html).

---

## What it does

A risk team watches specific companies and people. When something new enters the graph — a flagged vendor, a risky director with a new board tie — risk can spread along ownership, supply-chain, and personnel links. The team needs to know **what triggered the change**, **who on their watchlist moved**, and **why**.

1. **Knowledge graph** — nodes (companies, people) and typed edges (`owns`, `supplies_to`, `affiliated_with`, …).
2. **Propagation** — bounded BFS from the ingested entity; decay per hop; weak ties die out.
3. **Watchlists** — thematic lists; only tracked entities can alert for that list.
4. **Alert threshold** — notify when risk crosses into **medium** or **high** (small low-band bumps are ignored).
5. **Explainable alerts** — e.g. *"New entity Risky Vendor increased risk for Sister Subsidiary via Risky Subsidiary → Parent Holding Co"*.

On load, all scores are low. Nothing alerts until you run a scenario.

---

## Run the app

```bash
cd RiskPropogation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open **http://localhost:8000**. Run **`POST /reset`** before each scenario below.

---

## Watchlists

| Watchlist | Entities tracked |
|-----------|------------------|
| **Corporate Family** | Parent Holding Co, Risky Subsidiary, Sister Subsidiary |
| **Third-Party Counterparties** | Clean Third Party, Supplier Co |
| **Board & Leadership Links** | Board Director, CEO Person |

---

## Demo scenarios

### Alerts expected

#### 1 — Risky Vendor (new entity, high risk)

A **new supplier at 90% risk** links to Risky Subsidiary. Risk propagates through the corporate family.

**Watch:** Corporate Family — Risky Subsidiary, Parent Holding Co, Sister Subsidiary.

```bash
curl -X POST http://localhost:8000/reset
curl -X POST http://localhost:8000/ingest-entity \
  -H "Content-Type: application/json" \
  -d @data/scenarios/ingest_risky_vendor.json
```

#### 2 — Risky Board Director (new entity, high risk)

A **new person at 90% risk** gains a board-style tie to Clean Third Party. The director is not on a watchlist; the alert is on the **watched** third party.

**Watch:** Third-Party Counterparties — Clean Third Party. Bell text: *"New entity Risky Board Director increased risk for Clean Third Party"*.

```bash
curl -X POST http://localhost:8000/reset
curl -X POST http://localhost:8000/ingest-entity \
  -H "Content-Type: application/json" \
  -d @data/scenarios/ingest_risky_board_director.json
```

#### 3 — Risky Subsidiary score update (optional)

Re-score an **existing** entity to 85%. Shows the update path and a cross-watchlist hit on Supplier Co.

```bash
curl -X POST http://localhost:8000/reset
curl -X POST http://localhost:8000/ingest-entity \
  -H "Content-Type: application/json" \
  -d @data/scenarios/update_risky_subsidiary.json
```

### No alerts expected

These ingest new entities into the graph, but risk stays below the alert threshold on all watchlist entities. Good contrast: *"not everything lights up the desk."*

#### 4 — Clean Advisor (new entity, low risk)

A **low-risk advisor (15%)** links to Clean Third Party. Propagation is too weak to push Clean Third Party into medium.

```bash
curl -X POST http://localhost:8000/reset
curl -X POST http://localhost:8000/ingest-entity \
  -H "Content-Type: application/json" \
  -d @data/scenarios/ingest_clean_advisor.json
```

#### 5 — Minor Vendor (new entity, low risk)

A **low-risk supplier (20%)** links to Risky Subsidiary. Corporate family scores may tick up slightly; no band crossing, no bell.

```bash
curl -X POST http://localhost:8000/reset
curl -X POST http://localhost:8000/ingest-entity \
  -H "Content-Type: application/json" \
  -d @data/scenarios/ingest_minor_vendor.json
```

---

## Suggested demo flow (~7 min)

1. Open dashboard — quiet graph.
2. **Risky Vendor** → Corporate Family + bell.
3. `reset` → **Risky Board Director** → Counterparties + bell (call out: trigger is a *risky* person at 90%).
4. `reset` → **Clean Advisor** → no bell (*threshold + weak signal*).
5. Optional: `reset` → **Risky Subsidiary update** → cross-watchlist Supplier Co.

---

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/graph` | Entities, watchlists, current risk |
| `POST` | `/reset` | Reload `data/graph.json` |
| `POST` | `/ingest-entity` | Add/update entity, propagate, emit alerts |
| `GET` | `/events` | SSE alert stream (UI) |

Same requests in `requests.http` for REST Client in VS Code/Cursor.

---

## Code layout

```
backend/     config, graph, propagation, subscriptions, alerts, main
data/        graph.json + scenarios/
frontend/    dashboard
docs/        demo-graph.html
```
