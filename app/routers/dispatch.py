from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import DispatchStatus, PriorityLevel, QueueStatus, VehicleStatus
from app.rules.business_rules import BusinessRuleViolation
from app.schemas.schemas import (
    DispatchCreate,
    DispatchDepart,
    DispatchRead,
    QueueCreate,
    QueueRead,
    VehicleCreate,
    VehicleDisinfect,
    VehicleRead,
)
from app.services.dispatch_service import DispatchService

router = APIRouter(prefix="/api/dispatch", tags=["车队调度"])


@router.post("/vehicles", response_model=VehicleRead, status_code=201)
async def create_vehicle(data: VehicleCreate, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    return await svc.create_vehicle(data)


@router.get("/vehicles", response_model=list[VehicleRead])
async def list_vehicles(status: VehicleStatus | None = None, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    return await svc.list_vehicles(status)


@router.post("/vehicles/{vehicle_id}/disinfection", response_model=VehicleRead)
async def complete_disinfection(vehicle_id: UUID, data: VehicleDisinfect, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    try:
        return await svc.complete_disinfection(vehicle_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/queue", response_model=QueueRead, status_code=201)
async def enqueue(data: QueueCreate, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    try:
        return await svc.enqueue(data)
    except (ValueError, BusinessRuleViolation) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/queue", response_model=list[QueueRead])
async def list_queue(status: QueueStatus | None = None, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    return await svc.list_queue(status)


@router.post("/orders", response_model=DispatchRead, status_code=201)
async def create_dispatch(data: DispatchCreate, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    try:
        return await svc.dispatch(data)
    except (ValueError, BusinessRuleViolation) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders", response_model=list[DispatchRead])
async def list_dispatches(status: DispatchStatus | None = None, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    return await svc.list_dispatches(status)


@router.post("/orders/{dispatch_id}/depart", response_model=DispatchRead)
async def depart(dispatch_id: UUID, data: DispatchDepart, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    try:
        return await svc.depart(dispatch_id, data.departure_weight_kg)
    except (ValueError, BusinessRuleViolation) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{dispatch_id}/arrive", response_model=DispatchRead)
async def arrive(dispatch_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = DispatchService(db)
    try:
        return await svc.arrive(dispatch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
