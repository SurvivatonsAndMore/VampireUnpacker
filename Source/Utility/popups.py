class BasePopup(Exception):
    __match_args__ = ("title", "message")

    def __init__(self, title, message, *args):
        super().__init__(title, message, *args)
        self.title: str = title
        self.message: str = message


class InfoPopup(BasePopup):
    def __init__(self, title, message, *args):
        super().__init__(title, message, *args)


class WarningPopup(BasePopup):
    def __init__(self, title, message, *args):
        super().__init__(title, message, *args)


class ErrorPopup(BasePopup):
    def __init__(self, title, message, *args):
        super().__init__(title, message, *args)
