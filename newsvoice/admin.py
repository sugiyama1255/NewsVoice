from django.contrib import admin

from .models import ElevenLabsVoice, NewsArticle, NewsAudio, NewsSummary, NewsVoiceTTSSetting, UserTwoFactorCode


@admin.register(UserTwoFactorCode)
class UserTwoFactorCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "username", "updated_at")
    search_fields = ("user__username", "username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("display_title", "username", "source_name", "published_at", "category", "created_at")
    search_fields = ("username", "title", "title_ja", "source_name", "url", "keyword")
    list_filter = ("username", "category", "language", "country")


@admin.register(NewsSummary)
class NewsSummaryAdmin(admin.ModelAdmin):
    list_display = ("article", "username", "impact_label", "model_name", "updated_at")
    search_fields = ("username", "article__title", "summary_text", "radio_script", "ai_opinion")
    list_filter = ("username", "impact_label", "model_name")


@admin.register(NewsAudio)
class NewsAudioAdmin(admin.ModelAdmin):
    list_display = ("article_title", "username", "tts_provider", "voice_name", "model_id", "status", "generated_at", "updated_at")
    search_fields = (
        "username",
        "summary__article__title",
        "summary__article__title_ja",
        "voice_name",
        "voice_id",
        "error_message",
    )
    list_filter = ("username", "tts_provider", "status", "audio_format")
    readonly_fields = ("script_hash", "generated_at", "created_at", "updated_at")

    def article_title(self, obj):
        return obj.summary.article.display_title


@admin.register(ElevenLabsVoice)
class ElevenLabsVoiceAdmin(admin.ModelAdmin):
    list_display = ("name", "username", "category", "is_default", "is_active", "fetched_at")
    search_fields = ("username", "name", "voice_id", "category")
    list_filter = ("username", "category", "is_default", "is_active")


@admin.register(NewsVoiceTTSSetting)
class NewsVoiceTTSSettingAdmin(admin.ModelAdmin):
    list_display = ("username", "provider", "default_voice", "model_id", "language_code", "updated_at")
    search_fields = ("username", "provider", "model_id")
    list_filter = ("provider", "language_code")
