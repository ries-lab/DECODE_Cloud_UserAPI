import json
import os
import yaml
from typing import Any

from api import notifications


def _load_possibly_aws_secret(name: str) -> str | None:
    value = os.environ.get(name)
    try:
        return json.loads(value)["password"]  # AWS Secrets Manager
    except:
        return value


# Stage
prod = bool(int(os.environ.get("PROD", "0")))


# Data
database_url = os.environ.get("DATABASE_URL", "sqlite:///./sql_app.db")
if os.environ.get("DATABASE_SECRET"):  # set and not None
    database_secret = _load_possibly_aws_secret("DATABASE_SECRET")
    database_url = database_url.format(database_secret)
filesystem = os.environ.get("FILESYSTEM")
s3_bucket = os.environ.get("S3_BUCKET")
user_data_root_path = os.environ.get("USER_DATA_ROOT_PATH")


# Worker-facing API
workerfacing_api_url = os.environ.get("WORKERFACING_API_URL", "http://127.0.0.1:8001")
internal_api_key_secret = _load_possibly_aws_secret("INTERNAL_API_KEY_SECRET")


# Authentication
cognito_user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
cognito_region = os.environ.get("COGNITO_REGION")
cognito_client_id = os.environ.get("COGNITO_CLIENT_ID")
cognito_secret = _load_possibly_aws_secret("COGNITO_SECRET")
cognito_public_client_id = os.environ.get("COGNITO_PUBLIC_CLIENT_ID")


# Email sender
email_sender_service = os.environ["EMAIL_SENDER_SERVICE"]

match email_sender_service:
    case None:
        email_sender = notifications.DummyEmailSender()
    case "mailjet":
        email_sender = notifications.MailjetEmailSender(
            api_key=_load_possibly_aws_secret("EMAIL_SENDER_API_KEY"),
            api_secret=_load_possibly_aws_secret("EMAIL_SENDER_SECRET_KEY"),
            sender_address=os.environ["EMAIL_SENDER_ADDRESS"],
        )
    case _:
        raise ValueError(
            f"Unknown email sender service {email_sender_service}. Only mailjet is supported."
        )


# Config
application_config_file = os.environ.get(
    "APPLICATION_CONFIG_FILE",
    os.path.join(os.path.dirname(__file__), "..", "application_config.yaml"),
)


class JITConfig(object):
    def __getattribute__(self, __name: str) -> Any:
        with open(application_config_file) as f:
            config = yaml.safe_load(f)
        if __name == "config":
            return config
        return getattr(config, __name)

    def __getitem__(self, item):
        return self.config[item]


application_config = JITConfig()
