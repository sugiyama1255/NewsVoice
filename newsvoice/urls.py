from django.urls import path

from . import views

app_name = "newsvoice"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("login/2fa/", views.two_factor_view, name="two_factor"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/", views.settings_view, name="settings"),
    path("tts-settings/", views.tts_settings, name="tts_settings"),
    path("tts-settings/voices/refresh/", views.refresh_elevenlabs_voices_view, name="refresh_elevenlabs_voices"),
    path("tts-settings/voices/<str:voice_id>/set-default/", views.set_default_voice, name="set_default_voice"),
    path("", views.index, name="index"),
    path("articles/<int:article_id>/", views.detail, name="detail"),
    path("articles/<int:article_id>/generate/", views.generate_summary, name="generate_summary"),
    path("articles/<int:article_id>/delete/", views.delete_article, name="delete_article"),
    path("articles/<int:article_id>/generate-audio/", views.generate_audio, name="generate_audio"),
    path("jobs/<int:job_id>/", views.job_status, name="job_status"),
]
