## Beauty Roulette (FastAPI + SQLite)

### Что сделано

- **Рулетка (колесо)**: страница `static/index.html` рисует сегменты и крутится до выпавшего приза.
- **Backend**: FastAPI в `app/main.py`.
- **Хранилище**: SQLite файл `beauty.db`, таблица `used_phones`.
- **Ограничение**: **1 телефон = 1 промокод** (по `phone` как primary key).
- **Призы**: проценты (5/10/15/20/25/30) + **“Приведи друга: -1000₽ вам и другу”**.

### Запуск (Poetry)

```bash
poetry install
poetry run uvicorn app.main:app --reload
```

Откройте в браузере `http://127.0.0.1:8000/`.

### API

- `GET /api/segments` — список сегментов (фронтенд рисует колесо по нему).
- `POST /api/spin` — выдача приза и промокода.

Пример запроса:

```bash
curl -X POST "http://127.0.0.1:8000/api/spin" ^
  -H "Content-Type: application/json" ^
  -d "{\"phone\":\"+7 999 000-00-00\"}"
```

### Настройка призов

Список сегментов задаётся в `app/main.py` в переменной `SEGMENTS` (веса `weight` влияют на вероятность выпадения).

