from app.rules.business_rules import (
    BusinessRuleViolation,
    WeightDiffResult,
    check_box_can_queue,
    check_vehicle_can_dispatch,
    compute_weight_diff,
)
from app.models.models import (
    BoxStatus,
    CompressionBox,
    DisinfectionStatus,
    PriorityLevel,
    Vehicle,
    VehicleStatus,
)
import pytest


def _make_box(status: BoxStatus = BoxStatus.FULL) -> CompressionBox:
    return CompressionBox(
        box_code="BOX-T",
        status=status,
        current_weight_kg=7500.0,
        max_capacity_kg=8000.0,
        station_id=None,
    )


def _make_vehicle(
    status: VehicleStatus = VehicleStatus.READY,
    disinfection: DisinfectionStatus = DisinfectionStatus.COMPLETED,
) -> Vehicle:
    return Vehicle(
        plate_number="京T99999",
        driver_name="测试司机",
        status=status,
        disinfection_status=disinfection,
    )


class TestCheckBoxCanQueue:
    def test_full_box_passes(self):
        box = _make_box(BoxStatus.FULL)
        check_box_can_queue(box, PriorityLevel.NORMAL)

    def test_not_full_box_rejects(self):
        box = _make_box(BoxStatus.EMPTY)
        with pytest.raises(BusinessRuleViolation, match="BOX_NOT_FULL"):
            check_box_can_queue(box, PriorityLevel.NORMAL)

    def test_loading_box_rejects_high_priority(self):
        box = _make_box(BoxStatus.LOADING)
        with pytest.raises(BusinessRuleViolation, match="BOX_NOT_FULL_PRIORITY"):
            check_box_can_queue(box, PriorityLevel.HIGH)


class TestCheckVehicleCanDispatch:
    def test_ready_disinfected_vehicle_passes(self):
        vehicle = _make_vehicle(VehicleStatus.READY, DisinfectionStatus.COMPLETED)
        check_vehicle_can_dispatch(vehicle)

    def test_vehicle_not_disinfected_rejects(self):
        vehicle = _make_vehicle(VehicleStatus.READY, DisinfectionStatus.PENDING)
        with pytest.raises(BusinessRuleViolation, match="VEHICLE_DISINFECTION_INCOMPLETE"):
            check_vehicle_can_dispatch(vehicle)

    def test_vehicle_on_duty_rejects(self):
        vehicle = _make_vehicle(VehicleStatus.ON_DUTY, DisinfectionStatus.COMPLETED)
        with pytest.raises(BusinessRuleViolation, match="VEHICLE_NOT_AVAILABLE"):
            check_vehicle_can_dispatch(vehicle)


class TestComputeWeightDiff:
    def test_small_diff_no_review(self):
        result = compute_weight_diff(7480.0, 7450.0)
        assert not result.needs_review
        assert result.diff_kg == 30.0
        assert result.diff_rate_pct < 5.0

    def test_large_diff_pct_triggers_review(self):
        result = compute_weight_diff(7480.0, 6800.0)
        assert result.needs_review
        assert result.diff_rate_pct > 5.0

    def test_large_diff_abs_triggers_review(self):
        result = compute_weight_diff(10000.0, 9700.0)
        assert result.diff_kg == 300.0
        assert result.needs_review
