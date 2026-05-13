import shutil
import tempfile
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import NewsSearchForm
from .models import (
    ElevenLabsVoice,
    NewsArticle,
    NewsAudio,
    NewsSummary,
    NewsVoiceTTSSetting,
    ProcessingJob,
    UserTwoFactorCode,
)
from .services.gdelt_client import build_query
from .services.gemini_client import build_gemini_error_message
from .services.tts.audio_generator import generate_audio_for_record
from .services.tts.elevenlabs_tts import refresh_elevenlabs_voices


class IndexViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="password123")
        self.client.force_login(self.user)

    def test_index_returns_success(self):
        response = self.client.get(reverse("newsvoice:index"))

        self.assertEqual(response.status_code, 200)

    def test_index_shows_article(self):
        NewsArticle.objects.create(
            username=self.user.username,
            title="テストニュース",
            url="https://example.com/news",
            source_name="example.com",
        )

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, "テストニュース")

    def test_index_hides_other_users_article(self):
        NewsArticle.objects.create(
            username="other-user",
            title="別ユーザーのニュース",
            url="https://example.com/other-user-news",
            source_name="example.com",
        )

        response = self.client.get(reverse("newsvoice:index"))

        self.assertNotContains(response, "別ユーザーのニュース")

    def test_same_url_can_be_saved_per_user(self):
        shared_url = "https://example.com/shared-news"
        NewsArticle.objects.create(
            username=self.user.username,
            title="自分のニュース",
            url=shared_url,
            source_name="example.com",
        )
        NewsArticle.objects.create(
            username="other-user",
            title="別ユーザーの同一URLニュース",
            url=shared_url,
            source_name="example.com",
        )

        self.assertEqual(NewsArticle.objects.filter(url=shared_url).count(), 2)

    def test_index_prefers_japanese_title(self):
        NewsArticle.objects.create(
            username=self.user.username,
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

    def test_index_enqueues_news_fetch_and_shows_saved_articles(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="検索結果ニュース",
            url="https://example.com/search-result",
            source_name="example.com",
        )

        response = self.client.get(reverse("newsvoice:index"), {
            "category": "general",
            "keyword": "",
            "max_records": "5",
            "timespan": "1d",
            "language": "",
        })

        self.assertRedirects(response, reverse("newsvoice:index"))
        self.assertTrue(ProcessingJob.objects.filter(job_type=ProcessingJob.TYPE_NEWS_FETCH).exists())

    def test_index_reuses_same_queued_news_fetch_job(self):
        params = {
            "category": "general",
            "keyword": "",
            "max_records": "5",
            "timespan": "1d",
            "language": "",
        }

        self.client.get(reverse("newsvoice:index"), params)
        self.client.get(reverse("newsvoice:index"), params)

        self.assertEqual(ProcessingJob.objects.filter(job_type=ProcessingJob.TYPE_NEWS_FETCH).count(), 1)

    def test_delete_article_removes_saved_article(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="削除対象ニュース",
            url="https://example.com/delete-target",
            source_name="example.com",
        )

        response = self.client.post(reverse("newsvoice:delete_article", args=[article.id]))

        self.assertRedirects(response, reverse("newsvoice:index"))
        self.assertFalse(NewsArticle.objects.filter(id=article.id).exists())

    def test_summary_form_has_loading_state_attributes(self):
        NewsArticle.objects.create(
            username=self.user.username,
            title="作成中表示テスト",
            url="https://example.com/loading-state",
            source_name="example.com",
        )

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, "data-summary-form")
        self.assertContains(response, 'data-loading-text="作成中..."')

    def test_index_shows_recent_jobs(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="ジョブ対象ニュース",
            url="https://example.com/job-target",
            source_name="example.com",
        )
        ProcessingJob.objects.create(username=self.user.username, job_type=ProcessingJob.TYPE_SUMMARY, article=article)

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, "ジョブ状態")
        self.assertContains(response, "原稿生成")
        self.assertContains(response, "queued")
        self.assertContains(response, "ジョブ対象ニュース")

    @override_settings(NEWSVOICE_HIGH_QUALITY_TTS_ENABLED=True)
    def test_index_shows_audio_generation_button_for_summarized_article(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="一覧音声生成テスト",
            url="https://example.com/index-audio-button",
            source_name="example.com",
        )
        NewsSummary.objects.create(username=self.user.username, article=article, radio_script="今日のニュースです。")

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, reverse("newsvoice:generate_audio", args=[article.id]))
        self.assertContains(response, "高品質音声を生成")

    @override_settings(NEWSVOICE_HIGH_QUALITY_TTS_ENABLED=True)
    def test_index_disables_audio_generation_button_when_audio_job_is_pending(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="一覧音声生成中テスト",
            url="https://example.com/index-audio-pending",
            source_name="example.com",
        )
        NewsSummary.objects.create(username=self.user.username, article=article, radio_script="今日のニュースです。")
        job = ProcessingJob.objects.create(
            username=self.user.username,
            job_type=ProcessingJob.TYPE_AUDIO,
            article=article,
            status=ProcessingJob.STATUS_PROCESSING,
        )

        response = self.client.get(reverse("newsvoice:index"))

        self.assertContains(response, "生成中...")
        self.assertContains(response, "disabled")
        self.assertContains(response, reverse("newsvoice:job_status", args=[job.id]))


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="password123")

    def test_index_requires_login(self):
        response = self.client.get(reverse("newsvoice:index"))

        self.assertRedirects(response, f"{reverse('newsvoice:login')}?next={reverse('newsvoice:index')}")

    def test_login_password_step_redirects_to_two_factor(self):
        response = self.client.post(
            reverse("newsvoice:login"),
            {
                "username": "tester",
                "password": "password123",
                "next": reverse("newsvoice:index"),
            },
        )

        self.assertRedirects(response, reverse("newsvoice:two_factor"))
        self.assertEqual(self.client.session["newsvoice_pending_2fa_user_id"], self.user.id)

    def test_two_factor_code_completes_login(self):
        user_code = UserTwoFactorCode.objects.create(user=self.user)
        session = self.client.session
        session["newsvoice_pending_2fa_user_id"] = self.user.id
        session["newsvoice_pending_2fa_next"] = reverse("newsvoice:index")
        session.save()

        response = self.client.post(reverse("newsvoice:two_factor"), {"code": pyotp.TOTP(user_code.secret).now()})

        self.assertRedirects(response, reverse("newsvoice:index"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_two_factor_page_shows_qr_code(self):
        session = self.client.session
        session["newsvoice_pending_2fa_user_id"] = self.user.id
        session.save()

        response = self.client.get(reverse("newsvoice:two_factor"))

        self.assertContains(response, "data:image/png;base64,")
        self.assertContains(response, "手動入力キー")

    def test_two_factor_rejects_wrong_code(self):
        UserTwoFactorCode.objects.create(user=self.user)
        session = self.client.session
        session["newsvoice_pending_2fa_user_id"] = self.user.id
        session.save()

        response = self.client.post(reverse("newsvoice:two_factor"), {"code": "111111"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "認証コードが正しくありません。")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_settings_view_shows_two_factor_code(self):
        self.client.force_login(self.user)
        user_code = UserTwoFactorCode.objects.create(user=self.user)

        response = self.client.get(reverse("newsvoice:settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data:image/png;base64,")
        self.assertContains(response, user_code.secret)

    def test_settings_view_reissues_two_factor_code(self):
        self.client.force_login(self.user)
        old_code = UserTwoFactorCode.objects.create(user=self.user)

        with patch("newsvoice.models.generate_totp_secret", return_value="JBSWY3DPEHPK3PXP"):
            response = self.client.post(reverse("newsvoice:settings"))

        self.assertRedirects(response, reverse("newsvoice:settings"))
        new_code = UserTwoFactorCode.objects.get(user=self.user)
        self.assertNotEqual(new_code.secret, old_code.secret)
        self.assertEqual(new_code.secret, "JBSWY3DPEHPK3PXP")


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
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="audio-tester", password="password123")
        self.client.force_login(self.user)

    def test_generate_audio_requires_summary(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="Audio test",
            url="https://example.com/audio-test",
            source_name="example.com",
        )

        response = self.client.post(reverse("newsvoice:generate_audio", args=[article.id]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "failed")

    def test_detail_disables_audio_button_when_audio_job_is_pending(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="Audio pending test",
            url="https://example.com/audio-pending-test",
            source_name="example.com",
        )
        NewsSummary.objects.create(username=self.user.username, article=article, radio_script="今日のニュースです。")
        job = ProcessingJob.objects.create(
            username=self.user.username,
            job_type=ProcessingJob.TYPE_AUDIO,
            article=article,
            status=ProcessingJob.STATUS_PROCESSING,
        )

        response = self.client.get(reverse("newsvoice:detail", args=[article.id]))

        self.assertContains(response, "生成中...")
        self.assertContains(response, "disabled")
        self.assertContains(response, reverse("newsvoice:job_status", args=[job.id]))

    @override_settings(NEWSVOICE_HIGH_QUALITY_TTS_ENABLED=False)
    def test_generate_audio_returns_unavailable_when_disabled(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="Audio test",
            url="https://example.com/audio-test-2",
            source_name="example.com",
        )
        NewsSummary.objects.create(username=self.user.username, article=article, radio_script="今日のニュースです。")

        response = self.client.post(reverse("newsvoice:generate_audio", args=[article.id]))

        self.assertEqual(response.status_code, 400)
        self.assertIn("未対応", response.json()["error"])

    @override_settings(NEWSVOICE_HIGH_QUALITY_TTS_ENABLED=True)
    def test_generate_audio_returns_accepted_job(self):
        voice = ElevenLabsVoice.objects.create(
            username=self.user.username,
            voice_id="voice-1",
            name="Test Voice",
        )
        NewsVoiceTTSSetting.objects.create(username=self.user.username, default_voice=voice)
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="Audio test",
            url="https://example.com/audio-test-3",
            source_name="example.com",
        )
        NewsSummary.objects.create(username=self.user.username, article=article, radio_script="今日のニュースです。")

        response = self.client.post(reverse("newsvoice:generate_audio", args=[article.id]))

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], ProcessingJob.STATUS_QUEUED)
        self.assertTrue(ProcessingJob.objects.filter(id=payload["job_id"], job_type=ProcessingJob.TYPE_AUDIO).exists())


class ProcessingJobViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="job-tester", password="password123")
        self.client.force_login(self.user)

    def test_generate_summary_returns_accepted_job_for_ajax(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="Summary job test",
            url="https://example.com/summary-job",
            source_name="example.com",
        )

        response = self.client.post(
            reverse("newsvoice:generate_summary", args=[article.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], ProcessingJob.STATUS_QUEUED)
        self.assertTrue(ProcessingJob.objects.filter(id=payload["job_id"], job_type=ProcessingJob.TYPE_SUMMARY).exists())

    def test_job_status_returns_job_payload(self):
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="Job status test",
            url="https://example.com/job-status",
            source_name="example.com",
        )
        job = ProcessingJob.objects.create(username=self.user.username, job_type=ProcessingJob.TYPE_SUMMARY, article=article)

        response = self.client.get(reverse("newsvoice:job_status", args=[job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], job.id)
        self.assertEqual(response.json()["status"], ProcessingJob.STATUS_QUEUED)


class ElevenLabsTTSTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tts-tester", password="password123")
        self.client.force_login(self.user)
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    @override_settings(ELEVENLABS_API_KEY="test-key")
    @patch("newsvoice.services.tts.elevenlabs_tts.requests.get")
    def test_refresh_elevenlabs_voices_stores_voice_cache(self, mock_get):
        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "voices": [
                        {
                            "voice_id": "voice-1",
                            "name": "Radio Voice",
                            "category": "premade",
                            "preview_url": "https://example.com/preview.mp3",
                            "labels": {"accent": "ja"},
                            "samples": [],
                        }
                    ]
                }

        mock_get.return_value = FakeResponse()

        count = refresh_elevenlabs_voices(self.user.username)

        self.assertEqual(count, 1)
        voice = ElevenLabsVoice.objects.get(username=self.user.username, voice_id="voice-1")
        self.assertEqual(voice.name, "Radio Voice")
        self.assertEqual(voice.preview_url, "https://example.com/preview.mp3")

    def test_tts_settings_view_shows_voice_list(self):
        voice = ElevenLabsVoice.objects.create(
            username=self.user.username,
            voice_id="voice-1",
            name="Radio Voice",
            category="premade",
            preview_url="https://example.com/preview.mp3",
        )
        NewsVoiceTTSSetting.objects.create(username=self.user.username, default_voice=voice)

        response = self.client.get(reverse("newsvoice:tts_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Radio Voice")
        self.assertContains(response, "https://example.com/preview.mp3")

    @override_settings(NEWSVOICE_HIGH_QUALITY_TTS_ENABLED=True, ELEVENLABS_API_KEY="test-key")
    @patch("newsvoice.services.tts.elevenlabs_tts.requests.post")
    def test_generate_audio_for_record_calls_elevenlabs_and_saves_mp3(self, mock_post):
        class FakeResponse:
            ok = True
            content = b"fake mp3"

        mock_post.return_value = FakeResponse()
        voice = ElevenLabsVoice.objects.create(
            username=self.user.username,
            voice_id="voice-1",
            name="Radio Voice",
        )
        setting = NewsVoiceTTSSetting.objects.create(username=self.user.username, default_voice=voice)
        article = NewsArticle.objects.create(
            username=self.user.username,
            title="Audio test",
            url="https://example.com/elevenlabs-audio",
            source_name="example.com",
        )
        summary = NewsSummary.objects.create(
            username=self.user.username,
            article=article,
            radio_script="今日のニュースです。",
        )
        audio = NewsAudio.objects.create(
            username=self.user.username,
            summary=summary,
            tts_provider=NewsAudio.PROVIDER_ELEVENLABS,
            voice_id=voice.voice_id,
            voice_name=voice.name,
            model_id=setting.model_id,
            output_format=setting.output_format,
            language_code=setting.language_code,
            script_hash="hash",
            status=NewsAudio.STATUS_PENDING,
            stability=setting.stability,
            similarity_boost=setting.similarity_boost,
            style=setting.style,
            speed=setting.speed,
            use_speaker_boost=setting.use_speaker_boost,
        )

        generate_audio_for_record(audio)

        audio.refresh_from_db()
        self.assertEqual(audio.status, NewsAudio.STATUS_COMPLETED)
        self.assertTrue(audio.audio_file.name.endswith(".mp3"))
        self.assertEqual(mock_post.call_args.kwargs["json"]["model_id"], "eleven_multilingual_v2")
