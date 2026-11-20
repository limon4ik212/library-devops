"""HTTP API информационной системы управления библиотекой."""
import json
import logging
import os
import sys
import time
import uuid
from collections import defaultdict
from threading import Lock

from flask import Flask, g, jsonify, request

from app import services
from app.db import Database, from_env

APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")


# ---------------------------------------------------------------- логирование
class JsonFormatter(logging.Formatter):
    """Структурированные логи в формате JSON (удобно анализировать через docker logs | jq)."""

    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_ms", "error"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


log = logging.getLogger("library")


# -------------------------------------------------------------------- метрики
class Metrics:
    """Минимальный экспортер метрик в формате Prometheus."""

    def __init__(self):
        self.lock = Lock()
        self.requests = defaultdict(int)  # (method, endpoint, status) -> count
        self.latency_sum = defaultdict(float)
        self.errors = 0
        self.started = time.time()

    def observe(self, method, endpoint, status, seconds):
        with self.lock:
            self.requests[(method, endpoint, status)] += 1
            self.latency_sum[endpoint] += seconds
            if status >= 500:
                self.errors += 1

    def render(self, db_up, stats):
        lines = [
            "# HELP library_http_requests_total Количество HTTP-запросов",
            "# TYPE library_http_requests_total counter",
        ]
        with self.lock:
            for (m, e, s), n in sorted(self.requests.items()):
                lines.append(
                    f'library_http_requests_total{{method="{m}",endpoint="{e}",status="{s}"}} {n}'
                )
            lines += [
                "# HELP library_http_request_seconds_sum Суммарное время обработки",
                "# TYPE library_http_request_seconds_sum counter",
            ]
            for e, v in sorted(self.latency_sum.items()):
                lines.append(f'library_http_request_seconds_sum{{endpoint="{e}"}} {v:.6f}')
            lines += [
                "# TYPE library_http_errors_total counter",
                f"library_http_errors_total {self.errors}",
            ]
        lines += [
            "# TYPE library_uptime_seconds gauge",
            f"library_uptime_seconds {time.time() - self.started:.0f}",
            "# TYPE library_db_up gauge",
            f"library_db_up {1 if db_up else 0}",
        ]
        for key, value in (stats or {}).items():
            lines += [f"# TYPE library_{key} gauge", f"library_{key} {value}"]
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- приложение
def create_app(db: Database = None) -> Flask:
    setup_logging()
    app = Flask(__name__)
    app.json.ensure_ascii = False
    db = db or from_env()
    metrics = Metrics()
    app.config["DB"] = db
    app.config["METRICS"] = metrics

    if os.environ.get("SKIP_DB_INIT") != "1":
        for attempt in range(1, 11):
            try:
                db.init_schema()
                break
            except Exception as exc:  # БД может стартовать позже приложения
                log.warning("БД недоступна, попытка %s/10: %s", attempt, exc)
                time.sleep(2)

    @app.before_request
    def _start():
        g.start = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])

    @app.after_request
    def _finish(response):
        duration = time.perf_counter() - g.get("start", time.perf_counter())
        endpoint = request.url_rule.rule if request.url_rule else "unknown"
        metrics.observe(request.method, endpoint, response.status_code, duration)
        response.headers["X-Request-ID"] = g.get("request_id", "-")
        if endpoint not in ("/health", "/metrics"):
            level = logging.ERROR if response.status_code >= 500 else logging.INFO
            log.log(
                level,
                "request",
                extra={
                    "request_id": g.get("request_id"),
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
        return response

    # ---- обработка ошибок
    def _err(status, message):
        return jsonify({"error": message}), status

    @app.errorhandler(services.ValidationError)
    def _validation(e):
        return _err(400, str(e))

    @app.errorhandler(services.NotFoundError)
    def _not_found(e):
        return _err(404, str(e))

    @app.errorhandler(services.ConflictError)
    def _conflict(e):
        log.warning("business_conflict", extra={"error": str(e), "request_id": g.get("request_id")})
        return _err(409, str(e))

    @app.errorhandler(404)
    def _404(_):
        return _err(404, "Ресурс не найден")

    @app.errorhandler(Exception)
    def _unhandled(e):
        if hasattr(e, "code") and isinstance(getattr(e, "code"), int) and e.code < 500:
            return _err(e.code, getattr(e, "description", str(e)))
        log.exception("unhandled_error", extra={"error": str(e), "request_id": g.get("request_id")})
        return _err(500, "Внутренняя ошибка сервера")

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise services.ValidationError("Ожидается JSON-объект в теле запроса")
        return data

    # ---- служебные
    @app.get("/")
    def index():
        return jsonify(
            {
                "service": "Library Information System",
                "version": APP_VERSION,
                "endpoints": [
                    "GET/POST /api/books", "GET/DELETE /api/books/<id>",
                    "GET/POST /api/readers", "GET /api/readers/<id>",
                    "GET/POST /api/loans", "POST /api/loans/<id>/return",
                    "GET /api/stats", "GET /health", "GET /metrics",
                ],
            }
        )

    @app.get("/health")
    def health():
        try:
            db_ok = db.ping()
        except Exception as exc:
            log.error("healthcheck_db_failed", extra={"error": str(exc)})
            db_ok = False
        status = 200 if db_ok else 503
        return jsonify(
            {"status": "ok" if db_ok else "degraded", "database": "up" if db_ok else "down",
             "version": APP_VERSION}
        ), status

    @app.get("/metrics")
    def prom_metrics():
        try:
            db_ok, st = db.ping(), services.stats(db)
        except Exception:
            db_ok, st = False, None
        return metrics.render(db_ok, st), 200, {"Content-Type": "text/plain; version=0.0.4"}

    # ---- книги
    @app.get("/api/books")
    def books_list():
        return jsonify(
            services.search_books(
                db,
                query=request.args.get("q"),
                author=request.args.get("author"),
                available_only=request.args.get("available") == "true",
            )
        )

    @app.post("/api/books")
    def books_create():
        book = services.add_book(db, body())
        log.info("book_added", extra={"request_id": g.request_id})
        return jsonify(book), 201

    @app.get("/api/books/<int:book_id>")
    def books_get(book_id):
        return jsonify(services.get_book(db, book_id))

    @app.delete("/api/books/<int:book_id>")
    def books_delete(book_id):
        services.delete_book(db, book_id)
        return "", 204

    # ---- читатели
    @app.get("/api/readers")
    def readers_list():
        return jsonify(services.list_readers(db))

    @app.post("/api/readers")
    def readers_create():
        return jsonify(services.add_reader(db, body())), 201

    @app.get("/api/readers/<int:reader_id>")
    def readers_get(reader_id):
        return jsonify(services.get_reader(db, reader_id))

    # ---- выдачи
    @app.get("/api/loans")
    def loans_list():
        return jsonify(
            services.list_loans(
                db,
                open_only=request.args.get("open") == "true",
                overdue_only=request.args.get("overdue") == "true",
            )
        )

    @app.post("/api/loans")
    def loans_create():
        return jsonify(services.issue_book(db, body())), 201

    @app.post("/api/loans/<int:loan_id>/return")
    def loans_return(loan_id):
        return jsonify(services.return_book(db, loan_id))

    @app.get("/api/stats")
    def stats():
        return jsonify(services.stats(db))

    return app


if __name__ == "__main__":  # локальный запуск без gunicorn
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
