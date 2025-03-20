# Подключаем базовый слой с python 3.10
FROM python:3.10

# Переходим в образе в директорию /app: в ней будем хранить код проекта
WORKDIR /app

# Копируем файл с зависимостями в образ
COPY requirements.txt .

# Устанавливаем необходимые зависимости в образ
RUN pip install -r requirements.txt --no-cache-dir

# Сохраняем все файлы в рабочую директорию /app
COPY . .

# Переходим в каталог c manage.py
WORKDIR djserver

# При старте контейнера запустить сервер разработки
CMD ["python", "manage.py", "runserver", "0:8000"]