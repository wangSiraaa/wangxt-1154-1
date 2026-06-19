import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import BoxStatus, DisinfectionStatus, FaultStatus, PriorityLevel, QueueStatus, VehicleStatus
from app.rules.business_rules import BusinessRuleViolation
from app.schemas.schemas import (
    DispatchCreate,
    QueueCreate,
    RoutePointCreate,
    VehicleCreate,
    VehicleDisinfect,
    VehicleFaultCreate,
    VehicleFaultResolve,
)
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


@pytest.mark.asyncio
async def test_report_and_resolve_fault(db_session: AsyncSession, sample_vehicle):
    svc = DispatchService(db_session)
    fault = await svc.report_fault(
        sample_vehicle.id,
        VehicleFaultCreate(fault_code="BRAKE_WEAR", description="刹车片磨损", reported_by="mechanic_liu"),
    )
    assert fault.fault_code == "BRAKE_WEAR"
    assert fault.status == FaultStatus.OPEN

    resolved = await svc.resolve_fault(fault.id, VehicleFaultResolve(resolved_by="mechanic_wang"))
    assert resolved.status == FaultStatus.RESOLVED
    assert resolved.resolved_by == "mechanic_wang"


@pytest.mark.asyncio
async def test_dispatch_vehicle_with_open_fault_fails(
    db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue, sample_fault
):
    svc = DispatchService(db_session)
    with pytest.raises(BusinessRuleViolation, match="未处理故障"):
        await svc.dispatch(
            DispatchCreate(
                queue_id=sample_queue.id,
                vehicle_id=sample_vehicle.id,
                dispatcher_id="dispatcher_li",
            )
        )


@pytest.mark.asyncio
async def test_enqueue_not_full_with_overflow_approval(db_session: AsyncSession, sample_box):
    svc = DispatchService(db_session)
    sample_box.status = BoxStatus.LOADING
    queue = await svc.enqueue(
        QueueCreate(
            box_id=sample_box.id,
            priority=PriorityLevel.URGENT,
            overflow_approved_by="supervisor_chen",
            overflow_approval_remark="突发溢满，主管审批通过",
        )
    )
    assert queue.overflow_approved_by == "supervisor_chen"
    assert queue.overflow_approved_at is not None


@pytest.mark.asyncio
async def test_route_point_and_deviation_review(db_session: AsyncSession, sample_full_box, sample_vehicle, sample_queue):
    from app.models.models import ReviewType

    svc = DispatchService(db_session)
    order = await svc.dispatch(
        DispatchCreate(
            queue_id=sample_queue.id,
            vehicle_id=sample_vehicle.id,
            dispatcher_id="dispatcher_li",
        )
    )
    await svc.depart(order.id, departure_weight_kg=7480.0)

    point = await svc.report_route_point(
        order.id,
        RoutePointCreate(latitude=40.0, longitude=117.0),
        planned_lat=39.9,
        planned_lon=116.4,
    )
    assert point.is_deviation is True
    assert point.deviation_reason is not None

    await db_session.refresh(order)
    assert order.route_deviation_detected is True
