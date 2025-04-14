# OCR API

API для распознавания текста с изображений на основе FastAPI и EasyOCR с веб-интерфейсом на React.

## Функциональность

- Регистрация и аутентификация пользователей
- Распознавание текста с изображений (русский и английский языки)
- Премиум-подписка с расширенными возможностями
- История запросов OCR
- Административная панель с статистикой и управлением

## Структура проекта

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # Основной файл приложения
│   ├── config.py              # Конфигурация приложения
│   ├── database.py            # Настройка подключения к БД
│   ├── dependencies.py        # Зависимости FastAPI
│   ├── models/                # Pydantic модели
│   ├── routers/               # Маршруты API
│   ├── services/              # Сервисы бизнес-логики
│   └── utils/                 # Утилиты
├── .env                       # Переменные окружения
└── requirements.txt           # Зависимости
```

## Установка и запуск

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл .env на основе .env.example:
```bash
cp .env.example .env
```

3. Отредактируйте .env файл, установив правильные значения:
```
SECRET_KEY=your_secret_key_here
MONGODB_URL=mongodb://localhost:27017
```

4. Запустите сервер:
```bash
python run.py
```

API будет доступен по адресу http://localhost:8000.
Документация API доступна по адресу http://localhost:8000/docs.

## Примеры API-запросов

### Регистрация пользователя
```bash
curl -X 'POST' \
  'http://localhost:8000/register' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "user@example.com",
  "username": "testuser",
  "password": "password123"
}'
```

### Аутентификация
```bash
curl -X 'POST' \
  'http://localhost:8000/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=testuser&password=password123'
```

### Распознавание текста
```bash
curl -X 'POST' \
  'http://localhost:8000/extract-text' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'file=@/path/to/your/image.jpg' \
  -F 'language=ru+en' \
  -F 'preprocess=true' \
  -F 'detail=false'
```

## Требования

- Python 3.8+
- MongoDB
- PyTorch

## Лицензия

MIT