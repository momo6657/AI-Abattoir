import asyncio
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.main import app

TEST_DB_DIR = Path(tempfile.gettempdir()) / "ai-abattoir-tests"
TEST_DB_DIR.mkdir(exist_ok=True)
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_DIR / f'test-{os.getpid()}-{uuid4().hex}.db'}"

engine = create_async_engine(TEST_DATABASE_URL, echo=False, connect_args={"timeout": 30})
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db():
    async with TestSessionLocal() as session:
        yield session
