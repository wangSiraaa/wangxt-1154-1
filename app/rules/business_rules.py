from dataclasses import dataclass

from app.config import settings
from app.models.models import (
    BoxStatus,
    CompressionBox,
    DisinfectionStatus,
    PriorityLevel,
    TransferQueue,
    Vehicle,
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


def check_box_can_queue(box: CompressionBox, priority: PriorityLevel) -> None:
    if box.status != BoxStatus.FULL:
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
