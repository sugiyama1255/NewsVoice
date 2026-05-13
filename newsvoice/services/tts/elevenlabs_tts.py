import logging
import time

import requests
from django.conf import settings
from django.utils import timezone

from newsvoice.models import ElevenLabsVoice

from .base import BaseTTSService, TTSServiceError


logger = logging.getLogger(__name__)


def require_api_key():
    api_key = getattr(settings, "ELEVENLABS_API_KEY", "")
    if not api_key:
        raise TTSServiceError("ELEVENLABS_API_KEY が設定されていません。")
    return api_key


class ElevenLabsTTSService(BaseTTSService):
    def synthesize(
        self,
        text,
        *,
        voice_id,
        model_id,
        output_format,
        language_code,
        stability,
        similarity_boost,
        style,
        speed,
        use_speaker_boost,
        **kwargs,
    ):
        api_key = require_api_key()
        if not voice_id:
            raise TTSServiceError("ElevenLabsの音声が選択されていません。設定画面で声を選択してください。")

        base_url = getattr(settings, "ELEVENLABS_API_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
        url = f"{base_url}/v1/text-to-speech/{voice_id}"
        params = {"output_format": output_format}
        payload = {
            "text": text,
            "model_id": model_id,
            "language_code": language_code,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "speed": speed,
                "use_speaker_boost": use_speaker_boost,
            },
        }
        headers = {
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        timeout = getattr(settings, "ELEVENLABS_TIMEOUT_SECONDS", 60)

        try:
            response = requests.post(url, params=params, json=payload, headers=headers, timeout=timeout)
        except requests.Timeout as exc:
            raise TTSServiceError("ElevenLabs APIへの接続がタイムアウトしました。") from exc
        except requests.RequestException as exc:
            raise TTSServiceError(f"ElevenLabs APIへの接続に失敗しました: {exc}") from exc

        if not response.ok:
            raise TTSServiceError(build_elevenlabs_error_message(response))
        if not response.content:
            raise TTSServiceError("ElevenLabs APIから空の音声データが返されました。")
        return response.content


def build_elevenlabs_error_message(response):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    detail = payload.get("detail") or payload.get("message") or response.text[:200]
    if isinstance(detail, dict):
        status = detail.get("status", "")
        message = detail.get("message", "")
        if status == "missing_permissions":
            return f"ElevenLabs APIキーの権限が不足しています。{message}"
        detail = message or str(detail)
    if response.status_code in {401, 403}:
        return "ElevenLabs APIキーまたは権限に問題があります。"
    if response.status_code == 429:
        return "ElevenLabsの利用上限に達しました。時間を置いて再実行してください。"
    if response.status_code == 422:
        return f"ElevenLabsへの送信内容に問題があります: {detail}"
    return f"ElevenLabs APIでエラーが発生しました: {response.status_code} {detail}"


def fetch_elevenlabs_voices():
    api_key = require_api_key()
    base_url = getattr(settings, "ELEVENLABS_API_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
    url = f"{base_url}/v2/voices"
    headers = {"xi-api-key": api_key, "Accept": "application/json"}
    timeout = getattr(settings, "ELEVENLABS_TIMEOUT_SECONDS", 60)
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout as exc:
        raise TTSServiceError("ElevenLabsの声一覧取得がタイムアウトしました。") from exc
    except requests.RequestException as exc:
        raise TTSServiceError(f"ElevenLabsの声一覧取得に失敗しました: {exc}") from exc
    if not response.ok:
        raise TTSServiceError(build_elevenlabs_error_message(response))
    payload = response.json()
    return payload.get("voices", [])


def refresh_elevenlabs_voices(username):
    logger.info("ElevenLabs voice refresh started username=%s", username)
    started_at = time.monotonic()
    voices = fetch_elevenlabs_voices()
    fetched_at = timezone.now()
    active_voice_ids = set()
    for voice in voices:
        voice_id = voice.get("voice_id")
        if not voice_id:
            continue
        active_voice_ids.add(voice_id)
        ElevenLabsVoice.objects.update_or_create(
            username=username,
            voice_id=voice_id,
            defaults={
                "name": voice.get("name", "")[:255],
                "category": voice.get("category", "")[:100],
                "description": voice.get("description") or "",
                "preview_url": voice.get("preview_url") or "",
                "labels": voice.get("labels") or {},
                "samples": voice.get("samples") or [],
                "is_active": True,
                "fetched_at": fetched_at,
            },
        )
    if active_voice_ids:
        ElevenLabsVoice.objects.filter(username=username).exclude(voice_id__in=active_voice_ids).update(is_active=False)
    logger.info(
        "ElevenLabs voice refresh completed username=%s count=%s elapsed_ms=%s",
        username,
        len(active_voice_ids),
        int((time.monotonic() - started_at) * 1000),
    )
    return len(active_voice_ids)
