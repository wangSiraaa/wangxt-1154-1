import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import BoxStatus
from app.schemas.schemas import BoxCreate, BoxRegisterFull, StationCreate
from app.services.box_service import BoxService


@pytest.mark.asyncio
async def test_create_station(db_session: AsyncSession):
    svc = BoxService(db_session)
    station = await svc.create_station(StationCreate(name="城南压缩站", address="城南100号"))
    assert station.name == "城南压缩站"
    assert station.address == "城南100号"


@pytest.mark.asyncio
async def test_create_box(db_session: AsyncSession, sample_station):
    svc = BoxService(db_session)
    box = await svc.create_box(
        BoxCreate(station_id=sample_station.id, box_code="BOX-NEW", max_capacity_kg=10000.0)
    )
    assert box.box_code == "BOX-NEW"
    assert box.status == BoxStatus.EMPTY
    assert box.max_capacity_kg == 10000.0


@pytest.mark.asyncio
async def test_register_full(db_session: AsyncSession, sample_box):
    svc = BoxService(db_session)
    updated = await svc.register_full(
        sample_box.id, BoxRegisterFull(current_weight_kg=7500.0, registered_by="duty_wang")
    )
    assert updated.status == BoxStatus.FULL
    assert updated.current_weight_kg == 7500.0
    assert updated.registered_by == "duty_wang"


@pytest.mark.asyncio
async def test_register_full_already_full(db_session: AsyncSession, sample_full_box):
    svc = BoxService(db_session)
    with pytest.raises(ValueError, match="已是满载状态"):
        await svc.register_full(
            sample_full_box.id, BoxRegisterFull(current_weight_kg=8000.0, registered_by="duty_wang")
        )


@pytest.mark.asyncio
async def test_register_full_exceeds_capacity(db_session: AsyncSession, sample_box):
    svc = BoxService(db_session)
    with pytest.raises(ValueError, match="超过最大容量"):
        await svc.register_full(
            sample_box.id, BoxRegisterFull(current_weight_kg=99999.0, registered_by="duty_wang")
        )
