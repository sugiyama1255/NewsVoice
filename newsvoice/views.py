import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, NewsSearchForm, TwoFactorCodeForm
from .models import ElevenLabsVoice, NewsArticle, NewsVoiceTTSSetting, ProcessingJob, UserTwoFactorCode
from .services.jobs import enqueue_audio_job, enqueue_news_fetch_job, enqueue_summary_job
from .services.totp import build_user_qr_data_uri, verify_totp
from .services.tts.elevenlabs_tts import refresh_elevenlabs_voices
from .services.tts.audio_generator import get_latest_completed_audio
from .services.tts.base import TTSServiceError


logger = logging.getLogger(__name__)
PENDING_2FA_USER_ID_SESSION_KEY = "newsvoice_pending_2fa_user_id"
PENDING_2FA_NEXT_SESSION_KEY = "newsvoice_pending_2fa_next"


def safe_redirect_target(request, target):
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return reverse("newsvoice:index")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("newsvoice:index")

    next_url = safe_redirect_target(request, request.GET.get("next"))
    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if user is not None:
            request.session[PENDING_2FA_USER_ID_SESSION_KEY] = user.id
            request.session[PENDING_2FA_NEXT_SESSION_KEY] = safe_redirect_target(
                request,
                request.POST.get("next"),
            )
            return redirect("newsvoice:two_factor")
        form.add_error(None, "ユーザー名またはパスワードが正しくありません。")

    return render(
        request,
        "newsvoice/login.html",
        {
            "form": form,
            "next": next_url,
        },
    )


def two_factor_view(request):
    from django.contrib.auth import get_user_model

    pending_user_id = request.session.get(PENDING_2FA_USER_ID_SESSION_KEY)
    if not pending_user_id:
        return redirect("newsvoice:login")

    user = get_object_or_404(get_user_model(), pk=pending_user_id)
    user_code, created = UserTwoFactorCode.objects.get_or_create(
        user=user,
        defaults={"username": user.get_username()},
    )
    if not created and user_code.username != user.get_username():
        user_code.username = user.get_username()
        user_code.save(update_fields=["username", "updated_at"])
    form = TwoFactorCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if verify_totp(user_code.secret, form.cleaned_data["code"]):
            login(request, user)
            next_url = request.session.pop(PENDING_2FA_NEXT_SESSION_KEY, None)
            request.session.pop(PENDING_2FA_USER_ID_SESSION_KEY, None)
            return redirect(safe_redirect_target(request, next_url))
        form.add_error("code", "認証コードが正しくありません。")

    return render(
        request,
        "newsvoice/two_factor.html",
        {
            "form": form,
            "qr_data_uri": build_user_qr_data_uri(user, user_code.secret),
            "manual_secret": user_code.secret,
        },
    )


def logout_view(request):
    logout(request)
    messages.success(request, "ログアウトしました。")
    return redirect("newsvoice:login")


@login_required
def settings_view(request):
    username = request.user.get_username()
    user_code, created = UserTwoFactorCode.objects.get_or_create(
        user=request.user,
        defaults={"username": username},
    )
    if not created and user_code.username != username:
        user_code.username = username
        user_code.save(update_fields=["username", "updated_at"])
    if request.method == "POST":
        user_code.rotate()
        messages.success(request, "2段階認証コードを再発行しました。")
        return redirect("newsvoice:settings")

    return render(
        request,
        "newsvoice/settings.html",
        {
            "qr_data_uri": build_user_qr_data_uri(request.user, user_code.secret),
            "manual_secret": user_code.secret,
        },
    )


@login_required
def tts_settings(request):
    username = request.user.get_username()
    tts_setting = NewsVoiceTTSSetting.get_for_username(username)
    voices = ElevenLabsVoice.objects.filter(username=username, is_active=True).order_by("name")
    return render(
        request,
        "newsvoice/tts_settings.html",
        {
            "tts_setting": tts_setting,
            "voices": voices,
            "api_configured": bool(settings.ELEVENLABS_API_KEY),
            "high_quality_tts_enabled": settings.NEWSVOICE_HIGH_QUALITY_TTS_ENABLED,
        },
    )


@require_POST
@login_required
def refresh_elevenlabs_voices_view(request):
    try:
        count = refresh_elevenlabs_voices(request.user.get_username())
    except TTSServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"声一覧を更新しました。{count}件取得しました。")
    return redirect("newsvoice:tts_settings")


@require_POST
@login_required
def set_default_voice(request, voice_id):
    username = request.user.get_username()
    voice = get_object_or_404(ElevenLabsVoice, username=username, voice_id=voice_id, is_active=True)
    tts_setting = NewsVoiceTTSSetting.get_for_username(username)
    ElevenLabsVoice.objects.filter(username=username, is_default=True).exclude(pk=voice.pk).update(is_default=False)
    voice.is_default = True
    voice.save(update_fields=["is_default", "updated_at"])
    tts_setting.default_voice = voice
    tts_setting.save(update_fields=["default_voice", "updated_at"])
    messages.success(request, f"高品質音声の既定音声を {voice.name} にしました。")
    return redirect("newsvoice:tts_settings")


@login_required
def index(request):
    username = request.user.get_username()
    form = NewsSearchForm(request.GET or None)
    search_results = None
    saved_articles = (
        NewsArticle.objects.select_related("summary")
        .filter(username=username)
        .exclude(source_name="NewsVoice Job")[:20]
    )
    recent_jobs = (
        ProcessingJob.objects.select_related("article", "audio")
        .filter(username=username)
        .order_by("-created_at")[:20]
    )
    pending_audio_jobs = (
        ProcessingJob.objects.filter(
            username=username,
            job_type=ProcessingJob.TYPE_AUDIO,
            status__in=[ProcessingJob.STATUS_QUEUED, ProcessingJob.STATUS_PROCESSING],
        )
        .order_by("-created_at")
    )
    pending_audio_job_by_article = {job.article_id: job for job in pending_audio_jobs}

    if request.GET and form.is_valid():
        job = enqueue_news_fetch_job(
            {
                "username": username,
                "category": form.cleaned_data["category"],
                "keyword": form.cleaned_data["keyword"],
                "max_records": form.cleaned_data["max_records"],
                "timespan": form.cleaned_data["timespan"],
                "language": form.cleaned_data["language"],
            }
        )
        logger.info("ニュース取得ジョブ 受付 job_id=%s params=%s", job.id, job.payload)
        messages.success(request, f"ニュース取得を受け付けました。ジョブID: {job.id}")
        return redirect("newsvoice:index")

    return render(
        request,
        "newsvoice/index.html",
        {
            "form": form,
            "search_results": search_results,
            "saved_articles": saved_articles,
            "recent_jobs": recent_jobs,
            "pending_audio_job_by_article": pending_audio_job_by_article,
            "high_quality_tts_enabled": settings.NEWSVOICE_HIGH_QUALITY_TTS_ENABLED,
        },
    )


@login_required
def detail(request, article_id):
    username = request.user.get_username()
    article = get_object_or_404(
        NewsArticle.objects.select_related("summary"),
        pk=article_id,
        username=username,
    )
    latest_audio = None
    pending_audio_job = (
        ProcessingJob.objects.filter(
            username=username,
            article=article,
            job_type=ProcessingJob.TYPE_AUDIO,
            status__in=[ProcessingJob.STATUS_QUEUED, ProcessingJob.STATUS_PROCESSING],
        )
        .order_by("-created_at")
        .first()
    )
    tts_setting = NewsVoiceTTSSetting.get_for_username(username)
    if hasattr(article, "summary"):
        latest_audio = get_latest_completed_audio(article.summary)
    return render(
        request,
        "newsvoice/detail.html",
        {
            "article": article,
            "latest_audio": latest_audio,
            "pending_audio_job": pending_audio_job,
            "high_quality_tts_enabled": settings.NEWSVOICE_HIGH_QUALITY_TTS_ENABLED,
            "tts_setting": tts_setting,
        },
    )


@require_POST
@login_required
def generate_summary(request, article_id):
    article = get_object_or_404(NewsArticle, pk=article_id, username=request.user.get_username())
    job = enqueue_summary_job(article)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "status": job.status,
                "job_id": job.id,
                "job_url": request.build_absolute_uri(job_status_url(job.id)),
                "message": "ラジオ原稿の生成を受け付けました。",
            },
            status=202,
        )
    messages.success(request, "ラジオ原稿の生成を受け付けました。少し待ってから画面を更新してください。")
    return redirect("newsvoice:detail", article_id=article.id)


@require_POST
@login_required
def delete_article(request, article_id):
    article = get_object_or_404(NewsArticle, pk=article_id, username=request.user.get_username())
    title = article.display_title
    article.delete()
    messages.success(request, f"ニュースを削除しました: {title}")
    return redirect("newsvoice:index")


@require_POST
@login_required
def generate_audio(request, article_id):
    article = get_object_or_404(
        NewsArticle.objects.select_related("summary"),
        pk=article_id,
        username=request.user.get_username(),
    )
    provider = request.POST.get("provider") or settings.NEWSVOICE_DEFAULT_TTS_PROVIDER
    voice_name = request.POST.get("voice_name", settings.NEWSVOICE_DEFAULT_VOICE_NAME)
    try:
        job, audio, reused = enqueue_audio_job(article, provider=provider, voice_name=voice_name)
    except TTSServiceError as exc:
        return JsonResponse({"status": "failed", "error": str(exc)}, status=400)

    if reused:
        return JsonResponse(
            {
                "status": audio.status,
                "audio_url": audio.audio_file.url if audio.audio_file else "",
                "provider": audio.tts_provider,
                "reused": True,
            }
        )

    return JsonResponse(
        {
            "status": job.status,
            "job_id": job.id,
            "job_url": request.build_absolute_uri(job_status_url(job.id)),
            "provider": audio.tts_provider,
            "reused": False,
        },
        status=202,
    )


def job_status_url(job_id):
    return reverse("newsvoice:job_status", args=[job_id])


@login_required
def job_status(request, job_id):
    job = get_object_or_404(
        ProcessingJob.objects.select_related("article", "audio"),
        pk=job_id,
        username=request.user.get_username(),
    )
    payload = {
        "job_id": job.id,
        "type": job.job_type,
        "status": job.status,
        "error": job.error_message,
        "result": job.result,
    }
    if job.audio and job.audio.audio_file:
        payload["audio_url"] = job.audio.audio_file.url
    return JsonResponse(payload)
