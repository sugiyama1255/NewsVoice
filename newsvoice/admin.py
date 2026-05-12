from django.contrib import admin

from .models import NewsArticle, NewsAudio, NewsSummary


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("display_title", "source_name", "published_at", "category", "created_at")
    search_fields = ("title", "title_ja", "source_name", "url", "keyword")
    list_filter = ("category", "language", "country")


@admin.register(NewsSummary)
class NewsSummaryAdmin(admin.ModelAdmin):
    list_display = ("article", "impact_label", "model_name", "updated_at")
    search_fields = ("article__title", "summary_text", "radio_script", "ai_opinion")
    list_filter = ("impact_label", "model_name")


@admin.register(NewsAudio)
class NewsAudioAdmin(admin.ModelAdmin):
    list_display = ("article_title", "tts_provider", "voice_name", "status", "generated_at", "updated_at")
    search_fields = ("summary__article__title", "summary__article__title_ja", "voice_name", "error_message")
    list_filter = ("tts_provider", "status", "audio_format")
    readonly_fields = ("script_hash", "generated_at", "created_at", "updated_at")

    def article_title(self, obj):
        return obj.summary.article.display_title
