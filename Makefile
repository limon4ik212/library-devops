.PHONY: up up-mon down status logs analyze backup restore seed failure smoke security test lint
up:        ; ./scripts/start.sh
up-mon:    ; ./scripts/start.sh --monitoring
down:      ; ./scripts/stop.sh
status:    ; ./scripts/status.sh
logs:      ; docker compose logs -f app
analyze:   ; ./scripts/analyze_logs.sh
backup:    ; ./scripts/backup.sh
restore:   ; ./scripts/restore.sh
seed:      ; ./scripts/seed.sh
failure:   ; ./scripts/simulate_failure.sh
smoke:     ; ./scripts/smoke_test.sh
security:  ; ./scripts/security_check.sh
test:      ; python -m pytest --cov=app --cov-report=term-missing
lint:      ; flake8 app tests
