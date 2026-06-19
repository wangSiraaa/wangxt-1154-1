from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BoxStatus,
    CompressionBox,
    DispatchOrder,
    DispatchStatus,
    DisinfectionStatus,
    FaultStatus,
    PriorityLevel,
    QueueStatus,
    ReviewOrder,
    ReviewStatus,
    ReviewType,
    RoutePoint,
    TransferQueue,
    Vehicle,
    VehicleFault,
    VehicleStatus,
)
from app.rules.business_rules import (
    BusinessRuleViolation,
    check_box_can_queue,
    check_queue_can_dispatch,
    check_route_deviation,
    check_vehicle_can_dispatch,
    check_vehicle_faults,
)
from app.schemas.schemas import (
    DispatchCreate,
    QueueCreate,
    RoutePointCreate,
    VehicleCreate,
    VehicleDisinfect,
    VehicleFaultCreate,
    VehicleFaultResolve,
)


class DispatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_vehicle(self, data: VehicleCreate) -> Vehicle:
        vehicle = Vehicle(
            plate_number=data.plate_number,
            driver_name=data.driver_name,
            status=VehicleStatus.IDLE,
            disinfection_status=DisinfectionStatus.NONE,
        )
        self.db.add(vehicle)
        await self.db.flush()
        await self.db.refresh(vehicle)
        return vehicle

    async def complete_disinfection(self, vehicle_id: UUID, data: VehicleDisinfect) -> Vehicle:
        vehicle = await self.db.get(Vehicle, vehicle_id)
        if vehicle is None:
            raise ValueError(f"车辆 {vehicle_id} 不存在")
        if data.disinfected:
            vehicle.disinfection_status = DisinfectionStatus.COMPLETED
            vehicle.last_disinfection_at = datetime.now(timezone.utc)
            if vehicle.status == VehicleStatus.DISINFECTING:
                vehicle.status = VehicleStatus.READY
        else:
            vehicle.disinfection_status = DisinfectionStatus.PENDING
            vehicle.status = VehicleStatus.DISINFECTING
        await self.db.flush()
        await self.db.refresh(vehicle)
        return vehicle

    async def list_vehicles(self, status: VehicleStatus | None = None) -> list[Vehicle]:
        stmt = select(Vehicle).order_by(Vehicle.created_at)
        if status is not None:
            stmt = stmt.where(Vehicle.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_vehicle(self, vehicle_id: UUID) -> Vehicle | None:
        return await self.db.get(Vehicle, vehicle_id)

    async def report_fault(self, vehicle_id: UUID, data: VehicleFaultCreate) -> VehicleFault:
        vehicle = await self.db.get(Vehicle, vehicle_id)
        if vehicle is None:
            raise ValueError(f"车辆 {vehicle_id} 不存在")
        fault = VehicleFault(
            vehicle_id=vehicle_id,
            fault_code=data.fault_code,
            description=data.description,
            status=FaultStatus.OPEN,
            reported_by=data.reported_by,
        )
        self.db.add(fault)
        await self.db.flush()
        await self.db.refresh(fault)
        return fault

    async def resolve_fault(self, fault_id: UUID, data: VehicleFaultResolve) -> VehicleFault:
        fault = await self.db.get(VehicleFault, fault_id)
        if fault is None:
            raise ValueError(f"故障记录 {fault_id} 不存在")
        if fault.status != FaultStatus.OPEN:
            raise ValueError(f"故障记录状态为 {fault.status.value}，不可处理")
        fault.status = FaultStatus.RESOLVED
        fault.resolved_by = data.resolved_by
        fault.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(fault)
        return fault

    async def list_faults(self, vehicle_id: UUID | None = None, status: FaultStatus | None = None) -> list[VehicleFault]:
        stmt = select(VehicleFault).order_by(VehicleFault.created_at.desc())
        if vehicle_id is not None:
            stmt = stmt.where(VehicleFault.vehicle_id == vehicle_id)
        if status is not None:
            stmt = stmt.where(VehicleFault.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def enqueue(self, data: QueueCreate) -> TransferQueue:
        box = await self.db.get(CompressionBox, data.box_id)
        if box is None:
            raise ValueError(f"压缩箱 {data.box_id} 不存在")

        check_box_can_queue(box, data.priority, data.overflow_approved_by)

        max_pos_result = await self.db.execute(
            select(func.coalesce(func.max(TransferQueue.position), 0)).where(
                TransferQueue.status == QueueStatus.WAITING
            )
        )
        max_pos = max_pos_result.scalar_one()

        queue_entry = TransferQueue(
            box_id=data.box_id,
            priority=data.priority,
            status=QueueStatus.WAITING,
            position=max_pos + 1,
            overflow_approved_by=data.overflow_approved_by,
            overflow_approval_remark=data.overflow_approval_remark,
            overflow_approved_at=datetime.now(timezone.utc) if data.overflow_approved_by else None,
        )
        self.db.add(queue_entry)
        if box.status != BoxStatus.FULL:
            box.status = BoxStatus.FULL
        await self.db.flush()
        await self.db.refresh(queue_entry)
        await self.db.refresh(box)
        return queue_entry

    async def list_queue(self, status: QueueStatus | None = None) -> list[TransferQueue]:
        stmt = select(TransferQueue).order_by(TransferQueue.position)
        if status is not None:
            stmt = stmt.where(TransferQueue.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def dispatch(self, data: DispatchCreate) -> DispatchOrder:
        queue_entry = await self.db.get(TransferQueue, data.queue_id)
        if queue_entry is None:
            raise ValueError(f"排队记录 {data.queue_id} 不存在")

        check_queue_can_dispatch(queue_entry)

        vehicle = await self.db.get(Vehicle, data.vehicle_id)
        if vehicle is None:
            raise ValueError(f"车辆 {data.vehicle_id} 不存在")

        check_vehicle_can_dispatch(vehicle)

        faults_result = await self.db.execute(
            select(VehicleFault).where(VehicleFault.vehicle_id == data.vehicle_id)
        )
        faults = list(faults_result.scalars().all())
        check_vehicle_faults(vehicle, faults)

        order = DispatchOrder(
            queue_id=data.queue_id,
            box_id=queue_entry.box_id,
            vehicle_id=data.vehicle_id,
            dispatcher_id=data.dispatcher_id,
            status=DispatchStatus.CREATED,
        )
        self.db.add(order)

        queue_entry.status = QueueStatus.DISPATCHED
        queue_entry.dispatched_at = datetime.now(timezone.utc)
        vehicle.status = VehicleStatus.ON_DUTY

        await self.db.flush()
        await self.db.refresh(order)
        await self.db.refresh(queue_entry)
        await self.db.refresh(vehicle)
        return order

    async def depart(self, dispatch_id: UUID, departure_weight_kg: float) -> DispatchOrder:
        order = await self.db.get(DispatchOrder, dispatch_id)
        if order is None:
            raise ValueError(f"派车单 {dispatch_id} 不存在")
        if order.status != DispatchStatus.CREATED:
            raise ValueError(f"派车单状态为 {order.status.value}，不能出站")

        vehicle = await self.db.get(Vehicle, order.vehicle_id)
        if vehicle is not None and vehicle.disinfection_status != DisinfectionStatus.COMPLETED:
            raise BusinessRuleViolation(
                "VEHICLE_DISINFECTION_INCOMPLETE",
                f"车辆消杀未完成不能出车",
            )

        order.status = DispatchStatus.DEPARTED
        order.departure_weight_kg = departure_weight_kg
        order.departed_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def arrive(self, dispatch_id: UUID) -> DispatchOrder:
        order = await self.db.get(DispatchOrder, dispatch_id)
        if order is None:
            raise ValueError(f"派车单 {dispatch_id} 不存在")
        if order.status != DispatchStatus.DEPARTED and order.status != DispatchStatus.IN_TRANSIT:
            raise ValueError(f"派车单状态为 {order.status.value}，不能到达")

        order.status = DispatchStatus.ARRIVED
        order.arrived_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def list_dispatches(self, status: DispatchStatus | None = None) -> list[DispatchOrder]:
        stmt = select(DispatchOrder).order_by(DispatchOrder.created_at.desc())
        if status is not None:
            stmt = stmt.where(DispatchOrder.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_dispatch(self, dispatch_id: UUID) -> DispatchOrder | None:
        return await self.db.get(DispatchOrder, dispatch_id)

    async def report_route_point(
        self,
        dispatch_id: UUID,
        data: RoutePointCreate,
        planned_lat: float | None = None,
        planned_lon: float | None = None,
    ) -> RoutePoint:
        dispatch = await self.db.get(DispatchOrder, dispatch_id)
        if dispatch is None:
            raise ValueError(f"派车单 {dispatch_id} 不存在")
        if dispatch.status not in (DispatchStatus.DEPARTED, DispatchStatus.IN_TRANSIT):
            raise ValueError(f"派车单状态为 {dispatch.status.value}，不在运输途中")

        deviation_result = check_route_deviation(data.latitude, data.longitude, planned_lat, planned_lon)

        route_point = RoutePoint(
            dispatch_id=dispatch_id,
            latitude=data.latitude,
            longitude=data.longitude,
            is_deviation=deviation_result.is_deviation,
            deviation_reason=deviation_result.reason if deviation_result.is_deviation else None,
        )
        self.db.add(route_point)

        if deviation_result.is_deviation:
            dispatch.route_deviation_detected = True
            dispatch.route_deviation_reason = deviation_result.reason
            dispatch.status = DispatchStatus.IN_TRANSIT
            review = ReviewOrder(
                dispatch_id=dispatch_id,
                reason=deviation_result.reason,
                review_type=ReviewType.ROUTE_DEVIATION,
                status=ReviewStatus.PENDING,
            )
            self.db.add(review)

        await self.db.flush()
        await self.db.refresh(route_point)
        return route_point
