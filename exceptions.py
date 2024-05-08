class TokensError(Exception):
    """Отсутствуют обязательные переменные окружения."""

    pass


class HomeworkStatusError(Exception):
    """Неизвестный статус домашней работы."""

    pass
