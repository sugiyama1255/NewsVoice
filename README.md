# NewsVoice

GDELTから最新ニュースを取得し、Geminiでラジオ風ニュース原稿と短い見解を生成して、ブラウザのSpeechSynthesisで読み上げるDjangoアプリです。

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`config/settings_local.py` を作成し、共通設定を読み込んだうえでGemini APIやElevenLabs API設定を置きます。

```python
from .settings import *

GEMINI_API_KEY = "your-api-key"
GEMINI_MODEL = "gemini-2.5-flash-lite"
ELEVENLABS_API_KEY = "your-elevenlabs-api-key"
NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = True
NEWSVOICE_DEFAULT_TTS_PROVIDER = "elevenlabs"
```

## 起動

```powershell
.\.venv\Scripts\python.exe manage.py migrate --settings=config.settings_local
.\.venv\Scripts\python.exe manage.py runserver --settings=config.settings_local
```

ラジオ原稿生成や高品質音声生成はバックグラウンドジョブとして受け付けます。
別ターミナルで worker を起動してください。

```powershell
.\.venv\Scripts\python.exe manage.py process_jobs --settings=config.settings_local
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
.\.venv\Scripts\python.exe manage.py test --settings=config.settings_local
```

## 本番環境

NewsVoiceでは旧本番専用設定ファイルと `.env` は使いません。
開発・本番ともに `config.settings_local` を設定入口にし、本番・個別設定は `config/settings_local.py` に集約します。

`config/settings_local.py` は `.gitignore` に含め、Gitへコミットしません。
Git管理する設定例は `config/settings_local.example.py` だけです。

Gemini、ElevenLabs、機能ON/OFF、`DEBUG`、`ALLOWED_HOSTS`、HTTPS関連設定など、環境ごとの差分は `settings_local.py` に書きます。
`.env` はNewsVoiceの設定置き場として使わないでください。

本番用 `config/settings_local.py` の例:

```python
from .settings import *

DEBUG = False
SECRET_KEY = "長いランダム文字列"
ALLOWED_HOSTS = [
    "newsvoice.simoyakaviewer.com",
]

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

GEMINI_API_KEY = "ここにGemini APIキーを設定"
GEMINI_MODEL = "gemini-2.5-flash-lite"

NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = True
NEWSVOICE_DEFAULT_TTS_PROVIDER = "elevenlabs"
ELEVENLABS_API_KEY = "ここにElevenLabs APIキーを設定"

ELEVENLABS_DEFAULT_MODEL_ID = "eleven_multilingual_v2"
ELEVENLABS_DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
ELEVENLABS_DEFAULT_LANGUAGE_CODE = "ja"
ELEVENLABS_DEFAULT_STABILITY = 0.45
ELEVENLABS_DEFAULT_SIMILARITY_BOOST = 0.75
ELEVENLABS_DEFAULT_STYLE = 0.20
ELEVENLABS_DEFAULT_SPEED = 0.95
ELEVENLABS_DEFAULT_USE_SPEAKER_BOOST = True
```

本番設定の確認:

```bash
python manage.py shell --settings=config.settings_local -c "from django.conf import settings; print('HIGH=', getattr(settings, 'NEWSVOICE_HIGH_QUALITY_TTS_ENABLED', None)); print('PROVIDER=', getattr(settings, 'NEWSVOICE_DEFAULT_TTS_PROVIDER', None)); print('APIKEY=', bool(getattr(settings, 'ELEVENLABS_API_KEY', None)))"
```

期待値:

```text
HIGH= True
PROVIDER= elevenlabs
APIKEY= True
```

PostgreSQL を使う場合は、`settings_local.py` で `DATABASES` を上書きします。

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "DBNAME",
        "USER": "USER",
        "PASSWORD": "PASSWORD",
        "HOST": "HOST",
        "PORT": "5432",
    }
}
```

デプロイ時の代表的なコマンド:

```bash
python manage.py check --settings=config.settings_local
python manage.py migrate --noinput --settings=config.settings_local
python manage.py collectstatic --noinput --settings=config.settings_local
gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings_local
python manage.py process_jobs --settings=config.settings_local
```

systemd運用時の反映例:

```bash
python manage.py check --settings=config.settings_local
python manage.py migrate --settings=config.settings_local
python manage.py collectstatic --noinput --settings=config.settings_local
sudo systemctl daemon-reload
sudo systemctl restart newsvoice
sudo systemctl restart newsvoice-worker
```

Heroku系/Render系の Procfile 対応環境では、同梱の `Procfile` を使えます。`web` に加えて `worker` プロセスも起動してください。

このサーバーでは `deploy/` 配下に systemd/nginx 用の設定例を置いています。
`deploy/newsvoice-worker.service` を `/etc/systemd/system/newsvoice-worker.service` に配置すると、workerもsystemdで常駐管理できます。

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
