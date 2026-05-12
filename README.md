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

## 本番環境

本番では `config.settings_production` を使います。秘密値はファイルに書かず、環境変数で渡してください。

必須の環境変数:

```text
DJANGO_SETTINGS_MODULE=config.settings_production
DJANGO_SECRET_KEY=長いランダム文字列
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
GEMINI_API_KEY=your-api-key
```

PostgreSQL を使う場合は `DATABASE_URL` を設定します。未設定の場合は SQLite を使います。

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
```

デプロイ時の代表的なコマンド:

```bash
python manage.py collectstatic --noinput --settings=config.settings_production
python manage.py migrate --noinput --settings=config.settings_production
gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings_production
```

Heroku系/Render系の Procfile 対応環境では、同梱の `Procfile` を使えます。

このサーバーでは `deploy/` 配下に systemd/nginx 用の設定例を置いています。

## 読み上げ

初期状態では、ブラウザの SpeechSynthesis を使う簡易読み上げが有効です。
高品質音声生成のDB・API・画面の土台は用意していますが、Provider実装は未対応です。

```python
NEWSVOICE_SIMPLE_TTS_ENABLED = True
NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = False
NEWSVOICE_DEFAULT_TTS_PROVIDER = "voicevox"
```
