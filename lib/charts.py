"""Plotly-графики для дашборда."""

from datetime import date, timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def dynamics_chart(cumulative_df: pd.DataFrame,
                   target_plan: List[Tuple[date, int, int]],
                   sop_total: int,
                   exit_date: date,
                   milestones: list,
                   trend_start: date = None) -> go.Figure:
    """График кумулятивной динамики снятия замечаний.

    cumulative_df: DataFrame[dt, closed_day, cum]
    target_plan: [(date, cum, delta), ...]
    """
    fig = go.Figure()
    fact_annotations = []

    # Факт
    if not cumulative_df.empty:
        pct = (cumulative_df["cum"] / sop_total * 100.0).round(1) if sop_total else cumulative_df["cum"]
        fig.add_trace(go.Scatter(
            x=cumulative_df["dt"], y=pct,
            mode="lines+markers",
            name="Снято замечаний (факт)",
            line=dict(color="#1a237e", width=2),
            marker=dict(size=7, color="#1a237e"),
            fill="tozeroy",
            fillcolor="rgba(26,35,126,0.07)",
            customdata=[[c] for c in cumulative_df["cum"]],
            hovertemplate="%{x|%d.%m.%Y}<br>Факт: %{y:.1f}%% (%{customdata[0]} зам.)<extra></extra>",
        ))
        # Выноски с % на каждой точке факта (все влево, последняя — вправо)
        n = len(cumulative_df)
        for i, (d, p) in enumerate(zip(cumulative_df["dt"], pct)):
            is_last = (i == n - 1)
            ax = 30 if is_last else -30
            ay = -30 if is_last else -28
            fact_annotations.append(dict(
                x=d, y=float(p),
                text=f"<b>{p:.1f}%</b>",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1,
                arrowcolor="#1a237e",
                ax=ax, ay=ay,
                font=dict(size=10, color="#1a237e"),
                bgcolor="rgba(255,255,255,0.85)",
                borderpad=2,
            ))

    # План — независимая линия от своих собственных точек
    plan_annotations = []
    if target_plan and sop_total > 0:
        plan_dates = [t[0] for t in target_plan]
        plan_cums = [t[1] for t in target_plan]
        plan_pct = [round(c / sop_total * 100, 1) for c in plan_cums]
        fig.add_trace(go.Scatter(
            x=plan_dates, y=plan_pct,
            mode="lines+markers",
            name="Целевой план",
            line=dict(color="#f9a825", width=2, dash="dot"),
            marker=dict(size=7, color="#f9a825", symbol="diamond"),
            customdata=[[c] for c in plan_cums],
            hovertemplate="%{x|%d.%m.%Y}<br>План: %{y:.1f}%% (%{customdata[0]} зам.)<extra></extra>",
        ))
        # Выноски с количеством замечаний на каждой точке
        # Если точка плана близко к вехе — сдвигаем подпись вправо, чтобы не пересекалась
        # с вертикальной линией выноски вехи
        ms_dates = [m[0] for m in milestones] if milestones else []
        def _near_milestone(plan_date):
            return any(abs((plan_date - md).days) <= 3 for md in ms_dates)
        for i, (d, cum, _delta) in enumerate(target_plan):
            is_last = (i == len(target_plan) - 1)
            label = f"<b>{d.strftime('%d.%m')}</b>" if is_last else f"<b>{cum}</b>"
            if is_last:
                ax, ay = 0, -28
            elif _near_milestone(d):
                ax, ay = 38, 22           # подпись вправо-вниз (от линии плана)
            else:
                ax, ay = -28, -38         # стандартно влево-вверх
            plan_annotations.append(dict(
                x=d, y=plan_pct[i],
                text=label, showarrow=True,
                arrowhead=2, arrowsize=1, arrowwidth=1,
                arrowcolor="#f9a825",
                ax=ax, ay=ay,
                font=dict(size=11, color="#b8860b"),
                bgcolor="rgba(255,255,255,0.85)",
                borderpad=2,
            ))
        # Подпись "425 зам." на зелёной 100%-линии у правого края
        last_date = target_plan[-1][0]
        plan_annotations.append(dict(
            x=last_date, y=100,
            text=f"<b>{sop_total} зам.</b>",
            showarrow=False,
            xanchor="right", yanchor="bottom",
            xshift=-4, yshift=4,
            font=dict(size=12, color="#27ae60"),
        ))

    # Линия тренда (линейная регрессия только по точкам >= trend_start)
    trend_df = cumulative_df.copy()
    if trend_start is not None and not trend_df.empty:
        trend_df = trend_df[pd.to_datetime(trend_df["dt"]) >= pd.Timestamp(trend_start)]
    if not trend_df.empty and len(trend_df) >= 2 and sop_total > 0:
        x_dates = pd.to_datetime(trend_df["dt"])
        x_ord = np.array([d.toordinal() for d in x_dates])
        y_pct = (trend_df["cum"] / sop_total * 100.0).to_numpy()
        slope, intercept = np.polyfit(x_ord, y_pct, 1)

        # Тренд от первой точки окна до конца графика
        end_ord = pd.Timestamp(exit_date + timedelta(days=4)).toordinal()
        trend_x_ord = np.linspace(x_ord[0], end_ord, 50)
        trend_y = slope * trend_x_ord + intercept
        trend_x = [date.fromordinal(int(o)) for o in trend_x_ord]
        fig.add_trace(go.Scatter(
            x=trend_x, y=trend_y,
            mode="lines",
            name="Тренд",
            line=dict(color="#c0392b", width=1.5, dash="dash"),
            hovertemplate="%{x|%d.%m.%Y}<br>Тренд: %{y:.1f}%%<extra></extra>",
        ))

    # Линия 100% — без подписи на самой линии (есть в легенде через невидимый трейс)
    fig.add_hline(y=100, line=dict(color="#27ae60", dash="dashdot", width=1.2))
    # Невидимый трейс для легенды "Макс. (N зам.)"
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="lines",
        line=dict(color="#27ae60", dash="dashdot", width=1.2),
        name=f"Макс. ({sop_total} зам.)",
        showlegend=True, hoverinfo="skip",
    ))

    # Вехи — маркеры + выноски (annotations)
    milestone_annotations = []
    if milestones and target_plan and sop_total > 0:
        for m_date, short, full in milestones:
            cum = _interp_cum(target_plan, m_date)
            if cum is None:
                continue
            pct = round(cum / sop_total * 100, 1)
            fig.add_trace(go.Scatter(
                x=[m_date], y=[pct],
                mode="markers",
                name=full,
                marker=dict(size=11, color="#b39ddb", symbol="diamond",
                            line=dict(color="#6a1b9a", width=1.5)),
                hovertemplate=f"{full}<extra></extra>",
            ))
            milestone_annotations.append(dict(
                x=m_date, y=pct,
                text=f"<b>{m_date.strftime('%d.%m')} {short}</b>",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1,
                arrowcolor="#6a1b9a",
                ax=0, ay=-72,
                font=dict(size=11, color="#6a1b9a"),
                bgcolor="rgba(255,255,255,0.95)",
                borderpad=3,
            ))

    fig.update_layout(
        height=460,
        margin=dict(t=30, b=60, l=60, r=30),
        xaxis=dict(title="Дата", showgrid=True, gridcolor="#eaeded",
                   tickangle=-45, tickformat="%d.%m"),
        yaxis=dict(title="Снято замечаний, %",
                   range=[0, 110], showgrid=True, gridcolor="#eaeded",
                   ticksuffix="%"),
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.04,
                    xanchor="left", x=0,
                    bgcolor="rgba(255,255,255,0)"),
        hovermode="x unified",
        annotations=fact_annotations + plan_annotations + milestone_annotations,
    )
    return fig


def _interp_cum(target_plan, target_date: date):
    """Линейная интерполяция кумулятива на точке target_date по линии плана."""
    if not target_plan:
        return None
    pts = [(d, c) for d, c, _ in target_plan]
    # Если target до 1-й точки — берём 1-ю
    if target_date <= pts[0][0]:
        return pts[0][1]
    if target_date >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        d0, c0 = pts[i - 1]
        d1, c1 = pts[i]
        if d0 <= target_date <= d1:
            span = (d1 - d0).days
            if span == 0:
                return c1
            frac = (target_date - d0).days / span
            return c0 + (c1 - c0) * frac
    return None
