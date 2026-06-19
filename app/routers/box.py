from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import BoxStatus
from app.schemas.schemas import BoxCreate, BoxRead, BoxRegisterFull, StationCreate, StationRead
from app.services.box_service import BoxService

router = APIRouter(prefix="/api/stations", tags=["站点与压缩箱"])


@router.post("", response_model=StationRead, status_code=201)
async def create_station(data: StationCreate, db: AsyncSession = Depends(get_db)):
    svc = BoxService(db)
    return await svc.create_station(data)


@router.get("", response_model=list[StationRead])
async def list_stations(db: AsyncSession = Depends(get_db)):
    svc = BoxService(db)
    return await svc.list_stations()


@router.post("/boxes", response_model=BoxRead, status_code=201)
async def create_box(data: BoxCreate, db: AsyncSession = Depends(get_db)):
    svc = BoxService(db)
    try:
        return await svc.create_box(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/boxes", response_model=list[BoxRead])
async def list_boxes(
    station_id: UUID | None = None,
    status: BoxStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = BoxService(db)
    return await svc.list_boxes(station_id, status)


@router.post("/boxes/{box_id}/register-full", response_model=BoxRead)
async def register_full(box_id: UUID, data: BoxRegisterFull, db: AsyncSession = Depends(get_db)):
    svc = BoxService(db)
    try:
        return await svc.register_full(box_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
