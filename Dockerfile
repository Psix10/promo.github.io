FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Устанавливаем poetry и зависимости из pyproject.toml
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
