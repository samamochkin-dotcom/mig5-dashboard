"""
Конфигурация дашборда МиГ-5.

Параметры проекта вынесены отдельно — чтобы менять без рытья по коду.
Если в будущем захочется тянуть из вкладки `Settings` Google Sheet —
заменим эти константы на функцию-загрузчик.
"""

from datetime import date

# ── Источник данных ──────────────────────────────────────────────────────────
# ID берётся из Streamlit secrets (на проде) или fallback из локального файла
# C:\Users\MamochkinSA\Desktop\Claude\MiG-5\7_Dashboards\mig5-dashboard\.streamlit\sheet_id.txt
# чтобы не светить ID в публичном репозитории.
def _load_sheet_id() -> str:
    try:
        import streamlit as st
        if "sheet_id" in st.secrets:
            return str(st.secrets["sheet_id"])
    except Exception:
        pass
    from pathlib import Path
    f = Path(__file__).parent / ".streamlit" / "sheet_id.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "SHEET_ID не найден. Создай .streamlit/sheet_id.txt с ID таблицы "
        "(локально) или добавь sheet_id = \"...\" в Streamlit Cloud secrets."
    )

SHEET_ID = _load_sheet_id()
SHEET_TAB = "Замечания"

# ── Параметры проекта ────────────────────────────────────────────────────────
CASE_NUMBER = "77-9498/25-(0)-0 от 27.10.2025"
PROJECT_NAME = "МиГ-5 — Аналитика замечаний экспертизы"

# ── Сроки ────────────────────────────────────────────────────────────────────
EXIT_DATE = date(2026, 5, 27)

# Дополнительные нерабочие дни (помимо суббот/воскресений)
EXTRA_HOLIDAYS = {
    date(2026, 5,  1),  # Праздник Весны и Труда
    date(2026, 5, 11),  # Перенос (День Победы 09.05 — суббота)
}

# ── Целевой план снятия замечаний ────────────────────────────────────────────
TARGET_PLAN_BASE = 126                          # снято на 16.04.2026 (база)
TARGET_PLAN_DATES = [
    date(2026, 4, 22),
    date(2026, 4, 29),
    date(2026, 5,  6),
    date(2026, 5, 13),
    date(2026, 5, 20),
    date(2026, 5, 27),
]
TARGET_PLAN_INCREMENTS = [15, 15, 15, 40, 90]   # первые 5, 6-я динамическая

# ── Вехи ─────────────────────────────────────────────────────────────────────
TARGET_MILESTONES = [
    (date(2026, 4, 30), "АПР", "30.04 — Согласование всех АПР"),
    (date(2026, 5, 18), "ИД",  "18.05 — Получение ГЗК, ТУ, СТУ ПБ, АГР"),
]

# ── Прогноз выхода ───────────────────────────────────────────────────────────
FORECAST_WINDOW_DAYS = 28   # (deprecated, оставлено для совместимости)
# Регрессия (тренд + блок «Прогноз») считается только по точкам с этой даты —
# чтобы старые медленные недели не «удерживали» наклон при ускорении.
TREND_START_DATE = date(2026, 4, 1)

# ── UI ───────────────────────────────────────────────────────────────────────
REFRESH_INTERVAL_SEC = 600  # авто-обновление страницы (10 мин — чтобы не дёргалось)
COLOR_PRIMARY  = "#1a3a5c"
COLOR_SUCCESS  = "#27ae60"
COLOR_WARNING  = "#e67e22"
COLOR_INFO     = "#2980b9"
COLOR_DANGER   = "#c0392b"
COLOR_EXIT_RED = "#ff6b6b"
COLOR_CARD_BG  = "#ffffff"   # карточки белые на сером фоне
COLOR_CARD_BG2 = "#f7f9fb"
COLOR_TEXT_MUTED = "#7f8c8d"
COLOR_BORDER   = "#c8d2dc"
