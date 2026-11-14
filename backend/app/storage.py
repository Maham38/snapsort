from functools import lru_cache
from urllib.parse import quote

import httpx

from app.config import get_settings


@lru_cache
def _storage_config() -> tuple[str, str, str]:
    settings = get_settings()
    secret_key = settings.supabase_secret_key or settings.supabase_service_role_key
    required = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SECRET_KEY": secret_key,
        "SUPABASE_BUCKET_NAME": settings.supabase_bucket_name,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Supabase Storage is not configured. Missing: " + ", ".join(missing)
        )
    return (
        settings.supabase_url.rstrip("/"),
        secret_key,
        settings.supabase_bucket_name,
    )


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer " + key,
        "apikey": key,
    }


def create_upload_url(storage_key: str, content_type: str) -> str:
    base_url, service_key, bucket = _storage_config()
    path = quote(storage_key, safe="/")
    endpoint = f"{base_url}/storage/v1/object/upload/sign/{bucket}/{path}"
    try:
        response = httpx.post(
            endpoint,
            headers={**_headers(service_key), "Content-Type": "application/json"},
            json={"expiresIn": get_settings().supabase_signed_url_ttl_seconds},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("Supabase could not create a signed upload URL") from error

    token = data.get("token")
    if not token:
        raise RuntimeError("Supabase returned no signed upload token")
    return f"{base_url}/storage/v1/object/upload/sign/{bucket}/{path}?token={quote(token)}"


def object_exists(storage_key: str) -> bool:
    base_url, service_key, bucket = _storage_config()
    path = quote(storage_key, safe="/")
    endpoint = f"{base_url}/storage/v1/object/{bucket}/{path}"
    try:
        response = httpx.head(endpoint, headers=_headers(service_key), timeout=10)
    except httpx.HTTPError as error:
        raise RuntimeError("Supabase Storage could not be reached") from error
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def download_object(storage_key: str) -> bytes:
    base_url, service_key, bucket = _storage_config()
    path = quote(storage_key, safe="/")
    endpoint = f"{base_url}/storage/v1/object/{bucket}/{path}"
    try:
        response = httpx.get(endpoint, headers=_headers(service_key), timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError("Supabase Storage could not download the object") from error
    return response.content


def create_download_url(storage_key: str) -> str:
    base_url, service_key, bucket = _storage_config()
    path = quote(storage_key, safe="/")
    endpoint = f"{base_url}/storage/v1/object/sign/{bucket}/{path}"
    try:
        response = httpx.post(
            endpoint,
            headers={**_headers(service_key), "Content-Type": "application/json"},
            json={"expiresIn": get_settings().supabase_signed_url_ttl_seconds},
            timeout=10,
        )
        response.raise_for_status()
        token = response.json().get("signedURL")
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("Supabase could not create a signed download URL") from error
    if not token:
        raise RuntimeError("Supabase returned no signed download URL")
    if token.startswith("http"):
        return token
    return f"{base_url}/storage/v1{token}"
