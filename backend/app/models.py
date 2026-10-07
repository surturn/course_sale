import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResourceType(str, enum.Enum):
    course = "course"
    book = "book"
    pdf = "pdf"


class LedgerState(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    confirmed = "confirmed"
    failed = "failed"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str] = mapped_column(String(12), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    type: Mapped[ResourceType] = mapped_column(Enum(ResourceType, name="resource_type"))
    # ponytail: whole KES only — M-Pesa STK push rejects decimals. Switch to Numeric if another gateway arrives.
    price: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    page_count: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    published: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    total_amount: Mapped[int] = mapped_column(Integer)
    resource_ids: Mapped[list[int]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (UniqueConstraint("user_id", "resource_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    price_paid: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderPaid(Base):
    """Append-only payment ledger. A DB trigger (see migration) rejects UPDATE/DELETE."""
    __tablename__ = "orders_paid"
    __table_args__ = (
        # One terminal row per order: duplicate Daraja callbacks (success or failure) become no-ops.
        Index("uq_orders_paid_terminal", "order_id", unique=True,
              postgresql_where=text("state IN ('confirmed', 'failed')")),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    state: Mapped[LedgerState] = mapped_column(Enum(LedgerState, name="ledger_state"))
    checkout_request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(20), unique=True)
    phone: Mapped[str] = mapped_column(String(12))
    amount: Mapped[int] = mapped_column(Integer)
    account_reference: Mapped[str] = mapped_column(String(20))
    failure_reason: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
