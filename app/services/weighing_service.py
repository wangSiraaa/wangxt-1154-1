from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    DispatchOrder,
    DispatchStatus,
    ReviewOrder,
    ReviewStatus,
    WeighingRecord,
    WeighingStatus,
)
from app.rules.business_rules import compute_weight_diff
from app.schemas.schemas import ReviewApprove, WeighingInbound, WeighingOutbound


class WeighingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_outbound(self, dispatch_id: UUID, data: WeighingOutbound) -> WeighingRecord:
        dispatch = await self.db.get(DispatchOrder, dispatch_id)
        if dispatch is None:
            raise ValueError(f"派车单 {dispatch_id} 不存在")
        if dispatch.status not in (DispatchStatus.DEPARTED, DispatchStatus.CREATED):
            raise ValueError(f"派车单状态为 {dispatch.status.value}，不能记录出站称重")

        existing = (
            await self.db.execute(select(WeighingRecord).where(WeighingRecord.dispatch_id == dispatch_id))
        ).scalar_one_or_none()

        if existing is not None and existing.station_outbound_weight_kg is not None:
            raise ValueError("该派车单已有出站称重记录")

        if existing is None:
            record = WeighingRecord(
                dispatch_id=dispatch_id,
                station_outbound_weight_kg=data.station_outbound_weight_kg,
                outbound_weighed_at=datetime.now(timezone.utc),
                status=WeighingStatus.OUTBOUND_ONLY,
            )
            self.db.add(record)
        else:
            existing.station_outbound_weight_kg = data.station_outbound_weight_kg
            existing.outbound_weighed_at = datetime.now(timezone.utc)
            existing.status = WeighingStatus.OUTBOUND_ONLY
            record = existing

        dispatch.departure_weight_kg = data.station_outbound_weight_kg
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def record_inbound(self, dispatch_id: UUID, data: WeighingInbound) -> WeighingRecord:
        dispatch = await self.db.get(DispatchOrder, dispatch_id)
        if dispatch is None:
            raise ValueError(f"派车单 {dispatch_id} 不存在")
        if dispatch.status != DispatchStatus.ARRIVED:
            raise ValueError(f"派车单状态为 {dispatch.status.value}，需要先到达才能进厂称重")

        record = (
            await self.db.execute(select(WeighingRecord).where(WeighingRecord.dispatch_id == dispatch_id))
        ).scalar_one_or_none()

        if record is None:
            raise ValueError("该派车单无出站称重记录，不能直接进厂称重")
        if record.station_outbound_weight_kg is None:
            raise ValueError("出站称重数据缺失，不能进厂称重")
        if record.plant_inbound_weight_kg is not None:
            raise ValueError("该派车单已有进厂称重记录")

        record.plant_inbound_weight_kg = data.plant_inbound_weight_kg
        record.inbound_weighed_at = datetime.now(timezone.utc)

        diff_result = compute_weight_diff(record.station_outbound_weight_kg, data.plant_inbound_weight_kg)
        record.weight_diff_kg = diff_result.diff_kg
        record.weight_diff_rate_pct = diff_result.diff_rate_pct

        if diff_result.needs_review:
            record.status = WeighingStatus.REVIEW_REQUIRED
            review = ReviewOrder(
                weighing_id=record.id,
                dispatch_id=dispatch_id,
                reason=diff_result.reason,
                status=ReviewStatus.PENDING,
            )
            self.db.add(review)
        else:
            record.status = WeighingStatus.COMPLETE
            dispatch.status = DispatchStatus.COMPLETED

        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_weighings(self, status: WeighingStatus | None = None) -> list[WeighingRecord]:
        stmt = select(WeighingRecord).order_by(WeighingRecord.created_at.desc())
        if status is not None:
            stmt = stmt.where(WeighingRecord.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_weighing(self, weighing_id: UUID) -> WeighingRecord | None:
        return await self.db.get(WeighingRecord, weighing_id)


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_reviews(self, status: ReviewStatus | None = None) -> list[ReviewOrder]:
        stmt = select(ReviewOrder).order_by(ReviewOrder.created_at.desc())
        if status is not None:
            stmt = stmt.where(ReviewOrder.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_review(self, review_id: UUID) -> ReviewOrder | None:
        return await self.db.get(ReviewOrder, review_id)

    async def approve_review(self, review_id: UUID, data: ReviewApprove) -> ReviewOrder:
        review = await self.db.get(ReviewOrder, review_id)
        if review is None:
            raise ValueError(f"复核单 {review_id} 不存在")
        if review.status != ReviewStatus.PENDING:
            raise ValueError(f"复核单状态为 {review.status.value}，不可审核")

        if data.approved:
            review.status = ReviewStatus.APPROVED
            weighing = await self.db.get(WeighingRecord, review.weighing_id)
            if weighing is not None:
                weighing.status = WeighingStatus.COMPLETE
                dispatch = await self.db.get(DispatchOrder, review.dispatch_id)
                if dispatch is not None:
                    dispatch.status = DispatchStatus.COMPLETED
        else:
            review.status = ReviewStatus.REJECTED

        review.reviewed_by = data.reviewed_by
        review.remark = data.remark
        review.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(review)
        return review
