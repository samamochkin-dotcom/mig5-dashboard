"""Анонимизация ФИО: 'Иванов Иван Иванович' → 'Иванов И.И.'"""

import re


def short_fio(full_name: str) -> str:
    """Преобразует полное ФИО в фамилию + инициалы.

    'Иванов Иван Иванович'  → 'Иванов И.И.'
    'Иванов И.И.'           → 'Иванов И.И.'  (уже сокращённое)
    'Иванов'                → 'Иванов'
    ''                      → ''
    """
    if not full_name or not isinstance(full_name, str):
        return ""
    s = full_name.strip()
    if not s:
        return ""

    # Уже сокращённое (содержит точки в инициалах)
    if re.search(r"\b[А-ЯA-Z]\.\s*[А-ЯA-Z]?\.?", s):
        return s

    parts = s.split()
    if len(parts) == 1:
        return parts[0]
    surname = parts[0]
    initials = ".".join(p[0].upper() for p in parts[1:] if p) + "."
    return f"{surname} {initials}"
