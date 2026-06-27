"""Экстрактор старого бинарного XLS (раздел 7.4).

Клиника 7 — старый бинарный .xls (OLE2), три тарифа, заголовок на 6-й строке.
openpyxl такой формат не читает, поэтому конвертируем в .xlsx через
LibreOffice в headless-режиме и делегируем разбор XlsxExtractor-у. Если
конвертация недоступна (нет soffice), не падаем — возвращаем пустой результат
с предупреждением.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from app.pipeline.base import ExtractionResult, Extractor
from app.pipeline.extractors.xlsx_extractor import XlsxExtractor

# Имена бинаря LibreOffice на разных системах.
_SOFFICE_BINARIES = ("soffice", "libreoffice")
# Таймаут конвертации, секунды (большие книги конвертируются не мгновенно).
_CONVERT_TIMEOUT = 180


class XlsExtractor(Extractor):
    """Извлекает позиции из старого .xls через конвертацию в .xlsx."""

    name = "xls"

    def can_handle(self, file_path: str, file_format: str) -> bool:
        return file_format == "xls"

    def extract(self, file_path: str) -> ExtractionResult:
        result = ExtractionResult(extractor_used=self.name)

        with tempfile.TemporaryDirectory(prefix="xls2xlsx_") as tmpdir:
            converted = self._convert(file_path, tmpdir, result)
            if converted is None:
                # Конвертация не удалась — пустой результат, без исключения.
                return result

            # Делегируем разбор XLSX-экстрактору, переносим его данные к себе.
            inner = XlsxExtractor().extract(converted)
            result.items = inner.items
            result.raw_content = inner.raw_content
            result.page_count = inner.page_count
            result.ocr_applied = inner.ocr_applied
            for w in inner.warnings:
                result.warn(w)

        return result

    # ------------------------------------------------------------------
    # Конвертация LibreOffice headless
    # ------------------------------------------------------------------
    def _convert(
        self, file_path: str, tmpdir: str, result: ExtractionResult
    ) -> str | None:
        """Конвертирует .xls -> .xlsx в tmpdir. Возвращает путь к .xlsx или None.

        Пробует и «soffice», и «libreoffice» как имя бинаря.
        """
        last_error: str | None = None

        for binary in _SOFFICE_BINARIES:
            try:
                proc = subprocess.run(
                    [
                        binary,
                        "--headless",
                        "--convert-to",
                        "xlsx",
                        "--outdir",
                        tmpdir,
                        file_path,
                    ],
                    capture_output=True,
                    timeout=_CONVERT_TIMEOUT,
                )
            except FileNotFoundError:
                # Этого бинаря в системе нет — пробуем следующий.
                last_error = f"бинарь {binary!r} не найден"
                continue
            except subprocess.TimeoutExpired:
                last_error = f"таймаут конвертации через {binary!r}"
                continue
            except Exception as exc:  # noqa: BLE001 — любая ошибка процесса не валит pipeline
                last_error = f"ошибка {binary!r}: {exc}"
                continue

            if proc.returncode != 0:
                stderr = (proc.stderr or b"").decode("utf-8", "replace").strip()
                last_error = f"{binary!r} вернул код {proc.returncode}: {stderr}"
                continue

            converted = self._find_converted(file_path, tmpdir)
            if converted is not None:
                return converted
            last_error = f"{binary!r} отработал, но .xlsx не появился в {tmpdir}"

        result.warn(
            "Не удалось конвертировать .xls в .xlsx через LibreOffice: "
            f"{last_error or 'причина неизвестна'}"
        )
        return None

    @staticmethod
    def _find_converted(file_path: str, tmpdir: str) -> str | None:
        """Находит результат конвертации в tmpdir.

        LibreOffice сохраняет под тем же базовым именем с расширением .xlsx.
        """
        base = os.path.splitext(os.path.basename(file_path))[0]
        expected = os.path.join(tmpdir, f"{base}.xlsx")
        if os.path.isfile(expected):
            return expected
        # Фолбэк: любой .xlsx в каталоге вывода.
        for entry in os.listdir(tmpdir):
            if entry.lower().endswith(".xlsx"):
                return os.path.join(tmpdir, entry)
        return None
