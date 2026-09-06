"""Criminal-intelligence graph API.

Read-only endpoints over the graph store abstraction. Responses are identical
regardless of the configured backend (relational default, optional Neo4j).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission, scope_unit_ids
from app.database.session import get_db
from app.graph.store import get_graph_store
from app.models.user import User

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/overview")
def graph_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = get_graph_store(db)
    overview = store.overview()
    overview["backend"] = store.backend
    return overview


@router.get("/entities")
def graph_entities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    entity_type: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    store = get_graph_store(db)
    if q:
        return {"items": store.search(q, limit=limit)}
    return {"items": store.entities(entity_type=entity_type, limit=limit)}


@router.get("/relationships")
def graph_relationships(
    entity_id: str | None = Query(None),
    depth: int = Query(1, ge=1, le=3),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = get_graph_store(db)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id is required")
    try:
        return store.neighbors(entity_id, depth=depth)
    except Exception as exc:  # pragma: no cover - backend dependent
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/central")
def graph_central(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = get_graph_store(db)
    return {"items": store.central(limit=limit)}


@router.get("/communities")
def graph_communities(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = get_graph_store(db)
    try:
        return {"items": store.communities(limit=limit)}
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/connectivity")
def graph_connectivity(
    entity_a: str = Query(...),
    entity_b: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = get_graph_store(db)
    result = store.path_between(entity_a, entity_b)
    if not result:
        raise HTTPException(status_code=404, detail="no path between the two entities")
    return {"path": result, "hops": len(result) - 1}


@router.get("/search")
def graph_search(
    q: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = get_graph_store(db)
    return {"items": store.search(q, limit=limit)}