from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.models import (
    BoxStatus,
    DisinfectionStatus,
    DispatchStatus,
    FaultStatus,
    PriorityLevel,
    QueueStatus,
    ReviewStatus,
    ReviewType,
    VehicleStatus,
    WeighingStatus,
)


class StationCreate(BaseModel):
    name: str = Field(..., max_length=128)
    address: str | None = Field(None, max_length=256)


class StationRead(BaseModel):
    id: UUID
    name: str
    address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BoxRegisterFull(BaseModel):
    current_weight_kg: float = Field(..., gt=0)
    registered_by: str = Field(..., max_length=64)


class BoxCreate(BaseModel):
    station_id: UUID
    box_code: str = Field(..., max_length=64)
    max_capacity_kg: float = Field(..., gt=0)


class BoxRead(BaseModel):
    id: UUID
    station_id: UUID
    box_code: str
    status: BoxStatus
    current_weight_kg: float
    max_capacity_kg: float
    registered_full_at: datetime | None
    registered_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QueueCreate(BaseModel):
    box_id: UUID
    priority: PriorityLevel = PriorityLevel.NORMAL
    overflow_approved_by: str | None = Field(None, max_length=64)
    overflow_approval_remark: str | None = None


class QueueRead(BaseModel):
    id: UUID
    box_id: UUID
    priority: PriorityLevel
    status: QueueStatus
    position: int
    overflow_approved_by: str | None
    overflow_approval_remark: str | None
    overflow_approved_at: datetime | None
    created_at: datetime
    dispatched_at: datetime | None

    model_config = {"from_attributes": True}


class VehicleCreate(BaseModel):
    plate_number: str = Field(..., max_length=32)
    driver_name: str = Field(..., max_length=64)


class VehicleDisinfect(BaseModel):
    disinfected: bool


class VehicleRead(BaseModel):
    id: UUID
    plate_number: str
    driver_name: str
    status: VehicleStatus
    disinfection_status: DisinfectionStatus
    last_disinfection_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VehicleFaultCreate(BaseModel):
    fault_code: str = Field(..., max_length=64)
    description: str
    reported_by: str = Field(..., max_length=64)


class VehicleFaultResolve(BaseModel):
    resolved_by: str = Field(..., max_length=64)


class VehicleFaultRead(BaseModel):
    id: UUID
    vehicle_id: UUID
    fault_code: str
    description: str
    status: FaultStatus
    reported_by: str
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DispatchCreate(BaseModel):
    queue_id: UUID
    vehicle_id: UUID
    dispatcher_id: str = Field(..., max_length=64)


class DispatchDepart(BaseModel):
    departure_weight_kg: float = Field(..., gt=0)


class DispatchRead(BaseModel):
    id: UUID
    queue_id: UUID
    box_id: UUID
    vehicle_id: UUID
    dispatcher_id: str
    status: DispatchStatus
    departure_weight_kg: float | None
    route_deviation_detected: bool
    route_deviation_reason: str | None
    created_at: datetime
    departed_at: datetime | None
    arrived_at: datetime | None

    model_config = {"from_attributes": True}


class WeighingOutbound(BaseModel):
    station_outbound_weight_kg: float = Field(..., gt=0)
    outbound_operator: str = Field(..., max_length=64)


class WeighingInbound(BaseModel):
    plant_inbound_weight_kg: float = Field(..., gt=0)
    inbound_operator: str = Field(..., max_length=64)


class WeighingRead(BaseModel):
    id: UUID
    dispatch_id: UUID
    station_outbound_weight_kg: float | None
    plant_inbound_weight_kg: float | None
    weight_diff_kg: float | None
    weight_diff_rate_pct: float | None
    outbound_weighed_at: datetime | None
    inbound_weighed_at: datetime | None
    outbound_operator: str | None
    inbound_operator: str | None
    status: WeighingStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewRead(BaseModel):
    id: UUID
    weighing_id: UUID | None
    dispatch_id: UUID
    reason: str
    review_type: ReviewType
    status: ReviewStatus
    reviewed_by: str | None
    remark: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ReviewApprove(BaseModel):
    approved: bool
    reviewed_by: str = Field(..., max_length=64)
    remark: str | None = None


class RoutePointCreate(BaseModel):
    latitude: float
    longitude: float


class RoutePointRead(BaseModel):
    id: UUID
    dispatch_id: UUID
    latitude: float
    longitude: float
    is_deviation: bool
    deviation_reason: str | None
    recorded_at: datetime

    model_config = {"from_attributes": True}
