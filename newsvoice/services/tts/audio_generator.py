import hashlib
import logging

from django.conf import settings

from newsvoice.models import NewsAudio

from .base import TTSServiceError
from .factory import get_tts_service

logger = logging.getLogger(__name__)


def build_script_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_latest_completed_audio(summary):
    return summary.audios.filter(status=NewsAudio.STATUS_COMPLETED).exclude(audio_file="").first()


def generate_high_quality_audio(summary, provider=None, voice_name=None):
    if not getattr(settings, "NEWSVOICE_HIGH_QUALITY_TTS_ENABLED", False):
        raise TTSServiceError("高品質音声生成は現在未対応です。")

    radio_script = (summary.radio_script or "").strip()
    if not radio_script:
        raise TTSServiceError("ラジオ原稿が空のため、音声を生成できません。")

    max_length = getattr(settings, "NEWSVOICE_TTS_MAX_TEXT_LENGTH", 1200)
    if len(radio_script) > max_length:
        raise TTSServiceError(f"ラジオ原稿が長すぎます。{max_length}文字以内にしてください。")

    provider = provider or getattr(settings, "NEWSVOICE_DEFAULT_TTS_PROVIDER", "voicevox")
    voice_name = voice_name if voice_name is not None else getattr(settings, "NEWSVOICE_DEFAULT_VOICE_NAME", "")
    script_hash = build_script_hash(radio_script)

    existing = summary.audios.filter(
        tts_provider=provider,
        voice_name=voice_name,
        script_hash=script_hash,
        status=NewsAudio.STATUS_COMPLETED,
    ).exclude(audio_file="").first()
    if existing:
        return existing, True

    audio = NewsAudio.objects.create(
        summary=summary,
        tts_provider=provider,
        voice_name=voice_name,
        audio_format=getattr(settings, "NEWSVOICE_AUDIO_FORMAT", "mp3"),
        script_hash=script_hash,
        status=NewsAudio.STATUS_PROCESSING,
    )

    logger.info(
        "NewsVoice high quality audio generation started article_id=%s provider=%s",
        summary.article_id,
        provider,
    )

    try:
        service = get_tts_service(provider)
        service.synthesize(radio_script, voice_name=voice_name)
    except Exception as exc:
        audio.status = NewsAudio.STATUS_FAILED
        audio.error_message = str(exc)
        audio.save(update_fields=["status", "error_message", "updated_at"])
        logger.exception(
            "NewsVoice audio generation failed article_id=%s provider=%s",
            summary.article_id,
            provider,
        )
        raise TTSServiceError(str(exc)) from exc

    return audio, False
