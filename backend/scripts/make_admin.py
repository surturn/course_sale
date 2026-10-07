"""Promote an existing account to admin: python -m scripts.make_admin you@example.com"""
import asyncio
import sys

from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models import User


async def main(email: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(update(User).where(User.email == email.lower()).values(is_admin=True))
        await db.commit()
    print(f"{email} is now an admin" if result.rowcount else f"No account with email {email}; register first")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
