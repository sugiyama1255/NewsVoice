# NewsVoice

GDELTから最新ニュースを取得し、Geminiでラジオ風ニュース原稿と短い見解を生成して、ブラウザのSpeechSynthesisで読み上げるDjangoアプリです。

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`config/settings_local.py` を作成し、Gemini API設定を置きます。

```python
GEMINI_API_KEY = "your-api-key"
GEMINI_MODEL = "gemini-2.5-flash-lite"
```

## 起動

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

トップ画面:

```text
http://127.0.0.1:8000/
```

## テスト

```powershell
.\.venv\Scripts\python.exe manage.py test
```

## 読み上げ

初期状態では、ブラウザの SpeechSynthesis を使う簡易読み上げが有効です。
高品質音声生成のDB・API・画面の土台は用意していますが、Provider実装は未対応です。

```python
NEWSVOICE_SIMPLE_TTS_ENABLED = True
NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = False
NEWSVOICE_DEFAULT_TTS_PROVIDER = "voicevox"
```
