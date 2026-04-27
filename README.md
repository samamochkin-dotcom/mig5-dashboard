# MiG-5 Dashboard

Онлайн-дашборд аналитики замечаний экспертизы по делу 77-9498/25-(0)-0.

Тянет данные из Google Sheet, авто-обновляется раз в 30 секунд, шарится команде/руководству по ссылке.

## Стек
- **Streamlit** — UI и хостинг (Community Cloud)
- **gspread** + Service Account — read-only доступ к Google Sheet
- **Plotly** — интерактивные графики
- **pandas** — обработка данных

## Структура
```
mig5-dashboard/
├── app.py                  # точка входа Streamlit
├── config.py               # константы проекта (даты, цвета, sheet_id)
├── requirements.txt        # зависимости
├── lib/
│   ├── data.py             # загрузка из Sheet + mock fallback
│   ├── calc.py             # рабочие дни, целевой план, прогноз
│   ├── charts.py           # Plotly графики
│   └── anonymize.py        # ФИО → «Иванов И.И.»
└── .streamlit/
    ├── config.toml         # тема Streamlit (в git)
    └── service_account.json  # секретный ключ (НЕ в git)
```

## Локальный запуск

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Если `.streamlit/service_account.json` отсутствует — приложение поднимется с моковыми данными.

## Деплой
1. Push в этот репозиторий
2. На share.streamlit.io подключить репо
3. В Secrets вставить содержимое JSON-ключа в секцию `[gcp_service_account]`

## Безопасность
- ФИО экспертов в дашборде → формат «Фамилия И.И.»
- Service Account имеет только Viewer на одну таблицу
- JSON-ключ не попадает в репозиторий (см. `.gitignore`)
