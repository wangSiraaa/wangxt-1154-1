import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import BoxStatus, DisinfectionStatus, QueueStatus, VehicleStatus
from app.rules.business_rules import BusinessRuleViolation
from app.schemas.schemas import DispatchCreate, QueueCreate, VehicleCreate, VehicleDisinfect
from app.services.dispatch_service import DispatchService


@pytest.mark.asyncio
async def test_create_vehicle(db_session: AsyncSession):
    svc = DispatchService(db_session)
    vehicle = await svc.create_vehicle(VehicleCreate(plate_number="京B88888", driver_name="赵师傅"))
    assert vehicle.plate_number == "京B88888"
    assert vehicle.status == VehicleStatus.IDLE
    assert vehicle.disinfection_status == DisinfectionStatus.NONE


@pytest.mark.asyncio
async def test_complete_disinfection(db_session: AsyncSession, sample_vehicle):
    svc = DispatchService(db_session)
    updated = await svc.complete_disinfection(sample_vehicle.id, VehicleDisinfect(disinfected=True))
    assert updated.disinfection_status == DisinfectionStatus.COMPLETED
    assert updated.last_disinfection_at is not None


@pytest.mark.asyncio
async def test_enqueue_full_box(db_session: AsyncSession, sample_full_box):
    svc = DispatchService(db_session)
    queue = await svc.enqueue(QueueCreate(box_id=sample_full_box.id, priority="NORMAL"))
    assert queue.status == QueueStatus.WAITING
    assert queue.position == 1


@pytest.mark.asyncio
async def test_enqueue_not_full_box_fails(db_session: AsyncSession, sample_box):
    svc = DispatchService(db_session)
    with pytest.raises(BusinessRuleViolation, match="未满载"):
        await svc.enqueue(QueueCreate(box_id=sample_box.id, priority="NORMAL"))


@pytest.mark.asyncio
async def test_enqueue_not_full_high_priority_fails(db_session: AsyncSession, sample_box):
    svc = DispatchService(db_session)
    sample_box.status = BoxStatus.LOADING
    with pytest.raises(BusinessRuleViolation, match="未满载"):
        await svc.enqueue(QueueCreate(box_id=sample_box.id, priority="HIGH"))


@pytest.mark.asyncio
async def test_dispatch_success(db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    svc = DispatchService(db_session)
    order = await svc.dispatch(
        DispatchCreate(
            queue_id=sample_queue.id,
            vehicle_id=sample_vehicle.id,
            dispatcher_id="dispatcher_li",
        )
    )
    assert order.status.value == "CREATED"
    assert order.vehicle_id == sample_vehicle.id

    await db_session.refresh(sample_queue)
    assert sample_queue.status == QueueStatus.DISPATCHED

    await db_session.refresh(sample_vehicle)
    assert sample_vehicle.status == VehicleStatus.ON_DUTY


@pytest.mark.asyncio
async def test_dispatch_vehicle_not_disinfected_fails(
    db_session: AsyncSession, sample_full_box, sample_queue
):
    svc = DispatchService(db_session)
    vehicle = await svc.create_vehicle(VehicleCreate(plate_number="京C00001", driver_name="未消杀司机"))
    with pytest.raises(BusinessRuleViolation, match="消杀"):
        await svc.dispatch(
            DispatchCreate(
                queue_id=sample_queue.id,
                vehicle_id=vehicle.id,
                dispatcher_id="dispatcher_li",
            )
        )


@pytest.mark.asyncio
async def test_depart(db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    svc = DispatchService(db_session)
    order = await svc.dispatch(
        DispatchCreate(
            queue_id=sample_queue.id,
            vehicle_id=sample_vehicle.id,
            dispatcher_id="dispatcher_li",
        )
    )
    departed = await svc.depart(order.id, departure_weight_kg=7480.5)
    assert departed.status.value == "DEPARTED"
    assert departed.departure_weight_kg == 7480.5
    assert departed.departed_at is not None
