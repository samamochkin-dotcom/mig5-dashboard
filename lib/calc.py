"""Расчёты: рабочие дни, целевой план, прогноз даты выхода."""

from datetime import date, timedelta
from typing import List, Optional, Tuple

import pandas as pd


def working_days_between(start: date, end: date, extra_holidays: set) -> int:
    """Кол-во рабочих дней (Пн-Пт минус extra_holidays) от start (исключая) до end (включая)."""
    if start == end:
        return 0
    sign = 1
    if end < start:
        start, end = end, start
        sign = -1
    days = 0
    d = start + timedelta(days=1)
    while d <= end:
        if d.weekday() < 5 and d not in extra_holidays:
            days += 1
        d += timedelta(days=1)
    return sign * days


def working_days_until(target: date, today: Optional[date] = None,
                       extra_holidays: Optional[set] = None) -> int:
    """target > today → +N, target == today → 0, target < today → -N."""
    if today is None:
        today = date.today()
    if extra_holidays is None:
        extra_holidays = set()
    return working_days_between(today, target, extra_holidays)


def compute_target_plan(sop_total: int, base: int, dates: List[date],
                        increments: List[int]) -> List[Tuple[date, int, int]]:
    """Возвращает [(дата, кумулятив, прирост), ...].

    Первые 5 точек — фиксированные приросты.
    Если sop_total > cum_after_5 → последняя точка = sop_total.
    Иначе — только 5 точек (без 27.05).
    """
    cum = base
    plan: List[Tuple[date, int, int]] = []
    for d, inc in zip(dates[:5], increments):
        cum += inc
        plan.append((d, cum, inc))
    if len(dates) >= 6 and sop_total and sop_total > cum:
        last_inc = sop_total - cum
        plan.append((dates[5], sop_total, last_inc))
    return plan


def forecast_exit_date(closure_dates: pd.Series, sop_total: int,
                       window_days: int = 28,   # не используется (оставлено для совместимости)
                       extra_holidays: Optional[set] = None,
                       today: Optional[date] = None,
                       trend_start: Optional[date] = None) -> Optional[date]:
    """Прогноз даты завершения = линейная регрессия по факту с trend_start → когда cum = sop_total.

    Если факт ускоряется — slope растёт, прогноз смещается ближе.
    Если trend_start задан, точки до этой даты исключаются (не «держат» наклон).
    Если данных < 2 точек или регрессия отрицательная — возвращает None.
    """
    import numpy as np
    if today is None:
        today = date.today()
    if closure_dates is None or closure_dates.empty:
        return None

    cd = pd.to_datetime(closure_dates, errors="coerce").dropna()
    if cd.empty:
        return None

    # Кумулятив по дням (по всем точкам — чтобы cum включал старые)
    cum_df = (cd.dt.date.value_counts()
                .rename_axis("dt").reset_index(name="closed_day")
                .sort_values("dt"))
    cum_df["cum"] = cum_df["closed_day"].cumsum()
    if sop_total <= 0:
        return None

    closed_total = int(cum_df["cum"].iloc[-1])
    if sop_total <= closed_total:
        return today  # уже выполнено

    # Регрессию строим только по точкам с trend_start
    if trend_start is not None:
        cum_df = cum_df[cum_df["dt"] >= trend_start].reset_index(drop=True)
    if len(cum_df) < 2:
        return None

    x_ord = np.array([d.toordinal() for d in cum_df["dt"]])
    y_cum = cum_df["cum"].to_numpy()
    slope, intercept = np.polyfit(x_ord, y_cum, 1)   # cum = slope*x + intercept
    if slope <= 0:
        return None

    target_ord = (sop_total - intercept) / slope
    try:
        return date.fromordinal(int(round(target_ord)))
    except (ValueError, OverflowError):
        return None


def cumulative_by_date(closure_dates: pd.Series) -> pd.DataFrame:
    """Из серии дат снятия → DataFrame с кумулятивом по дням.

    Возвращает: dt (date), closed_day (int), cum (int).
    """
    cd = pd.to_datetime(closure_dates, errors="coerce").dropna()
    if cd.empty:
        return pd.DataFrame(columns=["dt", "closed_day", "cum"])
    df = (cd.dt.date.value_counts()
            .rename_axis("dt").reset_index(name="closed_day")
            .sort_values("dt"))
    df["cum"] = df["closed_day"].cumsum()
    return df.reset_index(drop=True)
