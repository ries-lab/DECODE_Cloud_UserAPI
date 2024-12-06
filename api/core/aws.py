import base64
import hashlib
import hmac


def calculate_secret_hash(email: str, client_id: str, key: str) -> str:
    return base64.b64encode(
        hmac.new(
            bytes(key, "utf-8"),
            bytes(email + client_id, "utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode()
