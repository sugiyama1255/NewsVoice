from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .forms import NewsSearchForm
from .models import NewsArticle, NewsSummary
from .services.gdelt_client import build_query
from .services.gemini_client import build_gemini_error_message


class IndexViewTests(TestCase):
    def test_index_returns_success(self):
        response = self.client.get(reverse("newsvoice:index"))

        self.assertEqual(response.status_code, 200)

    def test_index_shows_article(self):
        NewsArticle.objects.create(
            title="テストニュース",
            url="https://example.com/news",
            source_name="example.com",
        )

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, "テストニュース")

    def test_index_prefers_japanese_title(self):
        NewsArticle.objects.create(
            title="Calbee to Switch Some Packaging",
            title_ja="カルビー、一部パッケージを切り替えへ",
            url="https://example.com/calbee",
            source_name="example.com",
        )

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, "カルビー、一部パッケージを切り替えへ")
        self.assertContains(response, "原題: Calbee to Switch Some Packaging")

    def test_language_field_is_select_box(self):
        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, '<select name="language"', html=False)
        self.assertContains(response, '<option value="japanese">日本語</option>', html=False)

    def test_index_separates_search_results_and_saved_articles(self):
        article = NewsArticle.objects.create(
            title="検索結果ニュース",
            url="https://example.com/search-result",
            source_name="example.com",
        )

        with patch("newsvoice.views.fetch_and_store_articles", return_value=[article]):
            response = self.client.get(reverse("newsvoice:index"), {
                "category": "general",
                "keyword": "",
                "max_records": "5",
                "timespan": "1d",
                "language": "",
            })

        self.assertContains(response, "検索結果")
        self.assertContains(response, "DB登録済みニュース")

    def test_delete_article_removes_saved_article(self):
        article = NewsArticle.objects.create(
            title="削除対象ニュース",
            url="https://example.com/delete-target",
            source_name="example.com",
        )

        response = self.client.post(reverse("newsvoice:delete_article", args=[article.id]))

        self.assertRedirects(response, reverse("newsvoice:index"))
        self.assertFalse(NewsArticle.objects.filter(id=article.id).exists())

    def test_summary_form_has_loading_state_attributes(self):
        NewsArticle.objects.create(
            title="作成中表示テスト",
            url="https://example.com/loading-state",
            source_name="example.com",
        )

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, "data-summary-form")
        self.assertContains(response, 'data-loading-text="作成中..."')


class NewsSearchFormTests(TestCase):
    def test_language_accepts_choice_value(self):
        form = NewsSearchForm(data={
            "category": "general",
            "keyword": "",
            "max_records": "5",
            "timespan": "1d",
            "language": "japanese",
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["language"], "japanese")


class GdeltQueryTests(TestCase):
    def test_general_query_is_not_language_only(self):
        query = build_query("general", "", "japanese")

        self.assertIn("sourcelang:japanese", query)
        self.assertIn("Japan", query)
        self.assertNotIn("(Japan)", query)

    def test_keyword_is_added_to_query(self):
        query = build_query("ai", "OpenAI", "japanese")

        self.assertIn("OpenAI", query)
        self.assertIn("sourcelang:japanese", query)

    def test_language_filter_is_optional(self):
        query = build_query("general", "", "")

        self.assertIn("Japan", query)
        self.assertNotIn("sourcelang:", query)

    def test_or_query_is_wrapped_in_parentheses(self):
        query = build_query("general", "Sony OR Toyota", "")

        self.assertIn("Sony OR Toyota", query)


class GeminiErrorMessageTests(TestCase):
    def test_503_error_is_user_friendly(self):
        class FakeError(Exception):
            status_code = 503

            def __str__(self):
                return "This model is currently experiencing high demand."

        message = build_gemini_error_message(FakeError())

        self.assertIn("Geminiが現在混雑しています", message)

    def test_429_error_is_user_friendly(self):
        class FakeError(Exception):
            status_code = 429

            def __str__(self):
                return "RESOURCE_EXHAUSTED"

        message = build_gemini_error_message(FakeError())

        self.assertIn("利用制限", message)


class AudioGenerationViewTests(TestCase):
    def test_generate_audio_requires_summary(self):
        article = NewsArticle.objects.create(
            title="Audio test",
            url="https://example.com/audio-test",
            source_name="example.com",
        )

        response = self.client.post(reverse("newsvoice:generate_audio", args=[article.id]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "failed")

    def test_generate_audio_returns_unavailable_when_disabled(self):
        article = NewsArticle.objects.create(
            title="Audio test",
            url="https://example.com/audio-test-2",
            source_name="example.com",
        )
        NewsSummary.objects.create(article=article, radio_script="今日のニュースです。")

        response = self.client.post(reverse("newsvoice:generate_audio", args=[article.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn("未対応", response.json()["error"])
