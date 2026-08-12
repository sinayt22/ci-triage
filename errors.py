class ClassificationParseError(Exception):
    def __init__(self, raw_response:str, reason:str):
        self.raw_response = raw_response,
        self.reason = reason
        super().__init__(f"{reason}: {raw_response!r}")