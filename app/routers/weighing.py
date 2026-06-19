from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import ReviewStatus, WeighingStatus
from app.schemas.schemas import (
    ReviewApprove,
    ReviewRead,
    WeighingInbound,
    WeighingOutbound,
    WeighingRead,
)
from app.services.weighing_service import ReviewService, WeighingService

router = APIRouter(prefix="/api/weighing", tags=["称重与复核"])


@router.post("/{dispatch_id}/outbound", response_model=WeighingRead)
async def record_outbound(dispatch_id: UUID, data: WeighingOutbound, db: AsyncSession = Depends(get_db)):
    svc = WeighingService(db)
    try:
        return await svc.record_outbound(dispatch_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{dispatch_id}/inbound", response_model=WeighingRead)
async def record_inbound(dispatch_id: UUID, data: WeighingInbound, db: AsyncSession = Depends(get_db)):
    svc = WeighingService(db)
    try:
        return await svc.record_inbound(dispatch_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/records", response_model=list[WeighingRead])
async def list_weighings(status: WeighingStatus | None = None, db: AsyncSession = Depends(get_db)):
    svc = WeighingService(db)
    return await svc.list_weighings(status)


@router.get("/records/{weighing_id}", response_model=WeighingRead)
async def get_weighing(weighing_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = WeighingService(db)
    record = await svc.get_weighing(weighing_id)
    if record is None:
        raise HTTPException(status_code=404, detail="称重记录不存在")
    return record


@router.get("/reviews", response_model=list[ReviewRead])
async def list_reviews(status: ReviewStatus | None = None, db: AsyncSession = Depends(get_db)):
    svc = ReviewService(db)
    return await svc.list_reviews(status)


@router.get("/reviews/{review_id}", response_model=ReviewRead)
async def get_review(review_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = ReviewService(db)
    review = await svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="复核单不存在")
    return review


@router.post("/reviews/{review_id}/approve", response_model=ReviewRead)
async def approve_review(review_id: UUID, data: ReviewApprove, db: AsyncSession = Depends(get_db)):
    svc = ReviewService(db)
    try:
        return await svc.approve_review(review_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
