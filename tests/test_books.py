"""Тесты операций добавления и поиска книг."""


def test_add_book(client):
    r = client.post("/api/books", json={"title": "Война и мир", "author": "Л. Толстой", "copies": 3})
    assert r.status_code == 201
    data = r.get_json()
    assert data["id"] > 0
    assert data["copies_total"] == 3
    assert data["copies_available"] == 3


def test_add_book_requires_title(client):
    r = client.post("/api/books", json={"author": "Без названия"})
    assert r.status_code == 400
    assert "title" in r.get_json()["error"]


def test_add_book_invalid_copies(client):
    r = client.post("/api/books", json={"title": "X", "author": "Y", "copies": 0})
    assert r.status_code == 400


def test_add_book_invalid_year(client):
    r = client.post("/api/books", json={"title": "X", "author": "Y", "year": 3000})
    assert r.status_code == 400


def test_duplicate_isbn_rejected(client, book):
    r = client.post("/api/books", json={"title": "Копия", "author": "Z", "isbn": book["isbn"]})
    assert r.status_code == 409


def test_body_must_be_json(client):
    r = client.post("/api/books", data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_search_by_title_case_insensitive(client, book):
    client.post("/api/books", json={"title": "Преступление и наказание", "author": "Ф. Достоевский"})
    r = client.get("/api/books?q=мастер")
    titles = [b["title"] for b in r.get_json()]
    assert titles == ["Мастер и Маргарита"]


def test_search_latin_case_insensitive(client):
    client.post("/api/books", json={"title": "Clean Code", "author": "Robert Martin"})
    client.post("/api/books", json={"title": "Refactoring", "author": "Martin Fowler"})
    assert len(client.get("/api/books?q=CLEAN").get_json()) == 1
    assert len(client.get("/api/books?author=martin").get_json()) == 2


def test_search_by_isbn(client, book):
    r = client.get(f"/api/books?q={book['isbn']}")
    assert [b["id"] for b in r.get_json()] == [book["id"]]


def test_search_no_results(client, book):
    assert client.get("/api/books?q=несуществующая").get_json() == []


def test_get_book_not_found(client):
    assert client.get("/api/books/9999").status_code == 404


def test_delete_book(client, book):
    assert client.delete(f"/api/books/{book['id']}").status_code == 204
    assert client.get(f"/api/books/{book['id']}").status_code == 404
