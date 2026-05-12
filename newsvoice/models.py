from django.db import models


class NewsArticle(models.Model):
    title = models.CharField(max_length=500)
    title_ja = models.CharField(max_length=500, blank=True)
    url = models.URLField(unique=True)
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
    PROVIDER_OPENAI = "openai"
    PROVIDER_GOOGLE = "google"
    PROVIDER_VOICEVOX = "voicevox"
    PROVIDER_OTHER = "other"
    PROVIDER_CHOICES = [
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

    summary = models.ForeignKey(NewsSummary, on_delete=models.CASCADE, related_name="audios")
    tts_provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    voice_name = models.CharField(max_length=100, blank=True)
    audio_file = models.FileField(upload_to="newsvoice/audio/", blank=True)
    audio_format = models.CharField(max_length=20, default="mp3")
    script_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["tts_provider", "voice_name", "script_hash"]),
        ]

    def __str__(self):
        return f"{self.summary.article.display_title} ({self.tts_provider})"
