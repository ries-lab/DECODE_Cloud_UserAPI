import abc
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
class CachedConfig(abc.ABC):
    def __init__(self, config_path: str):
        """Configuration that is re-read from file when the file is modified."""
        self._config_path = config_path
        self._config = self._read_config()
        self._cache_date = self._read_last_modified()

    @property
    def config(self):
        last_modified = self._read_last_modified()
        if last_modified > self._cache_date:
            self._config = self._read_config()
            self._last_modified = self._read_last_modified()
        return self._config

    @abc.abstractmethod
    def _read_config(self):
        pass

    @abc.abstractmethod
    def _read_last_modified(self):
        pass


class LocalConfig(CachedConfig):
    def _read_config(self):
        with open(self._config_path) as f:
            return yaml.safe_load(f)

    def _read_last_modified(self):
        return os.path.getmtime(self._config_path)


class S3Config(CachedConfig):
    def __init__(self, config_path: str):
        import boto3

        self._s3_client = boto3.client("s3")
        self._bucket, self._key = config_path.split("s3://", 1)[1].split("/", 1)
        super().__init__(config_path)

    def _read_config(self):
        return yaml.safe_load(
            self._s3_client.get_object(Bucket=self._bucket, Key=self._key)["Body"]
        )

    def _read_last_modified(self):
        return self._s3_client.head_object(Bucket=self._bucket, Key=self._key)[
            "LastModified"
        ]


application_config_file = os.environ.get(
    "APPLICATION_CONFIG_FILE",
    os.path.join(os.path.dirname(__file__), "..", "application_config.yaml"),
)
if application_config_file.startswith("s3://"):
    application_config = S3Config(application_config_file)
else:
    application_config = LocalConfig(application_config_file)
