import logging
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from newsvoice.models import NewsArticle, NewsAudio, NewsVoiceTTSSetting, ProcessingJob
from newsvoice.services.gdelt_client import GdeltClientError, fetch_and_store_articles
from newsvoice.services.gemini_client import GeminiClientError, generate_radio_summary
from newsvoice.services.tts.audio_generator import build_script_hash, generate_audio_for_record
from newsvoice.services.tts.base import TTSServiceError


logger = logging.getLogger(__name__)


def enqueue_summary_job(article):
    return ProcessingJob.objects.create(
        username=article.username,
        job_type=ProcessingJob.TYPE_SUMMARY,
        article=article,
    )


def enqueue_news_fetch_job(search_params):
    username = search_params["username"]
    reusable_statuses = [
        ProcessingJob.STATUS_QUEUED,
        ProcessingJob.STATUS_PROCESSING,
    ]
    existing_job = (
        ProcessingJob.objects.filter(
            username=username,
            job_type=ProcessingJob.TYPE_NEWS_FETCH,
            status__in=reusable_statuses,
        )
        .order_by("-created_at")
        .first()
    )
    if existing_job and existing_job.payload == search_params:
        logger.info("ニュース取得ジョブ 重複受付 job_id=%s params=%s", existing_job.id, search_params)
        return existing_job

    job_article = NewsArticle.objects.create(
        username=username,
        title="ニュース取得ジョブ",
        url=f"https://newsvoice.local/jobs/{uuid4()}",
        source_name="NewsVoice Job",
    )
    return ProcessingJob.objects.create(
        username=username,
        job_type=ProcessingJob.TYPE_NEWS_FETCH,
        article=job_article,
        payload=search_params,
    )


def enqueue_audio_job(article, provider=None, voice_name=None):
    if not hasattr(article, "summary"):
        raise TTSServiceError("先にラジオ原稿を作成してください。")
    if not getattr(settings, "NEWSVOICE_HIGH_QUALITY_TTS_ENABLED", False):
        raise TTSServiceError("高品質音声生成は現在未対応です。")

    radio_script = (article.summary.radio_script or "").strip()
    if not radio_script:
        raise TTSServiceError("ラジオ原稿が空のため、音声を生成できません。")

    provider = provider or getattr(settings, "NEWSVOICE_DEFAULT_TTS_PROVIDER", NewsAudio.PROVIDER_ELEVENLABS)
    max_length = (
        getattr(settings, "ELEVENLABS_MAX_TEXT_LENGTH", 1200)
        if provider == NewsAudio.PROVIDER_ELEVENLABS
        else getattr(settings, "NEWSVOICE_TTS_MAX_TEXT_LENGTH", 1200)
    )
    if len(radio_script) > max_length:
        raise TTSServiceError(f"ラジオ原稿が長すぎます。{max_length}文字以内にしてください。")

    tts_setting = NewsVoiceTTSSetting.get_for_username(article.username)
    default_voice = tts_setting.default_voice
    if provider == NewsAudio.PROVIDER_ELEVENLABS and not default_voice:
        raise TTSServiceError("ElevenLabsの音声が未設定です。高品質音声設定画面で声一覧を更新し、使用する声を選択してください。")

    voice_id = default_voice.voice_id if default_voice else ""
    voice_name = voice_name if voice_name is not None else (default_voice.name if default_voice else "")
    model_id = tts_setting.model_id
    output_format = tts_setting.output_format
    script_hash = build_script_hash(radio_script)

    existing = article.summary.audios.filter(
        username=article.username,
        tts_provider=provider,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
        script_hash=script_hash,
        status=NewsAudio.STATUS_COMPLETED,
    ).exclude(audio_file="").first()
    if existing:
        return None, existing, True

    audio = NewsAudio.objects.create(
        username=article.username,
        summary=article.summary,
        tts_provider=provider,
        voice_name=voice_name,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
        language_code=tts_setting.language_code,
        audio_format=getattr(settings, "NEWSVOICE_AUDIO_FORMAT", "mp3"),
        script_hash=script_hash,
        status=NewsAudio.STATUS_PENDING,
        stability=tts_setting.stability,
        similarity_boost=tts_setting.similarity_boost,
        style=tts_setting.style,
        speed=tts_setting.speed,
        use_speaker_boost=tts_setting.use_speaker_boost,
    )
    job = ProcessingJob.objects.create(
        username=article.username,
        job_type=ProcessingJob.TYPE_AUDIO,
        article=article,
        audio=audio,
        payload={
            "provider": provider,
            "voice_id": voice_id,
            "voice_name": voice_name,
            "model_id": model_id,
            "output_format": output_format,
        },
    )
    return job, audio, False


def claim_next_job():
    with transaction.atomic():
        job = (
            ProcessingJob.objects.select_for_update()
            .filter(status=ProcessingJob.STATUS_QUEUED)
            .order_by("created_at")
            .first()
        )
        if not job:
            return None
        job.status = ProcessingJob.STATUS_PROCESSING
        job.started_at = timezone.now()
        job.error_message = ""
        job.save(update_fields=["status", "started_at", "error_message", "updated_at"])
        return job


def process_job(job):
    logger.info("Processing job started id=%s type=%s article_id=%s", job.id, job.job_type, job.article_id)
    try:
        if job.job_type == ProcessingJob.TYPE_NEWS_FETCH:
            articles = fetch_and_store_articles(**job.payload)
            result = {
                "count": len(articles),
                "article_ids": [article.id for article in articles],
            }
        elif job.job_type == ProcessingJob.TYPE_SUMMARY:
            summary = generate_radio_summary(NewsArticle.objects.get(pk=job.article_id, username=job.username))
            result = {
                "article_id": job.article_id,
                "summary_id": summary.id,
                "detail_url": summary.article.get_absolute_url() if hasattr(summary.article, "get_absolute_url") else "",
            }
        elif job.job_type == ProcessingJob.TYPE_AUDIO:
            audio = NewsAudio.objects.select_related("summary").get(pk=job.audio_id)
            generate_audio_for_record(audio)
            result = {
                "article_id": job.article_id,
                "audio_id": audio.id,
                "audio_url": audio.audio_file.url if audio.audio_file else "",
                "provider": audio.tts_provider,
            }
        else:
            raise ValueError(f"Unsupported job type: {job.job_type}")
    except (GdeltClientError, GeminiClientError, TTSServiceError, Exception) as exc:
        job.status = ProcessingJob.STATUS_FAILED
        job.error_message = str(exc)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
        logger.exception("Processing job failed id=%s type=%s", job.id, job.job_type)
        return job

    job.status = ProcessingJob.STATUS_COMPLETED
    job.result = result
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "result", "completed_at", "updated_at"])
    logger.info("Processing job completed id=%s type=%s", job.id, job.job_type)
    return job
