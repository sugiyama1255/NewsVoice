from django.urls import path

from . import views

app_name = "newsvoice"

urlpatterns = [
    path("", views.index, name="index"),
    path("articles/<int:article_id>/", views.detail, name="detail"),
    path("articles/<int:article_id>/generate/", views.generate_summary, name="generate_summary"),
    path("articles/<int:article_id>/delete/", views.delete_article, name="delete_article"),
    path("articles/<int:article_id>/generate-audio/", views.generate_audio, name="generate_audio"),
]
