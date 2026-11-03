# DBoard — Marketplace Dashboard

Дашборд для мониторинга продаж и остатков с маркетплейсов **Wildberries** и **Ozon**.

Остатки и продажи можно смотреть в трёх разрезах: **все склады** (по умолчанию), **склады маркетплейса** (FBO для Ozon / FBW для WB) и **свой склад** (FBS). Переключатель «Все склады / Склады WB (FBW) / Ozon FBO / Свой склад FBS» находится над диаграммой; выбранный разрез применяется к диаграмме, таблице «Остатки», матрице «Регионы», «Мониторингу» и таблице «Отгрузки».

![Dashboard Preview](https://via.placeholder.com/800x400/050505/a855f7?text=DBoard+AI)

## 🚀 Быстрый старт

### 1. Установите Python
Необходим Python 3.10+ (рекомендуется 3.14).

### 2. Установите зависимости
```bash
pip install -r requirements.txt
```

### 3. Настройте API ключи
Отредактируйте файл `Credentials.env`:
```
WB_API_TOKEN=ваш_токен_wildberries
OZON_CLIENT_ID=ваш_client_id_ozon
OZON_API_KEY=ваш_api_key_ozon
```

### 4. Обновите данные
```bash
python Scripts/run_all.py
```

### 5. Откройте дашборд
Запустите локальный сервер:
```bash
python -m http.server 8080
```
Откройте в браузере: http://localhost:8080

---

## 📁 Структура проекта

```
DBoard/
├── index.html              # Главная страница дашборда
├── main.js                 # Логика загрузки данных
├── style.css               # Стили (glassmorphism, анимации)
├── dashboard_data.json     # Данные для отображения (генерируется)
├── requirements.txt        # Python зависимости
├── Credentials.env         # API ключи (НЕ КОММИТИТЬ!)
├── Agents/                 # Инструкции агентов
├── Scripts/                # Python-скрипты
│   ├── run_all.py          # Единая точка запуска
│   ├── fetch_wb_data.py    # Получение данных WB
│   ├── fetch_ozon_data.py  # Получение данных Ozon
│   └── prepare_dashboard_data.py  # Подготовка JSON
└── Executions/             # Сырые данные API
```

---

## 🔄 Обновление данных

Данные обновляются вручную командой:
```bash
python Scripts/run_all.py
```

Для автоматического обновления можно настроить Task Scheduler (Windows) или cron (Linux).

---

## ⚠️ Безопасность

> **ВАЖНО:** Никогда не добавляйте `Credentials.env` в публичный репозиторий!

Добавьте в `.gitignore`:
```
Credentials.env
Executions/
dashboard_data.json
```

---

## 🛠 API Endpoints

### Wildberries — склады маркетплейса (FBW)
- Остатки: `GET https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains` (задание → статус → download)
- Продажи: `GET https://statistics-api.wildberries.ru/api/v1/supplier/sales`
- Заказы: `GET https://statistics-api.wildberries.ru/api/v1/supplier/orders`

### Wildberries — свои склады (FBS)
- Список своих складов: `GET https://marketplace-api.wildberries.ru/api/v3/warehouses`
- Остатки по складу: `POST https://marketplace-api.wildberries.ru/api/v3/stocks/{warehouseId}` (тело: `chrtIds`)
- Сопоставление `chrtID → артикул`: `POST https://content-api.wildberries.ru/content/v2/get/cards/list`

### Ozon — склады маркетплейса (FBO)
- Остатки по складам: `POST https://api-seller.ozon.ru/v2/analytics/stock_on_warehouses`

### Ozon — свои склады (FBS)
- Остатки по складам продавца: `POST https://api-seller.ozon.ru/v2/product/info/stocks-by-warehouse/fbs`
- Список складов: `POST https://api-seller.ozon.ru/v1/warehouse/list`

### Ozon — продажи
- Заказы: `POST https://api-seller.ozon.ru/v2/posting/fbo/list`
- Финансы/выкупы: `POST https://api-seller.ozon.ru/v3/finance/transaction/list`

> Для остатков на **своих** складах токен WB должен иметь категории «Маркетплейс» и «Контент»; ключ Ozon — доступ к ценам и остаткам.

---

## 📝 Лицензия

MIT License
