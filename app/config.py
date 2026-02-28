# app/config.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class SegmentConfig:
    id: int
    label: str
    discount_type: str  # "percent" | "fixed" | "gift"
    discount_value: Optional[int]
    weight: int


SEGMENTS: list[SegmentConfig] = [
    SegmentConfig(id=1, label="-10% на маникюр", discount_type="percent", discount_value=10, weight=50),
    SegmentConfig(id=2, label="-20% на окрашивание", discount_type="percent", discount_value=20, weight=30),
    SegmentConfig(id=3, label="Уход в подарок", discount_type="gift", discount_value=None, weight=20),
]
