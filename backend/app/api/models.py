from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.model import Model, ModelCapability
from app.models.user import User
from app.schemas.model import ModelCreate, ModelUpdate, ModelResponse
from app.api.auth import get_current_user, get_optional_user

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/", response_model=List[ModelResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).order_by(Model.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=ModelResponse)
async def create_model(data: ModelCreate, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    model = Model(**data.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(model_id: UUID, db: AsyncSession = Depends(get_db)):
    model = await db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(model_id: UUID, data: ModelUpdate, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    model = await db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(model, key, value)
    await db.commit()
    await db.refresh(model)
    return model


@router.delete("/{model_id}")
async def delete_model(model_id: UUID, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    model = await db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await db.delete(model)
    await db.commit()
    return {"detail": "Deleted"}
