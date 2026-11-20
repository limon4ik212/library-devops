"""Тесты читателей, выдачи и возврата книг."""
from datetime import date

from app import services


def issue(client, book, reader, **kw):
    return client.post("/api/loans", json={"book_id": book["id"], "reader_id": reader["id"], **kw})


def test_add_reader(client, reader):
    assert reader["email"] == "test1@example.com"


def test_reader_invalid_email(client):
    r = client.post("/api/readers", json={"full_name": "A", "email": "bad-email"})
    assert r.status_code == 400


def test_reader_duplicate_email(client, reader):
    r = client.post("/api/readers", json={"full_name": "B", "email": "TEST1@example.com"})
    assert r.status_code == 409


def test_issue_decreases_available(client, book, reader):
    r = issue(client, book, reader)
    assert r.status_code == 201
    assert client.get(f"/api/books/{book['id']}").get_json()["copies_available"] == 1


def test_cannot_issue_when_no_copies(client, book):
    readers = [
        client.post("/api/readers", json={"full_name": f"R{i}", "email": f"r{i}@ex.com"}).get_json()
        for i in range(3)
    ]
    assert issue(client, book, readers[0]).status_code == 201
    assert issue(client, book, readers[1]).status_code == 201
    r = issue(client, book, readers[2])
    assert r.status_code == 409
    assert client.get(f"/api/books/{book['id']}").get_json()["copies_available"] == 0


def test_cannot_issue_same_book_twice(client, book, reader):
    issue(client, book, reader)
    assert issue(client, book, reader).status_code == 409


def test_reader_loan_limit(client, reader):
    for i in range(services.MAX_OPEN_LOANS):
        b = client.post("/api/books", json={"title": f"B{i}", "author": "A"}).get_json()
        assert issue(client, b, reader).status_code == 201
    extra = client.post("/api/books", json={"title": "Extra", "author": "A"}).get_json()
    assert issue(client, extra, reader).status_code == 409


def test_return_restores_available(client, book, reader):
    loan = issue(client, book, reader).get_json()
    r = client.post(f"/api/loans/{loan['id']}/return")
    assert r.status_code == 200
    assert r.get_json()["returned_at"] is not None
    assert client.get(f"/api/books/{book['id']}").get_json()["copies_available"] == 2
    # повторный возврат запрещён
    assert client.post(f"/api/loans/{loan['id']}/return").status_code == 409


def test_issue_unknown_book(client, reader):
    r = client.post("/api/loans", json={"book_id": 999, "reader_id": reader["id"]})
    assert r.status_code == 404


def test_invalid_loan_days(client, book, reader):
    assert issue(client, book, reader, days=0).status_code == 400


def test_overdue_loans(db, client, book, reader):
    services.issue_book(db, {"book_id": book["id"], "reader_id": reader["id"], "days": 7},
                        today=date(2020, 1, 1))
    overdue = client.get("/api/loans?overdue=true").get_json()
    assert len(overdue) == 1
    assert overdue[0]["book_title"] == book["title"]


def test_available_filter(client, book, reader):
    other = client.post("/api/books", json={"title": "Одна копия", "author": "A"}).get_json()
    issue(client, other, reader)
    ids = [b["id"] for b in client.get("/api/books?available=true").get_json()]
    assert book["id"] in ids and other["id"] not in ids


def test_delete_issued_book_forbidden(client, book, reader):
    issue(client, book, reader)
    assert client.delete(f"/api/books/{book['id']}").status_code == 409
