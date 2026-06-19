from dataclasses import dataclass
from typing import List

from app.config import settings
from app.models.models import (
    BoxStatus,
    CompressionBox,
    DisinfectionStatus,
    FaultStatus,
    PriorityLevel,
    TransferQueue,
    Vehicle,
    VehicleFault,
    VehicleStatus,
)


class BusinessRuleViolation(Exception):
    def __init__(self, rule: str, detail: str):
        self.rule = rule
        self.detail = detail
        super().__init__(f"[{rule}] {detail}")


@dataclass(frozen=True)
class WeightDiffResult:
    diff_kg: float
    diff_rate_pct: float
    needs_review: bool
    reason: str


def check_box_can_queue(
    box: CompressionBox,
    priority: PriorityLevel,
    overflow_approved_by: str | None = None,
) -> None:
    if box.status == BoxStatus.FULL:
        return
    if overflow_approved_by is not None:
        return
    if priority in (PriorityLevel.HIGH, PriorityLevel.URGENT):
        raise BusinessRuleViolation(
            "BOX_NOT_FULL_PRIORITY",
            f"压缩箱 {box.box_code} 未满载，不能使用 {priority.value} 优先级排队",
        )
    raise BusinessRuleViolation(
        "BOX_NOT_FULL",
        f"压缩箱 {box.box_code} 状态为 {box.status.value}，未满载不能入队",
    )


def check_vehicle_can_dispatch(vehicle: Vehicle) -> None:
    if vehicle.status not in (VehicleStatus.READY, VehicleStatus.IDLE):
        raise BusinessRuleViolation(
            "VEHICLE_NOT_AVAILABLE",
            f"车辆 {vehicle.plate_number} 当前状态为 {vehicle.status.value}，不可调度",
        )
    if vehicle.disinfection_status != DisinfectionStatus.COMPLETED:
        raise BusinessRuleViolation(
            "VEHICLE_DISINFECTION_INCOMPLETE",
            f"车辆 {vehicle.plate_number} 消杀状态为 {vehicle.disinfection_status.value}，消杀未完成不能出车",
        )


def check_vehicle_faults(vehicle: Vehicle, faults: List[VehicleFault]) -> None:
    open_faults = [f for f in faults if f.status == FaultStatus.OPEN]
    if open_faults:
        codes = ", ".join(f.fault_code for f in open_faults)
        raise BusinessRuleViolation(
            "VEHICLE_HAS_OPEN_FAULTS",
            f"车辆 {vehicle.plate_number} 存在未处理故障 [{codes}]，不能调度",
        )


def check_queue_can_dispatch(queue: TransferQueue) -> None:
    from app.models.models import QueueStatus

    if queue.status != QueueStatus.WAITING:
        raise BusinessRuleViolation(
            "QUEUE_NOT_WAITING",
            f"排队记录 {queue.id} 状态为 {queue.status.value}，不在等待中",
        )


def compute_weight_diff(
    outbound_weight_kg: float,
    inbound_weight_kg: float,
) -> WeightDiffResult:
    diff_kg = abs(inbound_weight_kg - outbound_weight_kg)
    diff_rate_pct = (diff_kg / outbound_weight_kg) * 100.0 if outbound_weight_kg > 0 else 0.0

    reasons: list[str] = []
    needs_review = False

    if diff_rate_pct > settings.weight_diff_threshold_pct:
        needs_review = True
        reasons.append(f"差异率 {diff_rate_pct:.2f}% 超过阈值 {settings.weight_diff_threshold_pct}%")

    if diff_kg > settings.weight_diff_abs_threshold_kg:
        needs_review = True
        reasons.append(f"差异量 {diff_kg:.1f}kg 超过阈值 {settings.weight_diff_abs_threshold_kg}kg")

    reason = "; ".join(reasons) if reasons else "重量差异在允许范围内"
    return WeightDiffResult(
        diff_kg=diff_kg,
        diff_rate_pct=diff_rate_pct,
        needs_review=needs_review,
        reason=reason,
    )


@dataclass(frozen=True)
class RouteDeviationResult:
    is_deviation: bool
    reason: str


def check_route_deviation(
    latitude: float,
    longitude: float,
    planned_lat: float | None = None,
    planned_lon: float | None = None,
) -> RouteDeviationResult:
    if planned_lat is None or planned_lon is None:
        return RouteDeviationResult(is_deviation=False, reason="")

    from math import acos, cos, radians, sin

    lat1, lon1 = radians(planned_lat), radians(planned_lon)
    lat2, lon2 = radians(latitude), radians(longitude)
    delta = acos(
        sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(lon2 - lon1)
    )
    distance_km = delta * 6371.0

    threshold_km = settings.route_deviation_threshold_km
    if distance_km > threshold_km:
        return RouteDeviationResult(
            is_deviation=True,
            reason=f"路线偏离 {distance_km:.2f}km，超过阈值 {threshold_km}km",
        )
    return RouteDeviationResult(is_deviation=False, reason="")
