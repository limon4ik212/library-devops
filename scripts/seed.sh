#!/usr/bin/env bash
# Заполнение системы тестовыми (вымышленными) данными через API
source "$(dirname "$0")/common.sh"
post() { curl -s -X POST "$APP_URL$1" -H 'Content-Type: application/json' -d "$2"; echo; }
# id из JSON-ответа без зависимости от Python (на Windows python3 может отсутствовать)
id_of() { sed -n 's/.*"id":[[:space:]]*\([0-9]*\).*/\1/p'; }
B1=$(post /api/books '{"title":"Мастер и Маргарита","author":"Михаил Булгаков","isbn":"978-5-17-090001","year":1967,"copies":3}' | id_of)
post /api/books '{"title":"Преступление и наказание","author":"Фёдор Достоевский","isbn":"978-5-17-090002","year":1866,"copies":2}'
post /api/books '{"title":"Абай жолы","author":"Мухтар Ауэзов","isbn":"978-601-7-090003","year":1942,"copies":2}'
B4=$(post /api/books '{"title":"Clean Code","author":"Robert Martin","isbn":"978-0-13-235088","year":2008,"copies":1}' | id_of)
post /api/books '{"title":"The DevOps Handbook","author":"Gene Kim","isbn":"978-1-942788-00-3","year":2016,"copies":2}'
R1=$(post /api/readers '{"full_name":"Иванов Иван","email":"ivanov@example.com","phone":"+7 700 000 0001"}' | id_of)
R2=$(post /api/readers '{"full_name":"Петрова Анна","email":"petrova@example.com"}' | id_of)
post /api/loans "{\"book_id\":$B1,\"reader_id\":$R1,\"days\":14}"
post /api/loans "{\"book_id\":$B4,\"reader_id\":$R2,\"days\":7}"
log "Тестовые данные загружены"; curl -s "$APP_URL/api/stats"; echo
