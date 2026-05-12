from datetime import datetime
import logging
import time
from urllib.parse import urlparse

import requests
from requests.exceptions import JSONDecodeError
from django.conf import settings
from django.utils import timezone

from newsvoice.models import NewsArticle
from newsvoice.services.gemini_client import GeminiClientError, translate_title_to_japanese


class GdeltClientError(Exception):
    pass


logger = logging.getLogger(__name__)
_last_request_at = 0.0


CATEGORY_QUERIES = {
    "general": "Japan",
    "economy": "economy",
    "ai": "artificial intelligence",
    "semiconductor": "semiconductor",
    "stock_market": "stock market",
}


def build_query(category, keyword, language):
    parts = []
    category_query = CATEGORY_QUERIES.get(category, "")
    if category_query:
        if " OR " in category_query:
            parts.append(f"({category_query})")
        else:
            parts.append(category_query)
    if keyword:
        parts.append(keyword)
    if language:
        parts.append(f"sourcelang:{language}")
    return " ".join(parts) or "*"


def parse_gdelt_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return timezone.make_aware(parsed, timezone=timezone.utc)


def wait_for_rate_limit_slot():
    global _last_request_at
    min_interval = getattr(settings, "GDELT_MIN_REQUEST_INTERVAL_SECONDS", 6)
    now = time.monotonic()
    wait_seconds = min_interval - (now - _last_request_at)
    if wait_seconds > 0:
        logger.info("gdelt_rate_limit_wait elapsed=%.3fs", wait_seconds)
        time.sleep(wait_seconds)
    _last_request_at = time.monotonic()


def fetch_articles(category="general", keyword="", max_records=5, timespan="1d", language=""):
    params = {
        "query": build_query(category, keyword, language),
        "mode": "artlist",
        "format": "json",
        "maxrecords": max_records,
        "timespan": timespan,
        "sort": getattr(settings, "GDELT_SORT", "datedesc"),
    }
    headers = {
        "User-Agent": "NewsVoice/0.1 (+https://localhost)",
        "Accept": "application/json",
    }
    max_retries = getattr(settings, "GDELT_MAX_RETRIES", 2)
    retry_wait = getattr(settings, "GDELT_RETRY_WAIT_SECONDS", 3)

    try:
        for attempt in range(max_retries + 1):
            wait_for_rate_limit_slot()
            request_started_at = time.monotonic()
            logger.info("gdelt_request start attempt=%s params=%s", attempt + 1, params)
            response = requests.get(settings.GDELT_API_BASE_URL, params=params, headers=headers, timeout=20)
            request_elapsed = time.monotonic() - request_started_at
            logger.info(
                "gdelt_request response attempt=%s status=%s elapsed=%.3fs",
                attempt + 1,
                response.status_code,
                request_elapsed,
            )
            if response.status_code == 429 and attempt < max_retries:
                time.sleep(retry_wait * (attempt + 1))
                continue
            if response.status_code == 429:
                raise GdeltClientError(
                    "GDELTのアクセス制限に達しました。GDELTは短時間の連続アクセスを制限しています。"
                    "30秒ほど待ってから再実行するか、カテゴリやキーワードを指定して検索範囲を絞ってください。"
                )
            response.raise_for_status()
            try:
                payload = response.json()
            except JSONDecodeError as exc:
                body_preview = response.text.strip()[:120]
                if not body_preview:
                    body_preview = "空の応答"
                if "Parentheses may only be used" in body_preview:
                    raise GdeltClientError(
                        "GDELTの検索クエリ文法エラーです。キーワードの括弧やOR条件を見直してください。"
                        f"応答内容: {body_preview}"
                    ) from exc
                raise GdeltClientError(
                    "GDELTがJSONではない応答を返しました。"
                    "アクセス制限や一時的な混雑の可能性があります。"
                    f"少し待って再実行してください。応答内容: {body_preview}"
                ) from exc
            articles = payload.get("articles", [])
            logger.info("gdelt_request parsed count=%s", len(articles))
            break
    except GdeltClientError:
        raise
    except requests.Timeout as exc:
        raise GdeltClientError(
            "GDELTへの接続がタイムアウトしました。GDELT側が混雑している可能性があります。"
            "少し待ってから再実行するか、キーワードを指定して検索範囲を絞ってください。"
        ) from exc
    except requests.RequestException as exc:
        raise GdeltClientError(f"GDELTからニュースを取得できませんでした: {exc}") from exc
    except ValueError as exc:
        raise GdeltClientError("GDELTの応答JSONを解析できませんでした。少し待って再実行してください。") from exc

    return payload.get("articles", [])


def fetch_and_store_articles(category="general", keyword="", max_records=5, timespan="1d", language=""):
    total_started_at = time.monotonic()
    raw_articles = fetch_articles(
        category=category,
        keyword=keyword,
        max_records=max_records,
        timespan=timespan,
        language=language,
    )
    articles = []
    translation_total = 0.0
    db_total = 0.0
    for item in raw_articles:
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue
        title_ja = ""
        try:
            translation_started_at = time.monotonic()
            title_ja = translate_title_to_japanese(title)
            translation_elapsed = time.monotonic() - translation_started_at
            translation_total += translation_elapsed
            logger.info(
                "title_translation finished elapsed=%.3fs title=%r translated=%s",
                translation_elapsed,
                title[:120],
                bool(title_ja),
            )
        except GeminiClientError:
            logger.exception("title_translation gemini_error title=%r", title[:120])
            title_ja = ""
        except Exception:
            logger.exception("title_translation unexpected_error title=%r", title[:120])
            title_ja = ""

        db_started_at = time.monotonic()
        article, _ = NewsArticle.objects.update_or_create(
            url=url,
            defaults={
                "title": title[:500],
                "title_ja": title_ja[:500],
                "source_name": item.get("sourceCountry") or urlparse(url).netloc,
                "published_at": parse_gdelt_datetime(item.get("seendate")),
                "language": language,
                "country": item.get("sourceCountry", ""),
                "category": category,
                "keyword": keyword,
                "gdelt_id": item.get("url_mobile") or "",
            },
        )
        db_elapsed = time.monotonic() - db_started_at
        db_total += db_elapsed
        logger.info("article_store finished elapsed=%.3fs url=%s", db_elapsed, url)
        articles.append(article)
    logger.info(
        "fetch_and_store_articles finished raw_count=%s stored_count=%s translation_total=%.3fs db_total=%.3fs elapsed=%.3fs",
        len(raw_articles),
        len(articles),
        translation_total,
        db_total,
        time.monotonic() - total_started_at,
    )
    return articles
