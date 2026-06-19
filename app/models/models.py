import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BoxStatus(str, enum.Enum):
    EMPTY = "EMPTY"
    LOADING = "LOADING"
    FULL = "FULL"
    IN_TRANSIT = "IN_TRANSIT"


class QueueStatus(str, enum.Enum):
    WAITING = "WAITING"
    DISPATCHED = "DISPATCHED"
    CANCELLED = "CANCELLED"


class PriorityLevel(str, enum.Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class VehicleStatus(str, enum.Enum):
    IDLE = "IDLE"
    DISINFECTING = "DISINFECTING"
    READY = "READY"
    ON_DUTY = "ON_DUTY"


class DisinfectionStatus(str, enum.Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class DispatchStatus(str, enum.Enum):
    CREATED = "CREATED"
    DEPARTED = "DEPARTED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    COMPLETED = "COMPLETED"


class WeighingStatus(str, enum.Enum):
    OUTBOUND_ONLY = "OUTBOUND_ONLY"
    COMPLETE = "COMPLETE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class FaultStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ReviewType(str, enum.Enum):
    WEIGHT_DIFF = "WEIGHT_DIFF"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"


class ReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    boxes: Mapped[List["CompressionBox"]] = relationship(back_populates="station")


class CompressionBox(Base):
    __tablename__ = "compression_boxes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    station_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("stations.id"), nullable=False)
    box_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[BoxStatus] = mapped_column(Enum(BoxStatus), default=BoxStatus.EMPTY, nullable=False)
    current_weight_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_capacity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    registered_full_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    station: Mapped["Station"] = relationship(back_populates="boxes")
    queue_entries: Mapped[List["TransferQueue"]] = relationship(back_populates="box")


class TransferQueue(Base):
    __tablename__ = "transfer_queues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    box_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compression_boxes.id"), nullable=False)
    priority: Mapped[PriorityLevel] = mapped_column(Enum(PriorityLevel), default=PriorityLevel.NORMAL, nullable=False)
    status: Mapped[QueueStatus] = mapped_column(Enum(QueueStatus), default=QueueStatus.WAITING, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    overflow_approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    overflow_approval_remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overflow_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    box: Mapped["CompressionBox"] = relationship(back_populates="queue_entries")
    dispatch_order: Mapped[Optional["DispatchOrder"]] = relationship(back_populates="queue", uselist=False)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plate_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    driver_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(Enum(VehicleStatus), default=VehicleStatus.IDLE, nullable=False)
    disinfection_status: Mapped[DisinfectionStatus] = mapped_column(
        Enum(DisinfectionStatus), default=DisinfectionStatus.NONE, nullable=False
    )
    last_disinfection_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    dispatch_orders: Mapped[List["DispatchOrder"]] = relationship(back_populates="vehicle")
    faults: Mapped[List["VehicleFault"]] = relationship(back_populates="vehicle", order_by="VehicleFault.created_at.desc()")


class VehicleFault(Base):
    __tablename__ = "vehicle_faults"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vehicles.id"), nullable=False)
    fault_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FaultStatus] = mapped_column(Enum(FaultStatus), default=FaultStatus.OPEN, nullable=False)
    reported_by: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vehicle: Mapped["Vehicle"] = relationship(back_populates="faults")


class DispatchOrder(Base):
    __tablename__ = "dispatch_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    queue_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("transfer_queues.id"), nullable=False)
    box_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compression_boxes.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vehicles.id"), nullable=False)
    dispatcher_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DispatchStatus] = mapped_column(Enum(DispatchStatus), default=DispatchStatus.CREATED, nullable=False)
    departure_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    route_deviation_detected: Mapped[bool] = mapped_column(default=False, nullable=False)
    route_deviation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    departed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    queue: Mapped["TransferQueue"] = relationship(back_populates="dispatch_order")
    box: Mapped["CompressionBox"] = relationship()
    vehicle: Mapped["Vehicle"] = relationship(back_populates="dispatch_orders")
    weighing: Mapped[Optional["WeighingRecord"]] = relationship(back_populates="dispatch", uselist=False)


class WeighingRecord(Base):
    __tablename__ = "weighing_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dispatch_orders.id"), unique=True, nullable=False
    )
    station_outbound_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plant_inbound_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_diff_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_diff_rate_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    outbound_weighed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    inbound_weighed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    outbound_operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    inbound_operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[WeighingStatus] = mapped_column(
        Enum(WeighingStatus), default=WeighingStatus.OUTBOUND_ONLY, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    dispatch: Mapped["DispatchOrder"] = relationship(back_populates="weighing")
    review: Mapped[Optional["ReviewOrder"]] = relationship(back_populates="weighing", uselist=False)


class ReviewOrder(Base):
    __tablename__ = "review_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    weighing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("weighing_records.id"), unique=True, nullable=True
    )
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dispatch_orders.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    review_type: Mapped[ReviewType] = mapped_column(Enum(ReviewType), default=ReviewType.WEIGHT_DIFF, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    weighing: Mapped[Optional["WeighingRecord"]] = relationship(back_populates="review")


class RoutePoint(Base):
    __tablename__ = "route_points"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("dispatch_orders.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    is_deviation: Mapped[bool] = mapped_column(default=False, nullable=False)
    deviation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dispatch: Mapped["DispatchOrder"] = relationship()
