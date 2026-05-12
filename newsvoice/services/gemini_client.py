import re

from django.conf import settings
from google import genai
from google.genai import errors as genai_errors

from newsvoice.models import NewsSummary


class GeminiClientError(Exception):
    pass


def build_gemini_error_message(exc):
    status_code = getattr(exc, "status_code", None)
    message = str(exc)

    if status_code == 503 or "UNAVAILABLE" in message or "high demand" in message:
        return "Geminiが現在混雑しています。少し待ってから、もう一度ラジオ原稿を作成してください。"
    if status_code == 429 or "RESOURCE_EXHAUSTED" in message:
        return "Geminiの利用制限に達しました。しばらく待ってから再実行してください。"
    if status_code in {401, 403}:
        return "Gemini APIキーまたは権限に問題があります。config/settings_local.py の設定を確認してください。"
    if status_code == 404:
        return "指定されたGeminiモデルが見つかりません。GEMINI_MODEL の設定を確認してください。"
    return f"Gemini APIでエラーが発生しました: {message}"


def generate_content_text(prompt):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
    except genai_errors.APIError as exc:
        raise GeminiClientError(build_gemini_error_message(exc)) from exc
    except Exception as exc:
        raise GeminiClientError(f"Gemini APIへの接続中にエラーが発生しました: {exc}") from exc

    text = getattr(response, "text", "").strip()
    if not text:
        raise GeminiClientError("Geminiから空の回答が返されました。")
    return text


def contains_japanese(text):
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text or ""))


def translate_title_to_japanese(title):
    if not title or contains_japanese(title):
        return ""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return ""

    prompt = f"""次のニュース記事タイトルを、日本語の自然なニュース見出しに翻訳してください。

条件:
- 出力は翻訳後のタイトルのみ
- 解説や引用符は不要
- 固有名詞は無理に訳さない
- 投資判断や事実の追加はしない

タイトル:
{title}
"""
    return generate_content_text(prompt).strip("「」\"'")


def build_radio_prompt(article):
    return f"""以下のニュース情報をもとに、1分程度で読み上げるラジオ風ニュース原稿を作成してください。

条件:
- 日本語で書く
- 400〜600文字程度
- 読み上げやすい短い文にする
- 一文を長くしすぎない
- 句読点を自然に入れる
- ラジオ番組のニュースコーナーのように自然な口調にする
- 最初に短い導入を入れる
- ニュースの事実を簡潔に説明する
- 背景を少し補足する
- 最後にAIとしての短い見解を入れる
- 投資判断や断定的な表現は避ける
- 煽る表現は使わない
- 事実と意見が混ざりすぎないようにする
- 専門用語は少し噛み砕く
- SpeechSynthesisでも読み上げやすい文章にする

出力形式:
【タイトル】
【ラジオ原稿】
【AIの見解】
【影響ラベル】positive / negative / neutral / mixed / unknown

ニュース情報:
タイトル: {article.display_title}
原題: {article.title}
出典: {article.source_name}
公開日時: {article.published_at}
URL: {article.url}
本文または概要:
GDELTから取得した記事メタ情報をもとにしてください。記事本文の全文転載は避けてください。
"""


def parse_generated_text(text):
    sections = {
        "summary_text": "",
        "radio_script": text.strip(),
        "ai_opinion": "",
        "impact_label": NewsSummary.IMPACT_UNKNOWN,
    }
    radio_match = re.search(r"【ラジオ原稿】\s*(.*?)(?=【AIの見解】|【影響ラベル】|$)", text, re.S)
    opinion_match = re.search(r"【AIの見解】\s*(.*?)(?=【影響ラベル】|$)", text, re.S)
    impact_match = re.search(r"【影響ラベル】\s*(positive|negative|neutral|mixed|unknown)", text, re.I)
    title_match = re.search(r"【タイトル】\s*(.*?)(?=【ラジオ原稿】|$)", text, re.S)

    if title_match:
        sections["summary_text"] = title_match.group(1).strip()
    if radio_match:
        sections["radio_script"] = radio_match.group(1).strip()
    if opinion_match:
        sections["ai_opinion"] = opinion_match.group(1).strip()
    if impact_match:
        sections["impact_label"] = impact_match.group(1).lower()
    return sections


def generate_radio_summary(article):
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiClientError("GEMINI_API_KEY が設定されていません。config/settings_local.py に設定してください。")

    prompt = build_radio_prompt(article)
    text = generate_content_text(prompt)

    parsed = parse_generated_text(text)
    summary, _ = NewsSummary.objects.update_or_create(
        article=article,
        defaults={
            **parsed,
            "model_name": settings.GEMINI_MODEL,
            "prompt_text": prompt,
        },
    )
    return summary
