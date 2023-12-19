import json
import os
import yaml
from typing import Any


def _load_possibly_aws_secret(name: str) -> str | None:
    """Load environment variable and read password if it is a secret from AWS Secrets Manager."""
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
email_sender_api_key = os.environ.get("EMAIL_SENDER_API_KEY")
email_sender_secret_key = os.environ.get("EMAIL_SENDER_SECRET_KEY")
email_sender_address = os.environ.get("EMAIL_SENDER_ADDRESS")


# Config
application_config_file = os.environ.get(
    "APPLICATION_CONFIG_FILE",
    os.path.join(os.path.dirname(__file__), "..", "application_config.yaml"),
)


class JITConfig(object):
    """Configuration that is re-read from file on every access."""

    def __getattribute__(self, __name: str) -> Any:
        with open(application_config_file) as f:
            config = yaml.safe_load(f)
        if __name == "config":
            return config
        return getattr(config, __name)

    def __getitem__(self, item):
        return self.config[item]


application_config = JITConfig()
