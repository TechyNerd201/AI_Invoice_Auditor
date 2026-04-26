import boto3
import json
import os
from typing import Optional
from log_utils.logger import get_logger

logger = get_logger(__name__)

_s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))


def _bucket() -> str:
    return os.getenv("S3_BUCKET", "invoice-auditor-storage")


def upload_file(local_path: str, s3_key: str) -> None:
    _s3.upload_file(local_path, _bucket(), s3_key)
    logger.info("[s3_service] Uploaded %s → s3://%s/%s", local_path, _bucket(), s3_key)


def put_json(s3_key: str, obj: dict) -> None:
    _s3.put_object(
        Bucket=_bucket(),
        Key=s3_key,
        Body=json.dumps(obj, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )
    logger.info("[s3_service] Wrote JSON → s3://%s/%s", _bucket(), s3_key)


def put_text(s3_key: str, text: str) -> None:
    _s3.put_object(
        Bucket=_bucket(),
        Key=s3_key,
        Body=text.encode("utf-8"),
        ContentType="text/plain",
    )
    logger.info("[s3_service] Wrote text → s3://%s/%s", _bucket(), s3_key)


def get_json(s3_key: str) -> Optional[dict]:
    try:
        obj = _s3.get_object(Bucket=_bucket(), Key=s3_key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except _s3.exceptions.NoSuchKey:
        return None
    except Exception:
        return None


def get_text(s3_key: str) -> Optional[str]:
    try:
        obj = _s3.get_object(Bucket=_bucket(), Key=s3_key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return None


def key_exists(s3_key: str) -> bool:
    try:
        _s3.head_object(Bucket=_bucket(), Key=s3_key)
        return True
    except Exception:
        return False
