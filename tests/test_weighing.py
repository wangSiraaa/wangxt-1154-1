from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DispatchStatus, ReviewStatus, WeighingStatus
from app.schemas.schemas import DispatchCreate, ReviewApprove, WeighingInbound, WeighingOutbound
from app.services.dispatch_service import DispatchService
from app.services.weighing_service import ReviewService, WeighingService


async def _create_departed_dispatch(db: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    svc = DispatchService(db)
    order = await svc.dispatch(
        DispatchCreate(
            queue_id=sample_queue.id,
            vehicle_id=sample_vehicle.id,
            dispatcher_id="dispatcher_li",
        )
    )
    await svc.depart(order.id, departure_weight_kg=7480.0)
    return order.id


async def _arrive(db: AsyncSession, dispatch_id):
    svc = DispatchService(db)
    await svc.arrive(dispatch_id)


@pytest.mark.asyncio
async def test_outbound_weighing(db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    dispatch_id = await _create_departed_dispatch(db_session, sample_full_box, sample_vehicle, sample_queue)
    svc = WeighingService(db_session)
    record = await svc.record_outbound(dispatch_id, WeighingOutbound(station_outbound_weight_kg=7480.0))
    assert record.station_outbound_weight_kg == 7480.0
    assert record.status == WeighingStatus.OUTBOUND_ONLY


@pytest.mark.asyncio
async def test_inbound_weighing_normal(db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    dispatch_id = await _create_departed_dispatch(db_session, sample_full_box, sample_vehicle, sample_queue)
    ws = WeighingService(db_session)
    await ws.record_outbound(dispatch_id, WeighingOutbound(station_outbound_weight_kg=7480.0))
    await _arrive(db_session, dispatch_id)
    record = await ws.record_inbound(dispatch_id, WeighingInbound(plant_inbound_weight_kg=7450.0))
    assert record.plant_inbound_weight_kg == 7450.0
    assert record.status == WeighingStatus.COMPLETE
    assert record.weight_diff_kg is not None
    assert record.weight_diff_kg < 200.0


@pytest.mark.asyncio
async def test_inbound_weighing_triggers_review(
    db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue
):
    dispatch_id = await _create_departed_dispatch(db_session, sample_full_box, sample_vehicle, sample_queue)
    ws = WeighingService(db_session)
    await ws.record_outbound(dispatch_id, WeighingOutbound(station_outbound_weight_kg=7480.0))
    await _arrive(db_session, dispatch_id)
    record = await ws.record_inbound(dispatch_id, WeighingInbound(plant_inbound_weight_kg=6800.0))
    assert record.status == WeighingStatus.REVIEW_REQUIRED
    assert record.weight_diff_kg > 200.0

    rs = ReviewService(db_session)
    reviews = await rs.list_reviews(status=ReviewStatus.PENDING)
    assert len(reviews) == 1
    assert reviews[0].dispatch_id.hex == dispatch_id.hex


@pytest.mark.asyncio
async def test_approve_review(db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    dispatch_id = await _create_departed_dispatch(db_session, sample_full_box, sample_vehicle, sample_queue)
    ws = WeighingService(db_session)
    await ws.record_outbound(dispatch_id, WeighingOutbound(station_outbound_weight_kg=7480.0))
    await _arrive(db_session, dispatch_id)
    await ws.record_inbound(dispatch_id, WeighingInbound(plant_inbound_weight_kg=6800.0))

    rs = ReviewService(db_session)
    reviews = await rs.list_reviews(status=ReviewStatus.PENDING)
    review = await rs.approve_review(
        reviews[0].id,
        ReviewApprove(approved=True, reviewed_by="supervisor_chen", remark="核查无误"),
    )
    assert review.status == ReviewStatus.APPROVED
    assert review.reviewed_by == "supervisor_chen"

    weighing = await ws.get_weighing(reviews[0].weighing_id)
    assert weighing.status == WeighingStatus.COMPLETE


@pytest.mark.asyncio
async def test_reject_review(db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    dispatch_id = await _create_departed_dispatch(db_session, sample_full_box, sample_vehicle, sample_queue)
    ws = WeighingService(db_session)
    await ws.record_outbound(dispatch_id, WeighingOutbound(station_outbound_weight_kg=7480.0))
    await _arrive(db_session, dispatch_id)
    await ws.record_inbound(dispatch_id, WeighingInbound(plant_inbound_weight_kg=6800.0))

    rs = ReviewService(db_session)
    reviews = await rs.list_reviews(status=ReviewStatus.PENDING)
    review = await rs.approve_review(
        reviews[0].id,
        ReviewApprove(approved=False, reviewed_by="supervisor_chen", remark="数据异常需重新称重"),
    )
    assert review.status == ReviewStatus.REJECTED
