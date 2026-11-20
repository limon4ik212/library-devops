"""Бизнес-логика: книги, читатели, выдача и возврат литературы."""
import re
from datetime import date, datetime, timedelta

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_LOAN_DAYS = 14
MAX_OPEN_LOANS = 5


class ValidationError(Exception):
    """Некорректные входные данные (HTTP 400)."""


class NotFoundError(Exception):
    """Запись не найдена (HTTP 404)."""


class ConflictError(Exception):
    """Нарушение бизнес-правила (HTTP 409)."""


def _require(data, field):
    value = data.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"Поле '{field}' обязательно")
    return value.strip() if isinstance(value, str) else value


# ------------------------------------------------------------------- книги
def add_book(db, data):
    title = _require(data, "title")
    author = _require(data, "author")
    isbn = (data.get("isbn") or "").strip() or None
    year = data.get("year")
    copies = data.get("copies", 1)
    if not isinstance(copies, int) or copies < 1:
        raise ValidationError("Количество экземпляров должно быть целым числом ≥ 1")
    if year is not None:
        if not isinstance(year, int) or not (1000 <= year <= date.today().year):
            raise ValidationError("Некорректный год издания")
    with db.transaction() as cur:
        if isbn:
            cur.execute("SELECT id FROM books WHERE isbn = %s", (isbn,))
            if cur.fetchone():
                raise ConflictError(f"Книга с ISBN {isbn} уже существует")
        book_id = cur.insert(
            "INSERT INTO books (title, author, isbn, year, copies_total, copies_available) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (title, author, isbn, year, copies, copies),
        )
    return get_book(db, book_id)


def get_book(db, book_id):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM books WHERE id = %s", (book_id,))
        book = cur.fetchone()
    if not book:
        raise NotFoundError(f"Книга {book_id} не найдена")
    return _clean(book)


def search_books(db, query=None, author=None, available_only=False):
    sql = "SELECT * FROM books WHERE 1=1"
    params = []
    if query:
        sql += " AND (LOWER(title) LIKE %s OR LOWER(author) LIKE %s OR isbn = %s)"
        like = f"%{query.lower()}%"
        params += [like, like, query]
    if author:
        sql += " AND LOWER(author) LIKE %s"
        params.append(f"%{author.lower()}%")
    if available_only:
        sql += " AND copies_available > 0"
    sql += " ORDER BY title"
    with db.transaction() as cur:
        cur.execute(sql, tuple(params))
        return [_clean(b) for b in cur.fetchall()]


def delete_book(db, book_id):
    with db.transaction() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM loans WHERE book_id = %s AND returned_at IS NULL", (book_id,)
        )
        if cur.fetchone()["n"] > 0:
            raise ConflictError("Нельзя удалить книгу, которая выдана читателю")
        cur.execute("DELETE FROM loans WHERE book_id = %s", (book_id,))
        cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
        if cur.rowcount == 0:
            raise NotFoundError(f"Книга {book_id} не найдена")


# ----------------------------------------------------------------- читатели
def add_reader(db, data):
    full_name = _require(data, "full_name")
    email = _require(data, "email").lower()
    if not EMAIL_RE.match(email):
        raise ValidationError("Некорректный e-mail")
    with db.transaction() as cur:
        cur.execute("SELECT id FROM readers WHERE email = %s", (email,))
        if cur.fetchone():
            raise ConflictError("Читатель с таким e-mail уже зарегистрирован")
        reader_id = cur.insert(
            "INSERT INTO readers (full_name, email, phone) VALUES (%s, %s, %s)",
            (full_name, email, data.get("phone")),
        )
    return get_reader(db, reader_id)


def get_reader(db, reader_id):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM readers WHERE id = %s", (reader_id,))
        reader = cur.fetchone()
    if not reader:
        raise NotFoundError(f"Читатель {reader_id} не найден")
    return _clean(reader)


def list_readers(db):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM readers ORDER BY full_name")
        return [_clean(r) for r in cur.fetchall()]


# ------------------------------------------------------------ выдача книг
def issue_book(db, data, today=None):
    book_id = _require(data, "book_id")
    reader_id = _require(data, "reader_id")
    days = data.get("days", DEFAULT_LOAN_DAYS)
    if not isinstance(days, int) or not (1 <= days <= 60):
        raise ValidationError("Срок выдачи должен быть от 1 до 60 дней")
    today = today or date.today()
    get_book(db, book_id)
    get_reader(db, reader_id)
    with db.transaction() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM loans WHERE reader_id = %s AND returned_at IS NULL",
            (reader_id,),
        )
        if cur.fetchone()["n"] >= MAX_OPEN_LOANS:
            raise ConflictError(f"У читателя уже {MAX_OPEN_LOANS} книг на руках")
        cur.execute(
            "SELECT COUNT(*) AS n FROM loans "
            "WHERE reader_id = %s AND book_id = %s AND returned_at IS NULL",
            (reader_id, book_id),
        )
        if cur.fetchone()["n"] > 0:
            raise ConflictError("Эта книга уже выдана данному читателю")
        # Атомарное уменьшение остатка: защищает от выдачи последнего экземпляра дважды
        cur.execute(
            "UPDATE books SET copies_available = copies_available - 1 "
            "WHERE id = %s AND copies_available > 0",
            (book_id,),
        )
        if cur.rowcount == 0:
            raise ConflictError("Нет свободных экземпляров книги")
        due = today + timedelta(days=days)
        loan_id = cur.insert(
            "INSERT INTO loans (book_id, reader_id, due_date) VALUES (%s, %s, %s)",
            (book_id, reader_id, due.isoformat()),
        )
    return get_loan(db, loan_id)


def return_book(db, loan_id):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM loans WHERE id = %s", (loan_id,))
        loan = cur.fetchone()
        if not loan:
            raise NotFoundError(f"Выдача {loan_id} не найдена")
        if loan["returned_at"] is not None:
            raise ConflictError("Книга по этой выдаче уже возвращена")
        cur.execute(
            "UPDATE loans SET returned_at = %s WHERE id = %s",
            (datetime.now().isoformat(sep=" ", timespec="seconds"), loan_id),
        )
        cur.execute(
            "UPDATE books SET copies_available = copies_available + 1 WHERE id = %s",
            (loan["book_id"],),
        )
    return get_loan(db, loan_id)


def get_loan(db, loan_id):
    with db.transaction() as cur:
        cur.execute("SELECT * FROM loans WHERE id = %s", (loan_id,))
        loan = cur.fetchone()
    if not loan:
        raise NotFoundError(f"Выдача {loan_id} не найдена")
    return _clean(loan)


def list_loans(db, open_only=False, overdue_only=False, today=None):
    today = today or date.today()
    sql = (
        "SELECT l.*, b.title AS book_title, r.full_name AS reader_name FROM loans l "
        "JOIN books b ON b.id = l.book_id JOIN readers r ON r.id = l.reader_id WHERE 1=1"
    )
    params = []
    if open_only or overdue_only:
        sql += " AND l.returned_at IS NULL"
    if overdue_only:
        sql += " AND l.due_date < %s"
        params.append(today.isoformat())
    sql += " ORDER BY l.id"
    with db.transaction() as cur:
        cur.execute(sql, tuple(params))
        return [_clean(x) for x in cur.fetchall()]


def stats(db):
    with db.transaction() as cur:
        cur.execute(
            "SELECT COUNT(*) AS books, COALESCE(SUM(copies_total), 0) AS copies, "
            "COALESCE(SUM(copies_available), 0) AS available FROM books"
        )
        s = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS n FROM readers")
        s["readers"] = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM loans WHERE returned_at IS NULL")
        s["open_loans"] = cur.fetchone()["n"]
    return {k: int(v) for k, v in s.items()}


def _clean(row):
    """Приводит даты к строкам для JSON."""
    return {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in row.items()}
