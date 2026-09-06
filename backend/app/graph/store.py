"""GraphStore abstraction for the Criminal Intelligence dashboard.

Two backends behind one interface:
  - ``RelationalGraphStore`` (default): GraphNode/GraphEdge tables via SQLAlchemy.
    Zero extra dependencies; centrality = degree, communities = connected
    components computed in Python.
  - ``Neo4jGraphStore`` (optional): enabled with ``GRAPH_BACKEND=neo4j``. Uses
    the ``neo4j`` driver if installed; raises a clear error otherwise. It mirrors
    the same entity/relationship model so the API surface is identical.

Feature-flag rule: the default store knows nothing about Neo4j unless the env
var opts in, and swapping backends must not change the API responses.
"""

import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.graph_node import GraphEdge, GraphNode

RELATION = {
    "case_involves_person": "INVOLVES",
    "case_assoc_phone": "ASSOCIATED",
    "case_assoc_email": "ASSOCIATED",
    "case_assoc_vehicle": "ASSOCIATED",
    "case_assoc_account": "ASSOCIATED",
    "case_located": "LOCATED",
    "person_has_phone": "HAS",
    "person_has_email": "HAS",
    "person_has_vehicle": "HAS",
    "person_has_account": "HAS",
    "person_financial_to_person": "FUNDS",
    "phone_contacts_phone": "CONTACTS",
    "shared": "SHARED",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class GraphStore:
    backend = "base"

    def create_node(self, entity_type: str, value: str, name: str | None = None, properties: dict | None = None) -> Any: ...  # type: ignore[empty-body]  # noqa: E704

    def create_edge(self, source_id: str, target_id: str, relation: str, event_row_id: str | None = None, source_text: str | None = None) -> None: ...  # type: ignore[empty-body]  # noqa: E704

    def overview(self) -> dict: ...  # type: ignore[empty-body]  # noqa: E704

    def search(self, q: str, limit: int = 20) -> list: ...  # type: ignore[empty-body]  # noqa: E704

    def entities(self, entity_type: str | None = None, limit: int = 50) -> list: ...  # type: ignore[empty-body]  # noqa: E704

    def neighbors(self, entity_id: str, depth: int = 1) -> dict: ...  # type: ignore[empty-body]  # noqa: E704

    def central(self, limit: int = 20) -> list: ...  # type: ignore[empty-body]  # noqa: E704

    def communities(self, limit: int = 20) -> list: ...  # type: ignore[empty-body]  # noqa: E704

    def path_between(self, entity_a: str, entity_b: str) -> list: ...  # type: ignore[empty-body]  # noqa: E704


class RelationalGraphStore(GraphStore):
    backend = "relational"

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- writes ----------------------------------------------------------
    def create_node(self, entity_type: str, value: str, name: str | None = None, properties: dict | None = None) -> dict:
        node = (
            self.db.query(GraphNode)
            .filter(GraphNode.entity_type == entity_type, GraphNode.value == value)
            .first()
        )
        if node is not None:
            if properties and node.properties:
                merged = dict(node.properties)
                merged.update(properties)
                node.properties = merged
                self.db.add(node)
        else:
            node = GraphNode(
                id=_new_id(),
                entity_type=entity_type,
                value=value,
                name=name or value,
                properties=properties or {},
                created_at=_now(),
            )
            self.db.add(node)
            self.db.flush()
        return {
            "id": node.id,
            "entity_type": node.entity_type,
            "value": node.value,
            "name": node.name or node.value,
            "properties": node.properties or {},
        }

    def create_edge(self, source_id: str, target_id: str, relation: str, event_row_id: str | None = None, source_text: str | None = None) -> None:
        existing = (
            self.db.query(GraphEdge)
            .filter(
                GraphEdge.source_id == source_id,
                GraphEdge.target_id == target_id,
                GraphEdge.relation == relation,
            )
            .first()
        )
        if existing is not None:
            existing.weight += 1
            if event_row_id and not existing.event_row_id:
                existing.event_row_id = event_row_id
            self.db.add(existing)
            self.db.flush()
            return
        self.db.add(
            GraphEdge(
                id=_new_id(),
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                weight=1,
                event_row_id=event_row_id,
                source_text=source_text[:1000] if source_text else None,
                created_at=_now(),
            )
        )
        self.db.flush()

    # -- reads -----------------------------------------------------------
    def _node_dict(self, node: GraphNode, degree: int | None = None) -> dict:
        return {
            "id": node.id,
            "entity_type": node.entity_type,
            "value": node.value,
            "name": node.name or node.value,
            "properties": node.properties or {},
            "degree": degree,
        }

    def overview(self) -> dict:
        node_count = self.db.query(GraphNode).count()
        edge_count = self.db.query(GraphEdge).count()
        return {
            "nodes": node_count,
            "edges": edge_count,
            "entity_types": {
                row[0]: row[1]
                for row in self.db.query(
                    GraphNode.entity_type, func.count(GraphNode.id)
                )
                .group_by(GraphNode.entity_type)
                .all()
            },
        }

    def search(self, q: str, limit: int = 20) -> list:
        ql = q.lower().strip()
        if not ql:
            return []
        rows = (
            self.db.query(GraphNode)
            .filter(
                GraphNode.name.ilike(f"%{ql}%")
                | GraphNode.value.ilike(f"%{ql}%")
                | GraphNode.entity_type.ilike(f"%{ql}%")
            )
            .limit(limit)
            .all()
        )
        return [self._node_dict(r, self._degree(r.id)) for r in rows]

    def entities(self, entity_type: str | None = None, limit: int = 50) -> list:
        query = self.db.query(GraphNode)
        if entity_type:
            query = query.filter(GraphNode.entity_type == entity_type)
        rows = query.order_by(GraphNode.created_at.desc()).limit(limit).all()
        return [self._node_dict(r, self._degree(r.id)) for r in rows]

    def _degree(self, node_id: str) -> int:
        return (
            self.db.query(GraphEdge)
            .filter((GraphEdge.source_id == node_id) | (GraphEdge.target_id == node_id))
            .count()
        )

    def neighbors(self, entity_id: str, depth: int = 1) -> dict:
        seen = set()
        result: dict[str, Any] = {}
        frontier = [entity_id]
        result["nodes"] = {}
        result["edges"] = []
        for _ in range(depth):
            if not frontier:
                break
            nxt: set[str] = set()
            out = (
                self.db.query(GraphEdge)
                .filter(GraphEdge.source_id.in_(frontier))
                .all()
            )
            inn = (
                self.db.query(GraphEdge)
                .filter(GraphEdge.target_id.in_(frontier))
                .all()
            )
            for e in out + inn:
                a, b = e.source_id, e.target_id
                result["edges"].append(
                    {
                        "source": a,
                        "target": b,
                        "relation": e.relation,
                        "weight": e.weight,
                    }
                )
                for nid in (a, b):
                    seen.add(nid)
                    nxt.add(nid)
            frontier = [n for n in nxt if n not in result["nodes"]]
        for nid in seen:
            node = self.db.get(GraphNode, nid)
            if node is not None:
                result["nodes"][nid] = self._node_dict(node, self._degree(nid))
        return result

    def central(self, limit: int = 20) -> list:
        rows = self.db.query(GraphNode).all()
        degrees = {
            nid: c
            for nid, c in self.db.query(GraphEdge.source_id, func.count(GraphEdge.id))
            .group_by(GraphEdge.source_id)
            .all()
        }
        in_deg = {
            nid: c
            for nid, c in self.db.query(GraphEdge.target_id, func.count(GraphEdge.id))
            .group_by(GraphEdge.target_id)
            .all()
        }
        total = defaultdict(int)
        for nid, c in degrees.items():
            total[nid] += c
        for nid, c in in_deg.items():
            total[nid] += c
        ranked = sorted(rows, key=lambda r: total.get(r.id, 0), reverse=True)
        return [self._node_dict(r, total.get(r.id, 0)) for r in ranked[:limit]]

    def communities(self, limit: int = 20) -> list:
        parent: dict[str, str] = {}
        size: dict[str, int] = {}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]

        for node in self.db.query(GraphNode).all():
            parent[node.id] = node.id
            size[node.id] = 1
        for e in self.db.query(GraphEdge).all():
            union(e.source_id, e.target_id)

        groups: dict[str, list[str]] = defaultdict(list)
        for nid in parent:
            groups[find(nid)].append(nid)

        members: dict[str, list[dict]] = {
            root: [
                self._node_dict(n, self._degree(n.id))
                for n in self.db.query(GraphNode).filter(GraphNode.id.in_(ids)).all()
            ]
            for root, ids in groups.items()
        }
        ordered = sorted(groups.items(), key=lambda kv: (len(kv[1]), kv[0]), reverse=True)
        return [
            {
                "id": root,
                "size": len(ids),
                "entities": members[root],
            }
            for root, ids in ordered[:limit]
        ]

    def path_between(self, entity_a: str, entity_b: str) -> list:
        if entity_a == entity_b:
            return [self._node_dict(self.db.get(GraphNode, entity_a))]
        adj: dict[str, list[str]] = defaultdict(list)
        for e in self.db.query(GraphEdge).all():
            adj[e.source_id].append((e.target_id, e))
            adj[e.target_id].append((e.source_id, e))
        prev: dict[str, str | None] = {entity_a: None}
        q = deque([entity_a])
        while q:
            cur = q.popleft()
            if cur == entity_b:
                break
            for nxt, _e in adj.get(cur, []):
                if nxt not in prev:
                    prev[nxt] = cur
                    q.append(nxt)
        if entity_b not in prev:
            return []
        chain: list[str] = []
        cur: str | None = entity_b
        while cur is not None:
            chain.append(cur)
            cur = prev.get(cur)
        chain.reverse()
        return [self._node_dict(self.db.get(GraphNode, nid)) for nid in chain]


def get_graph_store(db: Session) -> GraphStore:
    """Default-style store selection; Neo4j requires explicit opt-in."""
    if get_settings().GRAPH_BACKEND.lower().strip() == "neo4j":
        return Neo4jGraphStore(db)
    return RelationalGraphStore(db)


class Neo4jGraphStore(GraphStore):
    """Optional adapter. Kept additive: relational remains the only default."""

    backend = "neo4j"

    def __init__(self, db: Session) -> None:
        self.db = db
        try:
            from neo4j import GraphDatabase  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "GRAPH_BACKEND=neo4j requires the 'neo4j' driver: pip install neo4j"
            ) from exc
        s = get_settings()
        self.driver = GraphDatabase.driver(s.NEO4J_URI, auth=(s.NEO4J_USER, s.NEO4J_PASSWORD))

    def _label(self, entity_type: str) -> str:
        return entity_type.upper().replace(" ", "_")

    def create_node(self, entity_type: str, value: str, name: str | None = None, properties: dict | None = None) -> dict:
        label = self._label(entity_type)
        with self.driver.session() as session:
            record = session.run(
                f"MERGE (n:{label} {{value: $value}}) "
                "ON CREATE SET n.name = $name, n.properties = $props "
                "ON MATCH SET n.name = $name, n.properties = n.properties + $props "
                "RETURN elementId(n) AS id",
                value=value, name=name or value, props=properties or {},
            ).single()
        nid = record["id"] if record else value
        return {"id": nid, "entity_type": entity_type, "value": value, "name": name or value, "properties": properties or {}}

    def create_edge(self, source_id: str, target_id: str, relation: str, event_row_id: str | None = None, source_text: str | None = None) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (a) WHERE elementId(a) = $a "
                "MATCH (b) WHERE elementId(b) = $b "
                "MERGE (a)-[r:REL {relation: $rel}]->(b) "
                "ON CREATE SET r.weight = 1, r.event_row_id = $event_row_id "
                "ON MATCH SET r.weight = coalesce(r.weight, 0) + 1",
                a=source_id, b=target_id, rel=relation, event_row_id=event_row_id,
            )

    def overview(self) -> dict:
        with self.driver.session() as session:
            nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            edges = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        return {"nodes": nodes, "edges": edges, "entity_types": {}}

    def search(self, q: str, limit: int = 20) -> list:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($q) OR toLower(n.value) CONTAINS toLower($q) "
                "RETURN elementId(n) AS id, labels(n)[0] AS entity_type, n.value AS value, n.name AS name "
                "LIMIT $limit",
                q=q, limit=limit,
            )
            items = []
            for r in result:
                items.append({"id": r["id"], "entity_type": (r["entity_type"] or "").lower(), "value": r["value"], "name": r["name"], "degree": None})
            return items

    def entities(self, entity_type: str | None = None, limit: int = 50) -> list:
        with self.driver.session() as session:
            if entity_type:
                result = session.run(
                    "MATCH (n:$label) RETURN elementId(n) AS id, labels(n)[0] AS entity_type, "
                    "n.value AS value, n.name AS name LIMIT $limit",
                    label=entity_type.upper(), limit=limit,
                )
            else:
                result = session.run(
                    "MATCH (n) RETURN elementId(n) AS id, labels(n)[0] AS entity_type, "
                    "n.value AS value, n.name AS name LIMIT $limit",
                    limit=limit,
                )
            return [
                {"id": r["id"], "entity_type": (r["entity_type"] or "").lower(), "value": r["value"], "name": r["name"], "degree": None}
                for r in result
            ]

    def neighbors(self, entity_id: str, depth: int = 1) -> dict:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n)-[r*1..1]-(m) WHERE elementId(n) = $id "
                "RETURN elementId(n) AS a, elementId(m) AS b, type(r[0]) AS rel, r[0].weight AS weight, labels(m)[0] AS lbl, m.value AS value, m.name AS name",
                id=entity_id, depth=depth,
            )
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        for r in result:
            edges.append({"source": r["a"], "target": r["b"], "relation": r["rel"], "weight": r["weight"]})
            nodes[r["b"]] = {"id": r["b"], "entity_type": (r["lbl"] or "").lower(), "value": r["value"], "name": r["name"], "degree": None}
        return {"nodes": nodes, "edges": edges}

    def central(self, limit: int = 20) -> list:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n) RETURN elementId(n) AS id, labels(n)[0] AS lbl, n.value AS value, n.name AS name, "
                "size((n)--()) AS degree ORDER BY degree DESC LIMIT $limit",
                limit=limit,
            )
            return [{"id": r["id"], "entity_type": (r["lbl"] or "").lower(), "value": r["value"], "name": r["name"], "degree": r["degree"]} for r in result]

    def communities(self, limit: int = 20) -> list:
        raise NotImplementedError(
            "community detection is only supported on the relational backend"
        )

    def path_between(self, entity_a: str, entity_b: str) -> list:
        with self.driver.session() as session:
            result = session.run(
                "MATCH p = shortestPath((a)-[*]-(b)) WHERE elementId(a) = $a AND elementId(b) = $b "
                "RETURN [n IN nodes(p) | {id: elementId(n), value: n.value, name: n.name, entity_type: labels(n)[0]}] AS path",
                a=entity_a, b=entity_b,
            )
            rec = result.single()
            return rec["path"] if rec else []