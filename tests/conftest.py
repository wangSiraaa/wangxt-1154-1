from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.models import (
    BoxStatus,
    CompressionBox,
    DisinfectionStatus,
    DispatchOrder,
    DispatchStatus,
    PriorityLevel,
    QueueStatus,
    ReviewOrder,
    ReviewStatus,
    Station,
    TransferQueue,
    Vehicle,
    VehicleStatus,
    WeighingRecord,
    WeighingStatus,
)

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

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
async def sample_station(db_session: AsyncSession):
    station = Station(name="城东压缩站", address="城东路88号")
    db_session.add(station)
    await db_session.flush()
    return station


@pytest_asyncio.fixture
async def sample_box(db_session: AsyncSession, sample_station: Station):
    box = CompressionBox(
        station_id=sample_station.id,
        box_code="BOX-001",
        max_capacity_kg=8000.0,
        status=BoxStatus.EMPTY,
    )
    db_session.add(box)
    await db_session.flush()
    return box


@pytest_asyncio.fixture
async def sample_full_box(db_session: AsyncSession, sample_station: Station):
    box = CompressionBox(
        station_id=sample_station.id,
        box_code="BOX-FULL-001",
        max_capacity_kg=8000.0,
        status=BoxStatus.FULL,
        current_weight_kg=7500.0,
        registered_by="duty_zhang",
    )
    db_session.add(box)
    await db_session.flush()
    return box


@pytest_asyncio.fixture
async def sample_vehicle(db_session: AsyncSession):
    vehicle = Vehicle(
        plate_number="京A12345",
        driver_name="李师傅",
        status=VehicleStatus.READY,
        disinfection_status=DisinfectionStatus.COMPLETED,
    )
    db_session.add(vehicle)
    await db_session.flush()
    return vehicle


@pytest_asyncio.fixture
async def sample_queue(db_session: AsyncSession, sample_full_box: CompressionBox):
    queue = TransferQueue(
        box_id=sample_full_box.id,
        priority=PriorityLevel.NORMAL,
        status=QueueStatus.WAITING,
        position=1,
    )
    db_session.add(queue)
    await db_session.flush()
    return queue
