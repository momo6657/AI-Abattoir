from uuid import UUID
from typing import List
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.model import Model
from app.models.user import User
from app.schemas.model import ModelCreate, ModelUpdate, ModelResponse, ModelDiscoverRequest, ModelDiscoverResponse
from app.api.auth import get_optional_user

router = APIRouter(prefix="/models", tags=["models"])


def _derive_provider(api_base: str | None, fallback: str = "custom") -> str:
    if not api_base:
        return fallback
    parsed = urlparse(api_base)
    host = parsed.netloc or parsed.path.split("/")[0]
    host = host.split("@")[-1].split(":")[0].lower()
    if not host:
        return fallback
    known = {
        "api.openai.com": "openai",
        "api.anthropic.com": "anthropic",
        "generativelanguage.googleapis.com": "google",
        "api.deepseek.com": "deepseek",
    }
    return known.get(host, host[:50])


def _normalize_api_base(api_base: str) -> str:
    base = api_base.strip()
    if not base:
        raise HTTPException(status_code=400, detail="API URL 不能为空")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="API URL 格式无效")

    base = base.rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/models"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base.rstrip("/")


def _model_endpoint_candidates(api_base: str) -> list[tuple[str, str]]:
    base = _normalize_api_base(api_base)
    if base.endswith("/v1"):
        return [(base, f"{base}/models")]
    return [
        (f"{base}/v1", f"{base}/v1/models"),
        (base, f"{base}/models"),
    ]


async def _fetch_model_ids(api_base: str, api_key: str | None) -> tuple[str, list[str]]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_error = "无法获取模型列表"
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        for normalized_base, url in _model_endpoint_candidates(api_base):
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                body = exc.response.text[:200]
                last_error = f"{url} 返回 HTTP {status_code}: {body}"
                continue
            except (httpx.RequestError, ValueError) as exc:
                last_error = f"{url} 请求失败: {str(exc)[:200]}"
                continue

            raw_models = payload.get("data") if isinstance(payload, dict) else payload
            if isinstance(payload, dict) and raw_models is None:
                raw_models = payload.get("models")

            model_ids: list[str] = []
            if isinstance(raw_models, list):
                for item in raw_models:
                    if isinstance(item, str):
                        model_ids.append(item)
                    elif isinstance(item, dict) and item.get("id"):
                        model_ids.append(str(item["id"]))

            model_ids = sorted(set(mid for mid in model_ids if mid))
            if model_ids:
                return normalized_base, model_ids
            last_error = f"{url} 未返回可识别的模型 ID"

    raise HTTPException(status_code=502, detail=last_error)


@router.get("/", response_model=List[ModelResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).order_by(Model.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=ModelResponse)
async def create_model(data: ModelCreate, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    values = data.model_dump()
    values["api_base"] = _normalize_api_base(values["api_base"]) if values.get("api_base") else None
    values["provider"] = values.get("provider") or _derive_provider(values.get("api_base"))
    if values["provider"] == "custom":
        values["provider"] = _derive_provider(values.get("api_base"))
    model = Model(**values)
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.post("/discover", response_model=ModelDiscoverResponse)
async def discover_models(data: ModelDiscoverRequest):
    api_base, model_ids = await _fetch_model_ids(data.api_base, data.api_key)
    return ModelDiscoverResponse(
        api_base=api_base,
        provider=_derive_provider(api_base),
        models=model_ids,
    )


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
    values = data.model_dump(exclude_unset=True)
    if values.get("api_base"):
        values["api_base"] = _normalize_api_base(values["api_base"])
    if values.get("api_base") and not values.get("provider"):
        values["provider"] = _derive_provider(values["api_base"])
    if values.get("api_key") == "":
        values.pop("api_key")
    for key, value in values.items():
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
