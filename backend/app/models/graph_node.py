"""Criminal-intelligence graph nodes (relational backing store).

Nodes are deduplicated entities extracted from synthetic case records
(person, phone, email, vehicle, bank_account, location, case). The relational
store is the default GraphStore backend; a Neo4j adapter may be enabled via
the ``GRAPH_BACKEND`` setting (see ``app/graph/store.py``).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.types import JSON

from app.database.base import Base


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(String(32), primary_key=True)
    entity_type = Column(String(32), nullable=False, index=True)
    value = Column(String(256), nullable=False)
    name = Column(String(256), nullable=True)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("entity_type", "value", name="uq_graph_node_entity_value"),
        Index("ix_graph_node_search", "name"),
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(String(32), primary_key=True)
    source_id = Column(String(32), nullable=False, index=True)
    target_id = Column(String(32), nullable=False, index=True)
    relation = Column(String(64), nullable=False)
    weight = Column(Integer, nullable=False, default=1)
    event_row_id = Column(String(32), nullable=True)
    source_text = Column(String(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation", name="uq_graph_edge_src_tgt_rel"),
        Index("ix_graph_edge_pair", "source_id", "target_id"),
    )