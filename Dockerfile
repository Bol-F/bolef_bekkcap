FROM python:3.12-slim

# Чтобы Python вёл себя нормально в контейнере
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Рабочая директория
WORKDIR /app

# Системные зависимости (для psycopg2 и т.п.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Команда по умолчанию:
# 1) collectstatic
# 2) migrate
# 3) запустить gunicorn
CMD ["sh", "-c", "python manage.py collectstatic --noinput \
    && python manage.py migrate \
    && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
