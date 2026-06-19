from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import BoxStatus, CompressionBox, Station
from app.rules.business_rules import check_box_can_queue
from app.schemas.schemas import BoxCreate, BoxRegisterFull, StationCreate


class BoxService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_station(self, data: StationCreate) -> Station:
        station = Station(name=data.name, address=data.address)
        self.db.add(station)
        await self.db.flush()
        return station

    async def list_stations(self) -> list[Station]:
        result = await self.db.execute(select(Station).order_by(Station.created_at))
        return list(result.scalars().all())

    async def create_box(self, data: BoxCreate) -> CompressionBox:
        box = CompressionBox(
            station_id=data.station_id,
            box_code=data.box_code,
            max_capacity_kg=data.max_capacity_kg,
            status=BoxStatus.EMPTY,
        )
        self.db.add(box)
        await self.db.flush()
        return box

    async def register_full(self, box_id: UUID, data: BoxRegisterFull) -> CompressionBox:
        box = await self.db.get(CompressionBox, box_id)
        if box is None:
            raise ValueError(f"压缩箱 {box_id} 不存在")
        if box.status == BoxStatus.FULL:
            raise ValueError(f"压缩箱 {box.box_code} 已是满载状态")
        if data.current_weight_kg > box.max_capacity_kg:
            raise ValueError(f"登记重量 {data.current_weight_kg}kg 超过最大容量 {box.max_capacity_kg}kg")

        box.status = BoxStatus.FULL
        box.current_weight_kg = data.current_weight_kg
        box.registered_full_at = datetime.now(timezone.utc)
        box.registered_by = data.registered_by
        await self.db.flush()
        return box

    async def list_boxes(self, station_id: UUID | None = None, status: BoxStatus | None = None) -> list[CompressionBox]:
        stmt = select(CompressionBox).order_by(CompressionBox.created_at)
        if station_id is not None:
            stmt = stmt.where(CompressionBox.station_id == station_id)
        if status is not None:
            stmt = stmt.where(CompressionBox.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_box(self, box_id: UUID) -> CompressionBox | None:
        return await self.db.get(CompressionBox, box_id)
