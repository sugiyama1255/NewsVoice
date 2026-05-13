from django.conf import settings
from django.db import models

from .services.totp import generate_totp_secret


def generate_two_factor_code():
    return "000000"


class UserTwoFactorCode(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="newsvoice_2fa")
    username = models.CharField(max_length=150, blank=True, default="", db_index=True)
    secret = models.CharField(max_length=64, default=generate_totp_secret)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User two-factor code"
        verbose_name_plural = "User two-factor codes"

    def rotate(self):
        self.secret = generate_totp_secret()
        self.save(update_fields=["secret", "updated_at"])
        return self.secret

    def __str__(self):
        return f"{self.user} 2FA"


class NewsArticle(models.Model):
    username = models.CharField(max_length=150, default="", db_index=True)
    title = models.CharField(max_length=500)
    title_ja = models.CharField(max_length=500, blank=True)
    url = models.URLField()
    source_name = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    language = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=20, blank=True)
    category = models.CharField(max_length=50, blank=True)
    keyword = models.CharField(max_length=255, blank=True)
    gdelt_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["username", "url"], name="newsvoice_article_username_url_uniq"),
        ]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title_ja or self.title


class NewsSummary(models.Model):
    IMPACT_POSITIVE = "positive"
    IMPACT_NEGATIVE = "negative"
    IMPACT_NEUTRAL = "neutral"
    IMPACT_MIXED = "mixed"
    IMPACT_UNKNOWN = "unknown"
    IMPACT_CHOICES = [
        (IMPACT_POSITIVE, "Positive"),
        (IMPACT_NEGATIVE, "Negative"),
        (IMPACT_NEUTRAL, "Neutral"),
        (IMPACT_MIXED, "Mixed"),
        (IMPACT_UNKNOWN, "Unknown"),
    ]

    username = models.CharField(max_length=150, default="", db_index=True)
    article = models.OneToOneField(NewsArticle, on_delete=models.CASCADE, related_name="summary")
    summary_text = models.TextField(blank=True)
    radio_script = models.TextField(blank=True)
    ai_opinion = models.TextField(blank=True)
    impact_label = models.CharField(max_length=20, choices=IMPACT_CHOICES, default=IMPACT_UNKNOWN)
    model_name = models.CharField(max_length=100, blank=True)
    prompt_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Summary: {self.article.title}"


class NewsAudio(models.Model):
    PROVIDER_ELEVENLABS = "elevenlabs"
    PROVIDER_OPENAI = "openai"
    PROVIDER_GOOGLE = "google"
    PROVIDER_VOICEVOX = "voicevox"
    PROVIDER_OTHER = "other"
    PROVIDER_CHOICES = [
        (PROVIDER_ELEVENLABS, "ElevenLabs"),
        (PROVIDER_OPENAI, "OpenAI TTS"),
        (PROVIDER_GOOGLE, "Google Cloud TTS"),
        (PROVIDER_VOICEVOX, "VOICEVOX"),
        (PROVIDER_OTHER, "Other"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    username = models.CharField(max_length=150, default="", db_index=True)
    summary = models.ForeignKey(NewsSummary, on_delete=models.CASCADE, related_name="audios")
    tts_provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    voice_name = models.CharField(max_length=100, blank=True)
    voice_id = models.CharField(max_length=100, blank=True)
    model_id = models.CharField(max_length=100, default="eleven_multilingual_v2")
    output_format = models.CharField(max_length=50, default="mp3_44100_128")
    language_code = models.CharField(max_length=10, default="ja")
    audio_file = models.FileField(upload_to="newsvoice/audio/", blank=True)
    audio_format = models.CharField(max_length=20, default="mp3")
    script_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    stability = models.FloatField(default=0.45)
    similarity_boost = models.FloatField(default=0.75)
    style = models.FloatField(default=0.20)
    speed = models.FloatField(default=0.95)
    use_speaker_boost = models.BooleanField(default=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["username", "status", "updated_at"]),
            models.Index(fields=["username", "tts_provider", "voice_id", "model_id", "output_format", "script_hash"]),
            models.Index(fields=["tts_provider", "voice_name", "script_hash"]),
        ]

    def __str__(self):
        return f"{self.summary.article.display_title} ({self.tts_provider})"


class ElevenLabsVoice(models.Model):
    username = models.CharField(max_length=150, default="", db_index=True)
    voice_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    preview_url = models.URLField(blank=True)
    labels = models.JSONField(default=dict, blank=True)
    samples = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["username", "voice_id"], name="newsvoice_eleven_voice_user_voice_uniq"),
        ]

    def __str__(self):
        return self.name


class NewsVoiceTTSSetting(models.Model):
    username = models.CharField(max_length=150, unique=True, db_index=True)
    provider = models.CharField(max_length=50, default=NewsAudio.PROVIDER_ELEVENLABS)
    default_voice = models.ForeignKey(ElevenLabsVoice, null=True, blank=True, on_delete=models.SET_NULL)
    model_id = models.CharField(max_length=100, default="eleven_multilingual_v2")
    output_format = models.CharField(max_length=50, default="mp3_44100_128")
    language_code = models.CharField(max_length=10, default="ja")
    stability = models.FloatField(default=0.45)
    similarity_boost = models.FloatField(default=0.75)
    style = models.FloatField(default=0.20)
    speed = models.FloatField(default=0.95)
    use_speaker_boost = models.BooleanField(default=True)
    attribution_text = models.CharField(max_length=255, default="Voice generated with ElevenLabs.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_for_username(cls, username):
        from django.conf import settings

        obj, _ = cls.objects.get_or_create(
            username=username,
            defaults={
                "model_id": settings.ELEVENLABS_DEFAULT_MODEL_ID,
                "output_format": settings.ELEVENLABS_DEFAULT_OUTPUT_FORMAT,
                "language_code": settings.ELEVENLABS_DEFAULT_LANGUAGE_CODE,
                "stability": settings.ELEVENLABS_DEFAULT_STABILITY,
                "similarity_boost": settings.ELEVENLABS_DEFAULT_SIMILARITY_BOOST,
                "style": settings.ELEVENLABS_DEFAULT_STYLE,
                "speed": settings.ELEVENLABS_DEFAULT_SPEED,
                "use_speaker_boost": settings.ELEVENLABS_DEFAULT_USE_SPEAKER_BOOST,
                "attribution_text": settings.ELEVENLABS_ATTRIBUTION_TEXT,
            },
        )
        return obj

    def __str__(self):
        return f"{self.username} TTS setting"


class ProcessingJob(models.Model):
    TYPE_SUMMARY = "summary"
    TYPE_AUDIO = "audio"
    TYPE_NEWS_FETCH = "news_fetch"
    TYPE_CHOICES = [
        (TYPE_SUMMARY, "Summary"),
        (TYPE_AUDIO, "Audio"),
        (TYPE_NEWS_FETCH, "News Fetch"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    username = models.CharField(max_length=150, default="", db_index=True)
    job_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="processing_jobs")
    audio = models.ForeignKey(NewsAudio, on_delete=models.SET_NULL, null=True, blank=True, related_name="processing_jobs")
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["username", "status", "job_type", "created_at"]),
            models.Index(fields=["status", "job_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.job_type}:{self.status} article={self.article_id}"
