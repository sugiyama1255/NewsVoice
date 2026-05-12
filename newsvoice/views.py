import logging
import time

from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import NewsSearchForm
from .models import NewsArticle
from .services.gdelt_client import GdeltClientError, fetch_and_store_articles
from .services.gemini_client import GeminiClientError, generate_radio_summary
from .services.tts.audio_generator import generate_high_quality_audio, get_latest_completed_audio
from .services.tts.base import TTSServiceError


logger = logging.getLogger(__name__)


def index(request):
    form = NewsSearchForm(request.GET or None)
    search_results = None
    saved_articles = NewsArticle.objects.select_related("summary").all()[:20]

    if request.GET and form.is_valid():
        started_at = time.monotonic()
        logger.info(
            "ニュース取得 全体開始 category=%s keyword=%r max_records=%s timespan=%s language=%s",
            form.cleaned_data["category"],
            form.cleaned_data["keyword"],
            form.cleaned_data["max_records"],
            form.cleaned_data["timespan"],
            form.cleaned_data["language"],
        )
        try:
            search_results = fetch_and_store_articles(
                category=form.cleaned_data["category"],
                keyword=form.cleaned_data["keyword"],
                max_records=form.cleaned_data["max_records"],
                timespan=form.cleaned_data["timespan"],
                language=form.cleaned_data["language"],
            )
            saved_articles = NewsArticle.objects.select_related("summary").all()[:20]
            elapsed = time.monotonic() - started_at
            logger.info(
                "ニュース取得 全体完了 count=%s elapsed=%.3fs",
                len(search_results),
                elapsed,
            )
            messages.success(request, f"{len(search_results)}件のニュースを取得しました。（{elapsed:.1f}秒）")
        except GdeltClientError as exc:
            logger.exception("ニュース取得 全体失敗 elapsed=%.3fs", time.monotonic() - started_at)
            messages.error(request, str(exc))

    return render(
        request,
        "newsvoice/index.html",
        {
            "form": form,
            "search_results": search_results,
            "saved_articles": saved_articles,
        },
    )


def detail(request, article_id):
    article = get_object_or_404(NewsArticle.objects.select_related("summary"), pk=article_id)
    latest_audio = None
    if hasattr(article, "summary"):
        latest_audio = get_latest_completed_audio(article.summary)
    return render(
        request,
        "newsvoice/detail.html",
        {
            "article": article,
            "latest_audio": latest_audio,
            "high_quality_tts_enabled": settings.NEWSVOICE_HIGH_QUALITY_TTS_ENABLED,
        },
    )


@require_POST
def generate_summary(request, article_id):
    article = get_object_or_404(NewsArticle, pk=article_id)
    try:
        generate_radio_summary(article)
        messages.success(request, "ラジオ原稿を生成しました。")
    except GeminiClientError as exc:
        messages.error(request, str(exc))
    return redirect("newsvoice:detail", article_id=article.id)


@require_POST
def delete_article(request, article_id):
    article = get_object_or_404(NewsArticle, pk=article_id)
    title = article.display_title
    article.delete()
    messages.success(request, f"ニュースを削除しました: {title}")
    return redirect("newsvoice:index")


@require_POST
def generate_audio(request, article_id):
    article = get_object_or_404(NewsArticle.objects.select_related("summary"), pk=article_id)
    if not hasattr(article, "summary"):
        return JsonResponse({"status": "failed", "error": "先にラジオ原稿を作成してください。"}, status=400)

    provider = request.POST.get("provider") or settings.NEWSVOICE_DEFAULT_TTS_PROVIDER
    voice_name = request.POST.get("voice_name", settings.NEWSVOICE_DEFAULT_VOICE_NAME)
    try:
        audio, reused = generate_high_quality_audio(article.summary, provider=provider, voice_name=voice_name)
    except TTSServiceError as exc:
        return JsonResponse({"status": "failed", "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "status": audio.status,
            "audio_url": audio.audio_file.url if audio.audio_file else "",
            "provider": audio.tts_provider,
            "reused": reused,
        }
    )
