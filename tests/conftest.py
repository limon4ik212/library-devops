import os

import pytest

from app.db import Database
from app.main import create_app


@pytest.fixture
def db(tmp_path):
    """SQLite во временном файле, либо PostgreSQL, если задан TEST_DATABASE_URL (в CI)."""
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    database.init_schema()
    yield database
    if database.kind == "postgres":
        with database.transaction() as cur:
            cur.execute("TRUNCATE loans, readers, books RESTART IDENTITY CASCADE")


@pytest.fixture
def client(db):
    app = create_app(db)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def book(client):
    return client.post(
        "/api/books",
        json={"title": "Мастер и Маргарита", "author": "М. Булгаков",
              "isbn": "978-5-17-000001", "year": 1967, "copies": 2},
    ).get_json()


@pytest.fixture
def reader(client):
    return client.post(
        "/api/readers", json={"full_name": "Тестов Тест", "email": "test1@example.com"}
    ).get_json()
