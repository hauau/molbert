class ImageValidationException(Exception):
    def __init__(self, type: str, info: str):
        self.type = type
        self.info = info