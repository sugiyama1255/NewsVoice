from .base import TTSServiceError
from .elevenlabs_tts import ElevenLabsTTSService


class UnimplementedTTSService:
    def __init__(self, provider):
        self.provider = provider

    def synthesize(self, text, **kwargs):
        raise TTSServiceError(f"{self.provider} の高品質音声生成はまだ未対応です。")


def get_tts_service(provider):
    if provider == "elevenlabs":
        return ElevenLabsTTSService()
    if provider in {"openai", "google", "voicevox", "other"}:
        return UnimplementedTTSService(provider)
    raise TTSServiceError(f"未対応のTTSプロバイダです: {provider}")
