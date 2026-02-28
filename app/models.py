# models.py
from sqlalchemy import Column, String, Integer, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class UsedPhone(Base):
    __tablename__ = "used_phones"

    phone = Column(String, primary_key=True, index=True)
    promo_code = Column(String)
    segment_id = Column(Integer, nullable=True)
    segment_label = Column(String, nullable=True)
    wheel_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True)


engine = create_engine(
    "sqlite:///./beauty.db",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(bind=engine)
