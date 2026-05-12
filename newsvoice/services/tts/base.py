class TTSServiceError(Exception):
    pass


class BaseTTSService:
    def synthesize(self, text, voice_name=None):
        raise NotImplementedError
