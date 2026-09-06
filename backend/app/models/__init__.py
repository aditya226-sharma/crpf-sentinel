"""Model registry. Import every table here so ``Base.metadata`` registers all
tables (used by app startup ``create_all`` and the test schema-reset).
"""

from app.database.base import Base
from app.models.agent import Agent
from app.models.alert import Alert, AlertEvent
from app.models.audit import AuditLog, Notification
from app.models.event import NormalizedEvent
from app.models.flow import Flow
from app.models.graph_node import GraphEdge, GraphNode
from app.models.incident import Incident, IncidentAlert, IncidentNote
from app.models.ioc import IocEntry
from app.models.log import Log
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.models.user import Role, User
from app.models.vpn_tunnel import VpnTunnel

__all__ = [
    "Agent",
    "Alert",
    "AlertEvent",
    "AuditLog",
    "DetectionRule",
    "GraphEdge",
    "GraphNode",
    "Incident",
    "IncidentAlert",
    "IncidentNote",
    "IocEntry",
    "Log",
    "NormalizedEvent",
    "Notification",
    "Role",
    "Unit",
    "User",
    "VpnTunnel",
    "Flow",
]