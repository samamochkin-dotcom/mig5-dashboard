"""
МиГ-5 — дашборд аналитики замечаний экспертизы.

Запуск локально:
    streamlit run app.py

Деплой: Streamlit Community Cloud (привязать репо).
"""

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import config
from lib.anonymize import short_fio
from lib.calc import (
    cumulative_by_date,
    compute_target_plan,
    forecast_exit_date,
    working_days_until,
)
from lib.charts import dynamics_chart
from lib.data import get_data

# ── Настройки страницы ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="МиГ-5 — Дашборд экспертизы",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auto-refresh раз в N сек ─────────────────────────────────────────────────
# Streamlit rerun (не page-reload) — сохраняет session_state и фильтры.
st_autorefresh(interval=config.REFRESH_INTERVAL_SEC * 1000, key="auto_refresh")

# ── Загрузка данных ──────────────────────────────────────────────────────────
df, data_meta = get_data(config.SHEET_ID, config.SHEET_TAB)

# Анонимизация ФИО
if "fio" in df.columns:
    df["fio_short"] = df["fio"].apply(short_fio)
else:
    df["fio_short"] = ""

# ── Сайдбар: фильтры (применяются к KPI и таблице) ───────────────────────────
st.sidebar.markdown(f"### Фильтры")
_mins = config.REFRESH_INTERVAL_SEC // 60
st.sidebar.caption(f"Авто-обновление каждые {_mins} мин")
if st.sidebar.button("🔄 Обновить сейчас", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

razdely = sorted([r for r in df["razdel"].dropna().unique() if r]) if "razdel" in df.columns else []
experts = sorted([e for e in df["fio_short"].dropna().unique() if e])

# Раздел и Эксперт — взаимоисключающие фильтры
# (раздел → у эксперта может не быть замечаний в нём → KPI=0; путаница).
prev_razdel  = st.session_state.get("f_razdel", [])
prev_expert  = st.session_state.get("f_expert", [])

razdel_disabled = bool(prev_expert)
expert_disabled = bool(prev_razdel)

sel_razdely = st.sidebar.multiselect(
    "Раздел", razdely, default=[], key="f_razdel",
    disabled=razdel_disabled,
    help="Недоступно, пока выбран эксперт" if razdel_disabled else None,
)
sel_experts = st.sidebar.multiselect(
    "Эксперт", experts, default=[], key="f_expert",
    disabled=expert_disabled,
    help="Недоступно, пока выбран раздел" if expert_disabled else None,
)

statuses = sorted([s for s in df["status"].dropna().unique() if s]) if "status" in df.columns else []
sel_statuses = st.sidebar.multiselect("Статус", statuses, default=[], key="f_status")

types_ = sorted([t for t in df["type"].dropna().unique() if t]) if "type" in df.columns else []
all_types = st.sidebar.checkbox("Все типы", value=True,
                                help="Снять галку чтобы выбрать конкретные типы",
                                key="f_all_types")
sel_types = st.sidebar.multiselect("Тип замечания", types_, default=[],
                                   disabled=all_types, key="f_type")
if all_types:
    sel_types = []  # пусто = без фильтрации (т.е. все)

# Применяем фильтры → df_f
df_f = df.copy()
if sel_razdely:
    df_f = df_f[df_f["razdel"].isin(sel_razdely)]
if sel_experts:
    df_f = df_f[df_f["fio_short"].isin(sel_experts)]
if sel_statuses:
    df_f = df_f[df_f["status"].isin(sel_statuses)]
if sel_types:
    df_f = df_f[df_f["type"].isin(sel_types)]

# ── Метрики (по фильтрованным данным) ────────────────────────────────────────
total = len(df_f)
zakryto = (df_f["status"] == "Закрыто").sum() if "status" in df_f.columns else 0
v_rabote = total - zakryto
pct = round(zakryto / total * 100) if total else 0
days_left = working_days_until(config.EXIT_DATE,
                                today=date.today(),
                                extra_holidays=config.EXTRA_HOLIDAYS)
total_all = len(df)  # для прогресс-бара и графика — общая картина

# ── Шапка ────────────────────────────────────────────────────────────────────
if data_meta["source"] == "sheet":
    src_html = (
        f'<span style="color:#a0e3a0;">● Google Sheet</span>'
    )
elif data_meta["error"]:
    src_html = (
        f'<span style="color:{config.COLOR_EXIT_RED};">● Mock-данные (Sheet недоступен)</span>'
    )
else:
    src_html = (
        f'<span style="color:#ffd166;">● Mock-данные (secrets не настроены)</span>'
    )

st.markdown(
    f"""
    <div style="padding: 16px 24px; background: linear-gradient(135deg, {config.COLOR_PRIMARY} 0%, #2c4a6e 100%);
                border-radius: 12px; margin-bottom: 18px; color: white;">
      <div style="font-size: 24px; font-weight: 700;">📊 {config.PROJECT_NAME}</div>
      <div style="font-size: 14px; opacity: 0.95; margin-top: 8px;">
        Дело {config.CASE_NUMBER}
        &nbsp;·&nbsp;
        <span style="color: {config.COLOR_EXIT_RED};">
          Дата получения из МГЭ: {config.EXIT_DATE.strftime('%d.%m.%Y')}
        </span>
      </div>
      <div style="font-size: 13px; opacity: 0.85; margin-top: 4px;">
        Источник: {src_html}
        &nbsp;·&nbsp; Последняя синхронизация: {data_meta["last_pull"].strftime("%d.%m.%Y %H:%M:%S")}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if data_meta["source"] == "mock" and data_meta["error"]:
    st.error(f"⚠️ Не удалось загрузить из Google Sheet: {data_meta['error']}. "
             f"Показаны mock-данные.")

# ── KPI-ряд ──────────────────────────────────────────────────────────────────
def _kpi(col, value, label, accent):
    col.markdown(
        f"""
        <div style="background: white; border-radius: 14px;
                    padding: 26px 18px; text-align: center;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                    border-top: 5px solid {accent}; height: 100%;">
          <div style="font-size: 50px; font-weight: 800; color: {config.COLOR_PRIMARY}; line-height: 1;">
            {value}
          </div>
          <div style="font-size: 14px; color: #7f8c8d; margin-top: 10px;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

c1, c2, c3, c4, c5 = st.columns(5)
_kpi(c1, total,    "Всего замечаний",          config.COLOR_PRIMARY)
_kpi(c2, zakryto,  "Закрыто",                  config.COLOR_SUCCESS)
_kpi(c3, v_rabote, "В работе",                 config.COLOR_WARNING)
_kpi(c4, f"{pct}%", "Устранено",               config.COLOR_INFO)
_kpi(c5, days_left, "Рабочих дней до выхода из МГЭ", config.COLOR_DANGER)

st.markdown("&nbsp;", unsafe_allow_html=True)

# ── Progress bar к EXIT_DATE с вехами на линии (custom HTML/SVG) ─────────────
with st.container():
    st.markdown("##### Шкала прогресса")

    # Шкала по времени: от начала проекта до EXIT_DATE
    project_start = date(2025, 10, 27)  # дата дела
    total_span = (config.EXIT_DATE - project_start).days
    elapsed = max(0, (date.today() - project_start).days)
    time_pct = max(0, min(100, elapsed / total_span * 100))

    def _date_to_pct(d: date) -> float:
        return max(0, min(100, (d - project_start).days / total_span * 100))

    def _marker(pct: float, color: str, label: str,
                label_position: str = "below",
                label_offset: int = 0) -> str:
        """Маркер: треугольник + длинная вертикальная линия через бар + подпись.

        label_position: "above" (над баром, треугольник снизу указывает вверх)
                        или "below" (под баром, треугольник сверху указывает вниз).
        """
        if label_position == "above":
            triangle = (
                f'<div style="position:absolute; left:50%; top:42px; '
                f'transform:translateX(-50%); width:0; height:0; '
                f'border-left:6px solid transparent; border-right:6px solid transparent; '
                f'border-bottom:9px solid {color};"></div>'
            )
            label_top = "-26px"
        else:
            triangle = (
                f'<div style="position:absolute; left:50%; top:-21px; '
                f'transform:translateX(-50%); width:0; height:0; '
                f'border-left:6px solid transparent; border-right:6px solid transparent; '
                f'border-top:9px solid {color};"></div>'
            )
            label_top = "56px"
        line = (
            f'<div style="position:absolute; left:50%; top:-12px; '
            f'width:3px; height:54px; background:{color}; '
            f'transform:translateX(-50%); border-radius:2px;"></div>'
        )
        label_html = (
            f'<div style="position:absolute; top:{label_top}; '
            f'left:calc(50% + {label_offset}px); transform:translateX(-50%); '
            f'font-size:11px; font-weight:700; color:{color}; white-space:nowrap;">'
            f'{label}</div>'
        )
        return (
            f'<div style="position:absolute; left:{pct}%; top:0; bottom:0; '
            f'width:0; z-index:3;">{triangle}{line}{label_html}</div>'
        )

    # Маркер «Старт» — лейбл под баром
    start_marker = _marker(0, "#7f8c8d",
                           f"Старт · {project_start.strftime('%d.%m.%Y')}",
                           label_position="below", label_offset=40)

    # Вехи — лейблы под баром
    milestones_html = ""
    for m_date, short, _full in sorted(config.TARGET_MILESTONES, key=lambda m: m[0]):
        m_pct = _date_to_pct(m_date)
        passed = m_date <= date.today()
        m_color = "#27ae60" if passed else "#6a1b9a"
        milestones_html += _marker(m_pct, m_color,
                                   f"{short} · {m_date.strftime('%d.%m')}",
                                   label_position="below")

    # Маркер «Выход» — лейбл сверху, полная дата
    exit_marker = _marker(100, config.COLOR_EXIT_RED,
                          f"Выход · {config.EXIT_DATE.strftime('%d.%m.%Y')}",
                          label_position="above", label_offset=-30)

    st.markdown(
        f"""
        <div style="margin: 32px 0 32px 0; padding-right: 6px;">
          <div style="position:relative; height:30px; background:#ecf0f1; border-radius:6px; overflow:visible;">
            <div style="position:absolute; left:0; top:0; bottom:0; width:{time_pct}%;
                        background:linear-gradient(90deg, {config.COLOR_INFO}, {config.COLOR_SUCCESS});
                        border-radius:6px; z-index:1;"></div>
            <div style="position:absolute; left:{time_pct}%; top:-12px; height:54px; width:3px;
                        background:{config.COLOR_PRIMARY}; z-index:2; transform:translateX(-50%);
                        border-radius:2px;"></div>
            <div style="position:absolute; left:{time_pct}%; top:-26px; transform:translateX(-50%);
                        font-size:11px; font-weight:700; color:{config.COLOR_PRIMARY}; white-space:nowrap;">
              сегодня
            </div>
            {start_marker}
            {milestones_html}
            {exit_marker}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── График динамики + прогноз ────────────────────────────────────────────────
left, right = st.columns([3, 1])

with left:
    st.markdown("#### 📈 Динамика снятия замечаний")
    # График строится по полным данным (общая картина), без фильтров.
    # Берём только статус "Закрыто" — иначе ловим даты, проставленные заранее
    # без смены статуса (как в отчёте expertise_report).
    if "date_out" in df.columns and "status" in df.columns:
        closure_dates = df[df["status"] == "Закрыто"]["date_out"]
    elif "date_out" in df.columns:
        closure_dates = df["date_out"]
    else:
        closure_dates = pd.Series([], dtype="object")
    cum_df = cumulative_by_date(closure_dates)
    target_plan = compute_target_plan(
        sop_total=total_all,
        base=config.TARGET_PLAN_BASE,
        dates=config.TARGET_PLAN_DATES,
        increments=config.TARGET_PLAN_INCREMENTS,
    )
    fig = dynamics_chart(cum_df, target_plan, total_all, config.EXIT_DATE,
                         config.TARGET_MILESTONES,
                         trend_start=config.TREND_START_DATE)
    st.plotly_chart(fig, use_container_width=True)

with right:
    forecast = forecast_exit_date(
        closure_dates=closure_dates,
        sop_total=total_all,
        window_days=config.FORECAST_WINDOW_DAYS,
        extra_holidays=config.EXTRA_HOLIDAYS,
        trend_start=config.TREND_START_DATE,
    )
    if forecast is None:
        st.info("Недостаточно данных для прогноза. Нужны снятия за последние "
                f"{config.FORECAST_WINDOW_DAYS} дней.")
    else:
        delta_days = (forecast - config.EXIT_DATE).days
        exit_str = config.EXIT_DATE.strftime('%d.%m.%Y')
        if delta_days < 0:
            color = config.COLOR_SUCCESS
            verdict = (f"Ориентировочное опережение графика от целевого плана "
                       f"{exit_str} на {-delta_days} календарных дней")
        elif delta_days == 0:
            color = config.COLOR_SUCCESS
            verdict = f"В графике — выходим точно к {exit_str}"
        else:
            color = config.COLOR_DANGER
            verdict = (f"Ориентировочное отставание от целевого плана "
                       f"{exit_str} на {delta_days} календарных дней")
        # Spacer перед карточкой прогноза — чтобы карточка опустилась к центру графика
        st.markdown("<div style='height: 90px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="padding: 22px 16px; border-radius: 10px; text-align: center;
                        background: #f4f6f8; border-left: 4px solid {color};">
              <div style="font-size: 16px; font-weight: 700; color:#34495e;">
                🔮 Прогноз темпа по текущей динамике:
              </div>
              <div style="font-size: 26px; font-weight: 800; color: {color}; margin: 8px 0 12px 0;">
                {forecast.strftime('%d.%m.%Y')}
              </div>
              <div style="font-size: 13px; line-height: 1.45; color:#34495e;">{verdict}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Spacer между карточкой прогноза и блоком "Что если" — растягиваем по высоте графика
    st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)

    # Что-если: ползунок темпа
    st.markdown("##### Что если…")
    weeks_left = max(1, working_days_until(config.EXIT_DATE, date.today(),
                                            config.EXTRA_HOLIDAYS) // 5)
    remaining_now = total - zakryto
    needed_per_week = max(1, remaining_now // weeks_left) if weeks_left else remaining_now
    desired = st.slider("Снимать в неделю",
                        min_value=1, max_value=max(60, needed_per_week * 2),
                        value=max(15, needed_per_week), step=1)
    if desired > 0:
        weeks_to_finish = remaining_now / desired
        finish_date = date.today() + timedelta(days=int(round(weeks_to_finish * 7)))
        st.markdown(
            f"<div style='font-size:14px; color:#34495e; font-weight:600; margin-top:4px;'>"
            f"Закроем {remaining_now} зам. за ~{weeks_to_finish:.1f} нед. → "
            f"<span style='color:#b8860b; font-weight:700;'>{finish_date.strftime('%d.%m.%Y')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Таблица замечаний (по фильтрам) ──────────────────────────────────────────
st.markdown(f"#### 📋 Замечания (по фильтрам — {len(df_f)} из {total_all})")


display_cols = []
if "date_in" in df_f.columns:
    df_f["date_in_str"] = df_f["date_in"].dt.strftime("%d.%m.%Y").fillna("")
    display_cols.append("date_in_str")
if "razdel" in df_f.columns:    display_cols.append("razdel")
if "fio_short" in df_f.columns: display_cols.append("fio_short")
if "soderzh" in df_f.columns:   display_cols.append("soderzh")
if "type" in df_f.columns:      display_cols.append("type")
if "status" in df_f.columns:    display_cols.append("status")
if "date_out" in df_f.columns:
    df_f["date_out_str"] = df_f["date_out"].dt.strftime("%d.%m.%Y").fillna("")
    display_cols.append("date_out_str")

rename_for_display = {
    "date_in_str":  "Дата получения",
    "razdel":       "Раздел",
    "fio_short":    "Эксперт",
    "soderzh":      "Содержание",
    "type":         "Тип",
    "status":       "Статус",
    "date_out_str": "Дата снятия",
}
df_show = (df_f[display_cols]
           .rename(columns=rename_for_display)
           .reset_index(drop=True))

# HTML-таблица с переносом строк (st.dataframe в 1.39 текст не оборачивает).
# Минусы: нет встроенной сортировки по столбцу. Плюс: длинные замечания читаются.
table_css = """
<style>
.mig-table-wrap {max-height: 540px; overflow-y: auto; border: 1px solid #e1e6ec;
                  border-radius: 8px;}
.mig-table {width: 100%; border-collapse: collapse; font-size: 13px;}
.mig-table thead th {position: sticky; top: 0; background: #d6dfe9;
                      color: #1a3a5c; font-weight: 700; padding: 10px 12px;
                      text-align: center; border-bottom: 2px solid #b8c2cf; z-index: 1;}
.mig-table td {padding: 9px 12px; border-bottom: 1px solid #eef1f4;
                vertical-align: top; line-height: 1.4; word-wrap: break-word;}
.mig-table tr:hover td {background: #fafbfc;}
.mig-status-closed {color: #27ae60; font-weight: 600;}
.mig-status-work   {color: #e67e22; font-weight: 600;}
.col-date  {white-space: nowrap; width: 92px;}
.col-razd  {width: 70px;}
.col-fio   {width: 130px; white-space: nowrap;}
.col-type  {width: 130px;}
.col-stat  {width: 90px; white-space: nowrap;}
.col-text  {min-width: 360px;}
</style>
"""
st.markdown(table_css, unsafe_allow_html=True)

def _status_badge(s: str) -> str:
    cls = "mig-status-closed" if s == "Закрыто" else "mig-status-work"
    return f'<span class="{cls}">{s}</span>'

def _esc(x):
    return ("" if x is None else str(x)
            ).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

rows_html = []
for _, r in df_show.iterrows():
    rows_html.append(
        "<tr>"
        f'<td class="col-date">{_esc(r.get("Дата получения",""))}</td>'
        f'<td class="col-razd">{_esc(r.get("Раздел",""))}</td>'
        f'<td class="col-fio">{_esc(r.get("Эксперт",""))}</td>'
        f'<td class="col-text">{_esc(r.get("Содержание",""))}</td>'
        f'<td class="col-type">{_esc(r.get("Тип",""))}</td>'
        f'<td class="col-stat">{_status_badge(_esc(r.get("Статус","")))}</td>'
        f'<td class="col-date">{_esc(r.get("Дата снятия",""))}</td>'
        "</tr>"
    )
st.markdown(
    '<div class="mig-table-wrap"><table class="mig-table">'
    "<thead><tr>"
    '<th class="col-date">Дата получения</th>'
    '<th class="col-razd">Раздел</th>'
    '<th class="col-fio">Эксперт</th>'
    '<th class="col-text">Содержание</th>'
    '<th class="col-type">Тип</th>'
    '<th class="col-stat">Статус</th>'
    '<th class="col-date">Дата снятия</th>'
    "</tr></thead><tbody>"
    + "".join(rows_html) +
    "</tbody></table></div>",
    unsafe_allow_html=True,
)

# ── Футер ────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style='text-align:center; color:{config.COLOR_TEXT_MUTED}; font-size:12px;
                margin-top:22px; line-height:1.7;'>
      <div style='font-weight:600; color:#34495e;'>МиГ-5 — Аналитика замечаний экспертизы</div>
      <div style='margin-top:2px;'>Авто-обновление каждые {config.REFRESH_INTERVAL_SEC // 60} мин</div>
    </div>
    """,
    unsafe_allow_html=True,
)
