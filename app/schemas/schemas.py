from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.models import (
    BoxStatus,
    DisinfectionStatus,
    DispatchStatus,
    PriorityLevel,
    QueueStatus,
    ReviewStatus,
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


class QueueRead(BaseModel):
    id: UUID
    box_id: UUID
    priority: PriorityLevel
    status: QueueStatus
    position: int
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
    created_at: datetime
    departed_at: datetime | None
    arrived_at: datetime | None

    model_config = {"from_attributes": True}


class WeighingOutbound(BaseModel):
    station_outbound_weight_kg: float = Field(..., gt=0)


class WeighingInbound(BaseModel):
    plant_inbound_weight_kg: float = Field(..., gt=0)


class WeighingRead(BaseModel):
    id: UUID
    dispatch_id: UUID
    station_outbound_weight_kg: float | None
    plant_inbound_weight_kg: float | None
    weight_diff_kg: float | None
    weight_diff_rate_pct: float | None
    outbound_weighed_at: datetime | None
    inbound_weighed_at: datetime | None
    status: WeighingStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewRead(BaseModel):
    id: UUID
    weighing_id: UUID
    dispatch_id: UUID
    reason: str
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
