"""Download objects from S3 for async document ingest."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote

from werkzeug.utils import secure_filename

_S3_URI_PATTERN = re.compile(r"^s3://([^/]+)/(.+)$")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse s3://bucket/key into bucket and key."""
    normalized = uri.strip()
    match = _S3_URI_PATTERN.match(normalized)
    if not match:
        raise ValueError("s3_uri must look like s3://bucket/path/to/object")
    bucket = match.group(1).strip()
    key = unquote(match.group(2).strip())
    if not bucket or not key:
        raise ValueError("s3_uri must include a bucket name and object key")
    return bucket, key


def resolve_s3_location(payload: dict) -> tuple[str, str]:
    """Resolve bucket and key from JSON body fields."""
    s3_uri = payload.get("s3_uri")
    if isinstance(s3_uri, str) and s3_uri.strip():
        return parse_s3_uri(s3_uri)

    bucket = payload.get("bucket")
    key = payload.get("key")
    if isinstance(bucket, str) and bucket.strip() and isinstance(key, str) and key.strip():
        return bucket.strip(), key.strip()

    raise ValueError("Provide s3_uri or both bucket and key.")


def s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=os.getenv("DOCINTEL_S3_REGION", "us-east-1"),
        endpoint_url=os.getenv("DOCINTEL_S3_ENDPOINT_URL", "") or None,
    )


def download_s3_object_to_job_dir(job_id: str, bucket: str, key: str) -> tuple[Path, str]:
    """Download an S3 object into the job work directory."""
    from docintel.storage import get_storage

    filename = secure_filename(Path(key).name) or "document.bin"
    work_dir = get_storage().job_dir(job_id)
    work_dir.mkdir(parents=True, exist_ok=True)
    destination = work_dir / filename
    s3_client().download_file(bucket, key, str(destination))
    return destination, filename
