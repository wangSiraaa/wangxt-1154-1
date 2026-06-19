from app.rules.business_rules import (
    BusinessRuleViolation,
    RouteDeviationResult,
    WeightDiffResult,
    check_box_can_queue,
    check_route_deviation,
    check_vehicle_can_dispatch,
    check_vehicle_faults,
    compute_weight_diff,
)
from app.models.models import (
    BoxStatus,
    CompressionBox,
    DisinfectionStatus,
    FaultStatus,
    PriorityLevel,
    Vehicle,
    VehicleFault,
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

    def test_not_full_box_with_overflow_approval_passes(self):
        box = _make_box(BoxStatus.LOADING)
        check_box_can_queue(box, PriorityLevel.HIGH, overflow_approved_by="supervisor_chen")

    def test_not_full_box_without_approval_rejects(self):
        box = _make_box(BoxStatus.EMPTY)
        with pytest.raises(BusinessRuleViolation, match="BOX_NOT_FULL"):
            check_box_can_queue(box, PriorityLevel.NORMAL)


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


class TestCheckVehicleFaults:
    def test_vehicle_no_faults_passes(self):
        vehicle = _make_vehicle()
        check_vehicle_faults(vehicle, [])

    def test_vehicle_with_open_fault_rejects(self):
        vehicle = _make_vehicle()
        fault = VehicleFault(
            vehicle_id=vehicle.id,
            fault_code="BRAKE_WEAR",
            description="刹车片磨损",
            status=FaultStatus.OPEN,
            reported_by="mechanic_liu",
        )
        with pytest.raises(BusinessRuleViolation, match="VEHICLE_HAS_OPEN_FAULTS"):
            check_vehicle_faults(vehicle, [fault])

    def test_vehicle_with_resolved_fault_passes(self):
        vehicle = _make_vehicle()
        fault = VehicleFault(
            vehicle_id=vehicle.id,
            fault_code="BRAKE_WEAR",
            description="刹车片磨损",
            status=FaultStatus.RESOLVED,
            reported_by="mechanic_liu",
            resolved_by="mechanic_wang",
        )
        check_vehicle_faults(vehicle, [fault])


class TestCheckRouteDeviation:
    def test_no_planned_route_no_deviation(self):
        result = check_route_deviation(39.9, 116.4)
        assert not result.is_deviation

    def test_within_threshold_no_deviation(self):
        result = check_route_deviation(39.901, 116.401, 39.9, 116.4)
        assert not result.is_deviation

    def test_beyond_threshold_is_deviation(self):
        result = check_route_deviation(40.0, 117.0, 39.9, 116.4)
        assert result.is_deviation
        assert "路线偏离" in result.reason
