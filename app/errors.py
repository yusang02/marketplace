class AppError(Exception):
    """Any API error we raise on purpose."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message