"""Ledger invariants enforced by the database itself. Needs dev Postgres up + `alembic upgrade head`."""
import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

SEED = """
WITH u AS (INSERT INTO users (email, phone, full_name, password_hash)
           VALUES ('ledger@test.local', '254700000001', 'Ledger Test', 'x') RETURNING id),
     o AS (INSERT INTO orders (user_id, total_amount, resource_ids)
           SELECT id, 100, '[]' FROM u RETURNING id)
INSERT INTO orders_paid (order_id, state, phone, amount, account_reference)
SELECT id, 'confirmed', '254700000001', 100, 'INV-1' FROM o RETURNING order_id
"""


def run_in_rolled_back_tx(statement: str):
    """Seed one confirmed ledger row, run `statement` against it, always roll back."""
    async def go():
        engine = create_async_engine(settings.DATABASE_URL)
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                order_id = (await conn.execute(text(SEED))).scalar_one()
                await conn.execute(text(statement), {"order_id": order_id})
            finally:
                await tx.rollback()
        await engine.dispose()
    asyncio.run(go())


def test_ledger_rejects_update():
    with pytest.raises(DBAPIError, match="append-only"):
        run_in_rolled_back_tx("UPDATE orders_paid SET amount = 1 WHERE order_id = :order_id")


def test_ledger_rejects_delete():
    with pytest.raises(DBAPIError, match="append-only"):
        run_in_rolled_back_tx("DELETE FROM orders_paid WHERE order_id = :order_id")


def test_ledger_allows_only_one_terminal_row_per_order():
    with pytest.raises(IntegrityError, match="uq_orders_paid_terminal"):
        run_in_rolled_back_tx(
            "INSERT INTO orders_paid (order_id, state, phone, amount, account_reference) "
            "VALUES (:order_id, 'failed', '254700000001', 100, 'INV-1')"
        )
