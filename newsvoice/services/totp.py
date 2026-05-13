import base64
from io import BytesIO

import pyotp
import qrcode


ISSUER_NAME = "NewsVoice"


def generate_totp_secret():
    return pyotp.random_base32()


def build_totp_uri(user, secret):
    return pyotp.TOTP(secret).provisioning_uri(name=user.get_username(), issuer_name=ISSUER_NAME)


def build_qr_data_uri(uri):
    image = qrcode.make(uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_user_qr_data_uri(user, secret):
    return build_qr_data_uri(build_totp_uri(user, secret))


def verify_totp(secret, code):
    return pyotp.TOTP(secret).verify(code, valid_window=1)
