from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.models import BoxStatus, CompressionBox, PriorityLevel, QueueStatus, Station

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test_api.db"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_station_and_box(db_session: AsyncSession):
    station = Station(name="城南压缩站", address="城南100号")
    db_session.add(station)
    await db_session.flush()
    await db_session.refresh(station)
    box = CompressionBox(
        station_id=station.id,
        box_code="BOX-API-001",
        max_capacity_kg=8000.0,
        status=BoxStatus.EMPTY,
    )
    db_session.add(box)
    await db_session.flush()
    await db_session.refresh(box)
    return station, box


@pytest.mark.asyncio
async def test_register_full_api_returns_complete_box_read(
    client: AsyncClient, seed_station_and_box
):
    station, box = seed_station_and_box
    response = await client.post(
        f"/api/stations/boxes/{box.id}/register-full",
        json={"current_weight_kg": 7500.0, "registered_by": "duty_wang"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(box.id)
    assert data["box_code"] == "BOX-API-001"
    assert data["status"] == "FULL"
    assert data["current_weight_kg"] == 7500.0
    assert data["registered_by"] == "duty_wang"
    assert data["registered_full_at"] is not None

    assert "created_at" in data and data["created_at"] is not None
    assert "updated_at" in data and data["updated_at"] is not None
    assert "station_id" in data and data["station_id"] == str(station.id)
    assert "max_capacity_kg" in data and data["max_capacity_kg"] == 8000.0


@pytest.mark.asyncio
async def test_register_full_list_boxes_status_reflects_full(
    client: AsyncClient, seed_station_and_box
):
    station, box = seed_station_and_box

    list_before = await client.get("/api/stations/boxes")
    assert list_before.status_code == 200
    data_before = list_before.json()
    assert len(data_before) == 1
    assert data_before[0]["status"] == "EMPTY"

    response = await client.post(
        f"/api/stations/boxes/{box.id}/register-full",
        json={"current_weight_kg": 7500.0, "registered_by": "duty_wang"},
    )
    assert response.status_code == 200

    list_after = await client.get("/api/stations/boxes")
    assert list_after.status_code == 200
    data_after = list_after.json()
    assert len(data_after) == 1
    assert data_after[0]["status"] == "FULL"
    assert data_after[0]["current_weight_kg"] == 7500.0
    assert data_after[0]["registered_by"] == "duty_wang"

    filtered = await client.get("/api/stations/boxes", params={"status": "FULL"})
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    empty_filtered = await client.get("/api/stations/boxes", params={"status": "EMPTY"})
    assert empty_filtered.status_code == 200
    assert len(empty_filtered.json()) == 0


@pytest.mark.asyncio
async def test_enqueue_not_full_box_blocked_by_business_rule(
    client: AsyncClient, seed_station_and_box
):
    station, box = seed_station_and_box
    assert box.status == BoxStatus.EMPTY

    response = await client.post(
        "/api/dispatch/queue",
        json={"box_id": str(box.id), "priority": "NORMAL"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "未满载" in detail or "BOX_NOT_FULL" in detail

    response_high = await client.post(
        "/api/dispatch/queue",
        json={"box_id": str(box.id), "priority": "HIGH"},
    )
    assert response_high.status_code == 400
    detail_high = response_high.json()["detail"]
    assert "未满载" in detail_high or "PRIORITY" in detail_high

    list_response = await client.get("/api/dispatch/queue")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 0


@pytest.mark.asyncio
async def test_enqueue_full_box_succeeds(
    client: AsyncClient, seed_station_and_box
):
    station, box = seed_station_and_box

    register = await client.post(
        f"/api/stations/boxes/{box.id}/register-full",
        json={"current_weight_kg": 7500.0, "registered_by": "duty_wang"},
    )
    assert register.status_code == 200

    enqueue = await client.post(
        "/api/dispatch/queue",
        json={"box_id": str(box.id), "priority": "HIGH"},
    )
    assert enqueue.status_code == 201
    data = enqueue.json()
    assert data["box_id"] == str(box.id)
    assert data["priority"] == "HIGH"
    assert data["status"] == "WAITING"
    assert data["position"] == 1
    assert "created_at" in data and data["created_at"] is not None

    list_response = await client.get("/api/dispatch/queue")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["status"] == "WAITING"
