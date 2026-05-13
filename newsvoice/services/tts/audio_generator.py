import hashlib
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from newsvoice.models import NewsAudio, NewsVoiceTTSSetting

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

    provider = provider or getattr(settings, "NEWSVOICE_DEFAULT_TTS_PROVIDER", NewsAudio.PROVIDER_ELEVENLABS)
    tts_setting = NewsVoiceTTSSetting.get_for_username(summary.username)
    default_voice = tts_setting.default_voice
    if provider == NewsAudio.PROVIDER_ELEVENLABS and not default_voice:
        raise TTSServiceError("ElevenLabsの音声が未設定です。高品質音声設定画面で声を選択してください。")
    voice_id = default_voice.voice_id if default_voice else ""
    voice_name = voice_name if voice_name is not None else (default_voice.name if default_voice else "")
    script_hash = build_script_hash(radio_script)

    existing = summary.audios.filter(
        username=summary.username,
        tts_provider=provider,
        voice_id=voice_id,
        model_id=tts_setting.model_id,
        output_format=tts_setting.output_format,
        script_hash=script_hash,
        status=NewsAudio.STATUS_COMPLETED,
    ).exclude(audio_file="").first()
    if existing:
        return existing, True

    audio = NewsAudio.objects.create(
        username=summary.username,
        summary=summary,
        tts_provider=provider,
        voice_name=voice_name,
        voice_id=voice_id,
        model_id=tts_setting.model_id,
        output_format=tts_setting.output_format,
        language_code=tts_setting.language_code,
        audio_format=getattr(settings, "NEWSVOICE_AUDIO_FORMAT", "mp3"),
        script_hash=script_hash,
        status=NewsAudio.STATUS_PROCESSING,
        stability=tts_setting.stability,
        similarity_boost=tts_setting.similarity_boost,
        style=tts_setting.style,
        speed=tts_setting.speed,
        use_speaker_boost=tts_setting.use_speaker_boost,
    )

    generate_audio_for_record(audio)
    return audio, False


def generate_audio_for_record(audio):
    audio.status = NewsAudio.STATUS_PROCESSING
    audio.error_message = ""
    audio.save(update_fields=["status", "error_message", "updated_at"])

    radio_script = (audio.summary.radio_script or "").strip()
    logger.info(
        "NewsVoice high quality audio generation started article_id=%s provider=%s audio_id=%s",
        audio.summary.article_id,
        audio.tts_provider,
        audio.id,
    )
    try:
        service = get_tts_service(audio.tts_provider)
        generated = service.synthesize(
            radio_script,
            voice_id=audio.voice_id,
            voice_name=audio.voice_name,
            model_id=audio.model_id,
            output_format=audio.output_format,
            language_code=audio.language_code,
            stability=audio.stability,
            similarity_boost=audio.similarity_boost,
            style=audio.style,
            speed=audio.speed,
            use_speaker_boost=audio.use_speaker_boost,
        )
        if isinstance(generated, bytes):
            filename = f"article-{audio.summary.article_id}-audio-{audio.id}.{audio.audio_format}"
            audio.audio_file.save(filename, ContentFile(generated), save=False)
    except Exception as exc:
        audio.status = NewsAudio.STATUS_FAILED
        audio.error_message = str(exc)
        audio.save(update_fields=["status", "error_message", "updated_at"])
        logger.exception(
            "NewsVoice audio generation failed article_id=%s provider=%s audio_id=%s",
            audio.summary.article_id,
            audio.tts_provider,
            audio.id,
        )
        raise TTSServiceError(str(exc)) from exc

    audio.status = NewsAudio.STATUS_COMPLETED
    audio.generated_at = timezone.now()
    audio.save(update_fields=["audio_file", "status", "generated_at", "updated_at"])
    logger.info(
        "NewsVoice high quality audio generation completed article_id=%s provider=%s audio_id=%s",
        audio.summary.article_id,
        audio.tts_provider,
        audio.id,
    )
    return audio
