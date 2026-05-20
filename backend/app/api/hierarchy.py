from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.api.auth import get_current_user, get_optional_user
from app.schemas.game import HierarchyCreate, HierarchyResponse
from app.services.hierarchy_service import hierarchy_service

router = APIRouter(prefix="/hierarchy", tags=["hierarchy"])


@router.post("")
async def create_hierarchy(data: HierarchyCreate, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    try:
        relation = await hierarchy_service.create_hierarchy(
            db, data.parent_agent_id, data.child_agent_id,
            data.relation_type, data.context_id,
        )
        return {
            "id": str(relation.id),
            "parent_agent_id": str(relation.parent_agent_id),
            "child_agent_id": str(relation.child_agent_id),
            "relation_type": relation.relation_type,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{agent_id}")
async def get_hierarchy_tree(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        tree = await hierarchy_service.get_hierarchy_tree(db, agent_id)
        return tree
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
