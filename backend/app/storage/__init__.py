"""Object storage. Оригиналы файлов не удаляются никогда (требование ТЗ).

Бэкенд local (том в Docker) или s3-совместимое. Выбор по STORAGE_BACKEND.
"""

from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod

from app.config import settings


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, src_path: str) -> str:
        """Сохранить файл, вернуть storage_path."""

    @abstractmethod
    def open_path(self, storage_path: str) -> str:
        """Вернуть локальный путь для чтения (скачать при необходимости)."""


class LocalStorage(Storage):
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save(self, key: str, src_path: str) -> str:
        dst = os.path.join(self.base_dir, key)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.abspath(src_path) != os.path.abspath(dst):
            shutil.copy2(src_path, dst)
        return dst

    def open_path(self, storage_path: str) -> str:
        return storage_path


class S3Storage(Storage):
    def __init__(self) -> None:
        import boto3

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            region_name=settings.s3_region,
        )
        self._tmp = "/tmp/medpartners-s3"
        os.makedirs(self._tmp, exist_ok=True)

    def save(self, key: str, src_path: str) -> str:
        self.client.upload_file(src_path, self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def open_path(self, storage_path: str) -> str:
        key = storage_path.split(f"s3://{self.bucket}/", 1)[-1]
        local = os.path.join(self._tmp, key)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        self.client.download_file(self.bucket, key, local)
        return local


def get_storage() -> Storage:
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage(settings.storage_local_dir)
