class TTSServiceError(Exception):
    pass


class BaseTTSService:
    def synthesize(self, text, **kwargs):
        raise NotImplementedError
