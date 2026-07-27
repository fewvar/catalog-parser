"""HTTP-слой: вежливые запросы с паузами и повторами."""

import time
import requests

# Только latin-1: HTTP-заголовки не принимают кириллицу.
USER_AGENT = "catalog-parser/1.0 (+https://github.com/fewvar/catalog-parser)"


class FetchError(Exception):
    """Страницу не удалось получить после всех попыток."""


def describe(error: Exception) -> str:
    """Короткое человеческое описание вместо простыни из urllib3."""
    if isinstance(error, requests.ConnectionError):
        return "нет соединения с сайтом"
    if isinstance(error, requests.Timeout):
        return "сайт не ответил вовремя"
    if isinstance(error, requests.TooManyRedirects):
        return "слишком много перенаправлений"
    message = str(error)
    return message if len(message) < 120 else message[:117] + "…"


class Fetcher:
    def __init__(self, delay: float = 0.5, timeout: int = 20, retries: int = 3):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_request = 0.0
        self.requests_made = 0

    def _wait(self) -> None:
        """Выдерживаем паузу между запросами, чтобы не нагружать сайт."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def get(self, url: str) -> str:
        last_error = None

        for attempt in range(1, self.retries + 1):
            self._wait()
            try:
                response = self.session.get(url, timeout=self.timeout)
                self._last_request = time.monotonic()
                self.requests_made += 1

                if response.status_code == 404:
                    raise FetchError(f"страница не найдена: {url}")

                # Сервер просит подождать или ему плохо — отступаем и пробуем снова.
                if response.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {response.status_code}")

                response.raise_for_status()
                response.encoding = response.apparent_encoding or "utf-8"
                return response.text

            except FetchError:
                raise
            except (requests.RequestException, requests.HTTPError) as error:
                last_error = error
                if attempt < self.retries:
                    pause = self.delay * (2 ** attempt)
                    print(f"    попытка {attempt} из {self.retries} не удалась ({describe(error)}), жду {pause:.1f}с")
                    time.sleep(pause)

        raise FetchError(f"не удалось загрузить {url} — {describe(last_error)}")

    def close(self) -> None:
        self.session.close()
