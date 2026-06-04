"""Загрузка данных из Google Sheet + fallback на моковые данные."""

import json
import os
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# ── Колонки Google Sheet "Замечания" (фактические заголовки) ─────────────────
# A: Раздел, B: Специализация Эксперта, C: ФИО Эксперта, D: Замечания,
# E: Дата получения, F: Зона ответственности, G: ФИО ответственного,
# H: Анализ по типам замечаний, I: Примечание, J: Статус, K: Дата снятия
COL_MAP = {
    "date_in":  "дата получения",
    "fio":      "фио",            # ловим "ФИО Эксперта" (берём первое совпадение)
    "razdel":   "раздел",
    "soderzh":  "замечания",
    "type":     "анализ по типам",
    "status":   "статус",
    "date_out": "дата снятия",
}


_LOCAL_JSON = Path(__file__).parent.parent / ".streamlit" / "service_account.json"


def _has_secrets() -> bool:
    """Проверяет, доступен ли service account (локальный JSON или Streamlit secrets)."""
    # Сначала проверяем локальный файл — чтобы не триггерить warning от st.secrets
    if _LOCAL_JSON.exists():
        return True
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        return False


def _get_credentials():
    """Возвращает google-auth credentials из локального файла или secrets."""
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    if _LOCAL_JSON.exists():
        return Credentials.from_service_account_file(str(_LOCAL_JSON), scopes=scopes)

    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(info, scopes=scopes)
    except Exception:
        pass

    raise RuntimeError(
        "Service account не найден. Положи JSON в .streamlit/service_account.json "
        "(локально) или добавь секцию [gcp_service_account] в Streamlit Cloud secrets."
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_from_sheet(sheet_id: str, sheet_tab: str) -> pd.DataFrame:
    """Читает лист из Google Sheet и возвращает DataFrame."""
    import gspread
    creds = _get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(sheet_tab)
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    header = rows[0]
    # Дедупликация имён колонок (если в Sheet есть пустые/повторяющиеся заголовки)
    seen = {}
    dedup_header = []
    for i, h in enumerate(header):
        h_clean = (h or f"col_{i}").strip()
        if h_clean in seen:
            seen[h_clean] += 1
            h_clean = f"{h_clean}__{seen[h_clean]}"
        else:
            seen[h_clean] = 0
        dedup_header.append(h_clean)
    df = pd.DataFrame(rows[1:], columns=dedup_header)
    return _normalize(df)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Унифицирует названия колонок и парсит даты/числа."""
    if df.empty:
        return df

    # Очистка имён колонок от \n и лишних пробелов
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]

    # Найдём колонки по подстроке (без чувствительности к регистру)
    def find(keyword: str) -> Optional[str]:
        kw = keyword.lower()
        for c in df.columns:
            if kw in str(c).lower():
                return c
        return None

    rename = {}
    used_cols = set()
    for short, label in COL_MAP.items():
        col = find(label)
        if col is not None and col != short and col not in used_cols:
            rename[col] = short
            used_cols.add(col)
    df = df.rename(columns=rename)

    # Уберём строки, где раздел и фио пусты (хвост таблицы)
    if "razdel" in df.columns and "fio" in df.columns:
        mask = (df["razdel"].astype(str).str.strip() != "") | \
               (df["fio"].astype(str).str.strip() != "")
        df = df[mask].reset_index(drop=True)

    # Даты
    for c in ("date_in", "date_out"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    # Чистка строк (защита от дубликатов имён — итерируем по уникальным)
    for c in list(df.columns):
        col = df[c]
        # Если по имени вернулся DataFrame (дубликаты) — берём первую колонку
        if isinstance(col, pd.DataFrame):
            col = col.iloc[:, 0]
        if col.dtype == object:
            col = col.astype(str).str.strip()
            col = col.where(col != "nan", "")
            df[c] = col
    return df


# ── Моковые данные (для разработки без secrets) ──────────────────────────────

def mock_data(sop_total: int = 425, today: Optional[date] = None) -> pd.DataFrame:
    """Генерирует синтетические данные похожие на реальные.

    Используется когда service account не подключён —
    чтобы можно было крутить вёрстку локально.
    """
    if today is None:
        today = date.today()
    rng = random.Random(42)

    razdely = ["АИО", "АР", "ВК", "ГОЧС", "ИГИ", "ИГДИ", "ИЭИ", "КР",
               "ОВиК", "ОДИ", "ООС", "ПБ", "ПОС", "ПТА", "ПЗ",
               "СПОЗУ", "ТХ", "ЭС", "ЭЭ"]
    # Реалистичный список экспертов (ФИО заглушки)
    experts = [
        "Иванов Иван Иванович", "Петров Пётр Петрович", "Сидоров Сидор Сидорович",
        "Кузнецов Алексей Викторович", "Смирнов Дмитрий Андреевич",
        "Васильев Илья Сергеевич", "Михайлов Олег Юрьевич",
        "Фёдоров Антон Александрович", "Волков Игорь Николаевич",
        "Соколов Максим Геннадьевич", "Лебедев Артём Дмитриевич",
        "Морозов Виктор Анатольевич",
    ]
    types_ = ["Сутевое", "ИД от Заказчика", "Отсылка к смежным разделам",
              "Оформительское", "СТУ", "ТУ", "Отсылка к ФЗ"]

    # Распределение замечаний по разделам (ближе к реальности)
    rows = []
    start = date(2026, 2, 1)
    for i in range(sop_total):
        date_in = start + timedelta(days=rng.randint(0, 60))
        razd = rng.choices(razdely, weights=[3, 5, 2, 1, 2, 1, 2, 1, 4, 3, 3, 2, 2, 1, 2, 2, 4, 4, 1])[0]
        fio = rng.choice(experts)
        typ = rng.choices(types_, weights=[10, 3, 3, 3, 3, 1, 1])[0]
        rows.append({
            "date_in":  pd.Timestamp(date_in),
            "fio":      fio,
            "razdel":   razd,
            "soderzh":  f"Замечание №{i+1}",
            "type":     typ,
            "addr":     "стр. 12",
            "status":   "В работе",
            "date_out": pd.NaT,
        })
    df = pd.DataFrame(rows)

    # Закроем ~32% замечаний случайными датами
    closed_idx = rng.sample(range(len(df)), k=int(len(df) * 0.32))
    for i in closed_idx:
        # Дата снятия = в окне Feb-Apr 2026, до today
        din = df.at[i, "date_in"].date()
        max_close = min(today, date(2026, 4, 25))
        if din < max_close:
            doff = din + timedelta(days=rng.randint(7, 60))
            if doff > max_close:
                doff = max_close
            df.at[i, "date_out"] = pd.Timestamp(doff)
            df.at[i, "status"] = "Закрыто"
    return df


def get_data(sheet_id: str, sheet_tab: str):
    """Главный загрузчик: пытается из Sheet, иначе fallback на mock.

    Возвращает (df, meta), где meta = {
        "source":    "sheet" | "mock",
        "last_pull": datetime — время последнего успешного pull,
        "error":    Optional[str] — текст ошибки если Sheet не дотянулся,
    }.
    """
    from datetime import datetime
    if _has_secrets():
        try:
            df = load_from_sheet(sheet_id, sheet_tab)
            return df, {"source": "sheet", "last_pull": datetime.now(), "error": None}
        except Exception as e:
            err = str(e)
            return mock_data(), {"source": "mock", "last_pull": datetime.now(), "error": err}
    return mock_data(), {"source": "mock", "last_pull": datetime.now(), "error": None}
