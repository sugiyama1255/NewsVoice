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
ELEVENLABS_API_KEY = "your-elevenlabs-api-key"
NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = True
NEWSVOICE_DEFAULT_TTS_PROVIDER = "elevenlabs"
```

## 起動

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

ラジオ原稿生成や高品質音声生成はバックグラウンドジョブとして受け付けます。
別ターミナルで worker を起動してください。

```powershell
.\.venv\Scripts\python.exe manage.py process_jobs
```

GDELTが混雑してニュース取得に失敗した場合、worker は次のニュース取得ジョブへ進む前に既定で60秒待機します。
待機秒数は `NEWSVOICE_NEWS_FETCH_FAILURE_COOLDOWN_SECONDS` で変更できます。

トップ画面:

```text
http://127.0.0.1:8000/
```

ログインにはDjangoユーザーのユーザー名/パスワードと、認証アプリの6桁コードを使います。
管理ユーザーは `python manage.py createsuperuser` で作成できます。
パスワード認証後の2段階認証画面、またはログイン後のヘッダー「設定」からQRコードを読み取って認証アプリへ登録できます。
QRを再発行すると、それまでの認証アプリコードは使えなくなります。

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
python manage.py process_jobs --settings=config.settings_production
```

Heroku系/Render系の Procfile 対応環境では、同梱の `Procfile` を使えます。`web` に加えて `worker` プロセスも起動してください。

このサーバーでは `deploy/` 配下に systemd/nginx 用の設定例を置いています。

## 読み上げ

初期状態では、ブラウザの SpeechSynthesis を使う簡易読み上げが有効です。
高品質音声生成は ElevenLabs を使います。`ELEVENLABS_API_KEY` を設定し、ログイン後の「音声設定」で声一覧を更新して、既定音声を選んでください。

```python
NEWSVOICE_SIMPLE_TTS_ENABLED = True
NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = True
NEWSVOICE_DEFAULT_TTS_PROVIDER = "elevenlabs"
ELEVENLABS_API_KEY = "your-elevenlabs-api-key"
```

高品質音声はニュース詳細画面の既存の「高品質音声を生成」ボタンから生成します。同じ原稿・同じ音声設定のmp3が既にある場合は再利用します。
