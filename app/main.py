import os
import random
import string
from datetime import datetime, timezone
from typing import Literal, Optional, NamedTuple

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sqlalchemy import Column, DateTime, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError


# =====================
# ENV
# =====================

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class Segment(NamedTuple):
    id: int
    label: str
    discount_type: Literal["percent", "fixed", "gift"]
    discount_value: Optional[int]
    weight: int


# wheel_id = 0 — базовое колесо (как было ранее)
SEGMENTS_BASE = [
    Segment(1, "Скидка 5%", "percent", 5, 30),
    Segment(2, "Скидка 10%", "percent", 10, 25),
    Segment(3, "Скидка 15%", "percent", 15, 20),
    Segment(4, "Скидка 20%", "percent", 20, 15),
    Segment(5, "Скидка 25%", "percent", 25, 8),
    Segment(6, "Скидка 30%", "percent", 30, 2),
    Segment(7, "Приведи друга: -1000₽ вам и другу", "fixed", 1000, 16),
]

# wheel_id = 1 — страница index1
SEGMENTS_WHEEL_1 = [
    Segment(101, "оформление бровей в подарок (при ламинировании ресниц)", "gift", None, 1),
    Segment(102, "-40% на ламинирование бровей", "percent", 40, 1),
    Segment(103, "-40% на ламинирование ресниц", "percent", 40, 1),
    Segment(104, "-30% на оформление бровей", "percent", 30, 1),
    Segment(105, "-20% тебе и другу", "percent", 20, 1),
    Segment(106, "-15% на три посещения подряд", "percent", 15, 1),
    Segment(107, "-15% на три посещения подряд", "percent", 15, 1),
]

# wheel_id = 2 — страница index2
SEGMENTS_WHEEL_2 = [
    Segment(201, "-10% на наращивание ресниц", "percent", 10, 1),
    Segment(202, "-10% на наращивание ресниц", "percent", 10, 1),
    Segment(203, "-20% на наращивание ресниц", "percent", 20, 1),
    Segment(204, "-20% на наращивание ресниц", "percent", 20, 1),
    Segment(205, "-30% на наращивание ресниц", "percent", 30, 1),
    Segment(206, "оформление бровей в подарок при наращивании ресниц", "gift", None, 1),
    Segment(207, "оформление бровей в подарок при наращивании ресниц", "gift", None, 1),
    Segment(208, "приди с подругой и получите -15% каждая на наращивание ресниц", "percent", 15, 1),
]

DEFAULT_WHEEL_ID = 0
SEGMENT_SETS: dict[int, list[Segment]] = {
    0: SEGMENTS_BASE,
    1: SEGMENTS_WHEEL_1,
    2: SEGMENTS_WHEEL_2,
}

# =====================
# DATABASE (SQLite)
# =====================

DATABASE_URL = "sqlite:///./beauty.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class UsedPhone(Base):
    __tablename__ = "used_phones"

    phone = Column(String, primary_key=True, index=True)
    promo_code = Column(String)
    segment_id = Column(Integer, nullable=True)
    segment_label = Column(String, nullable=True)
    wheel_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True)


Base.metadata.create_all(bind=engine)

def _ensure_schema():
    """
    Проект уже мог быть запущен с минимальной схемой (phone, promo_code).
    Для совместимости аккуратно добавляем новые колонки через ALTER TABLE.
    """
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(used_phones)")).fetchall()}

        if "segment_id" not in cols:
            conn.execute(text("ALTER TABLE used_phones ADD COLUMN segment_id INTEGER"))
        if "segment_label" not in cols:
            conn.execute(text("ALTER TABLE used_phones ADD COLUMN segment_label VARCHAR"))
        if "wheel_id" not in cols:
            conn.execute(text("ALTER TABLE used_phones ADD COLUMN wheel_id INTEGER"))
        if "created_at" not in cols:
            conn.execute(text("ALTER TABLE used_phones ADD COLUMN created_at DATETIME"))

_ensure_schema()


# =====================
# FASTAPI
# =====================

app = FastAPI(title="Beauty Roulette")


class SpinRequest(BaseModel):
    phone: str
    wheel_id: int | None = None


class SegmentOut(BaseModel):
    id: int
    label: str
    discount_type: Literal["percent", "fixed", "gift"]
    discount_value: Optional[int]


class SpinResponse(BaseModel):
    segment: SegmentOut
    promo_code: str


# =====================
# LOGIC
# =====================

def get_segments_for_wheel(wheel_id: int | None) -> list[Segment]:
    if wheel_id is None:
        wheel_id = DEFAULT_WHEEL_ID
    return SEGMENT_SETS.get(wheel_id, SEGMENT_SETS[DEFAULT_WHEEL_ID])


def choose_segment(segments: list[Segment]) -> Segment:
    """Выбирает сегмент с учетом веса"""
    total_weight = sum(s.weight for s in segments)
    rnd = random.uniform(0, total_weight)
    cumulative = 0
    
    for s in segments:
        cumulative += s.weight
        if rnd <= cumulative:
            return s
    
    return segments[-1]


def generate_promo_code(segment_label: str) -> str:
    """
    Формат: FEB2026-S<ID>-AB12CD34
    """
    prefix = "FEB2026"
    alphabet = string.ascii_uppercase + string.digits
    part1 = "".join(random.choice(alphabet) for _ in range(8))
    return f"{prefix}-S{segment_label}-{part1}"


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())

    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]

    return digits


async def send_to_telegram(phone: str, promo_code: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram disabled")
        return

    text = (
        "🎯 Новая заявка с рулетки\n\n"
        f"Номер телефона: +{phone}\n"
        f"Промокод: {promo_code}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text
            })
        except Exception as e:
            print("Telegram error:", e)


# =====================
# API
# =====================

@app.post("/api/spin", response_model=SpinResponse)
async def spin(req: SpinRequest):
    raw_phone = req.phone.strip()

    if not raw_phone:
        raise HTTPException(status_code=400, detail="Phone is required")

    phone = normalize_phone(raw_phone)

    if not (len(phone) == 11 and phone.startswith("7")):
        raise HTTPException(
            status_code=400,
            detail="Введите телефон в формате России (+7 900 000 00 00)"
        )

    db = SessionLocal()

    segments = get_segments_for_wheel(req.wheel_id)
    segment = choose_segment(segments)
    promo_code = generate_promo_code(str(segment.id))
    
    try:
        db.add(
            UsedPhone(
                phone=phone,
                promo_code=promo_code,
                segment_id=segment.id,
                segment_label=segment.label,
                wheel_id=req.wheel_id if req.wheel_id is not None else DEFAULT_WHEEL_ID,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Для этого номера промокод уже был выдан"
        )
    finally:
        db.close()

    await send_to_telegram(phone, promo_code)

    return SpinResponse(
        segment=SegmentOut(
            id=segment.id,
            label=segment.label,
            discount_type=segment.discount_type,
            discount_value=segment.discount_value,
        ),
        promo_code=promo_code,
    )

@app.get("/api/segments", response_model=list[SegmentOut])
async def segments(wheel_id: int | None = None):
    segs = get_segments_for_wheel(wheel_id)
    return [
        SegmentOut(
            id=s.id,
            label=s.label,
            discount_type=s.discount_type,
            discount_value=s.discount_value,
        )
        for s in segs
    ]

# =====================
# STATIC
# =====================

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.on_event("startup")
async def _startup():
    _ensure_schema()


app.mount("/static", StaticFiles(directory="static"), name="static")
