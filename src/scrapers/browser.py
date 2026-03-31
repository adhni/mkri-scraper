from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .mkri_tracking import DEFAULT_USER_AGENT, TrackingAccessBlockedError, _looks_like_cloudflare_challenge


class BrowserAutomationUnavailableError(RuntimeError):
    pass


def _normalized_download_key(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    parts = urlsplit(url)
    scheme = "https" if parts.scheme in {"http", "https"} else parts.scheme
    host = parts.netloc.casefold()
    path = parts.path.rstrip("/")
    query = tuple(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return (f"{scheme}://{host}", path, query)


def _download_url_matches(candidate_url: str, target_url: str) -> bool:
    if candidate_url == target_url:
        return True
    if _normalized_download_key(candidate_url) == _normalized_download_key(target_url):
        return True

    candidate_parts = urlsplit(candidate_url)
    target_parts = urlsplit(target_url)
    candidate_query = dict(parse_qsl(candidate_parts.query, keep_blank_values=True))
    target_query = dict(parse_qsl(target_parts.query, keep_blank_values=True))
    if candidate_parts.path == target_parts.path and candidate_query == target_query:
        return True

    candidate_id = candidate_query.get("id")
    target_id = target_query.get("id")
    return (
        candidate_id is not None
        and candidate_id == target_id
        and "download.putusan" in candidate_parts.query.casefold() + candidate_parts.path.casefold()
        and "download.putusan" in target_parts.query.casefold() + target_parts.path.casefold()
    )


@dataclass
class BrowserSessionConfig:
    headless: bool = True
    timeout_ms: int = 30000
    storage_state_path: str | Path | None = None


class MkriBrowserSession:
    def __init__(self, config: BrowserSessionConfig | None = None) -> None:
        self.config = config or BrowserSessionConfig()
        self._playwright_cm: Any | None = None
        self._playwright: Any | None = None
        self.browser: Any | None = None
        self.context: Any | None = None
        self.page: Any | None = None

    def __enter__(self) -> "MkriBrowserSession":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - import path depends on environment.
            raise BrowserAutomationUnavailableError(
                "Browser mode requires Playwright. Install with `pip install -e '.[browser]'` and run `playwright install chromium`."
            ) from exc

        self._playwright_cm = sync_playwright()
        self._playwright = self._playwright_cm.start()
        self.browser = self._playwright.chromium.launch(headless=self.config.headless)
        context_kwargs: dict[str, Any] = {
            "accept_downloads": True,
            "user_agent": DEFAULT_USER_AGENT,
            "locale": "id-ID",
        }
        storage_state_path = self._storage_state_path()
        if storage_state_path and storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)
        self.context = self.browser.new_context(**context_kwargs)
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.config.timeout_ms)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        storage_state_path = self._storage_state_path()
        if self.context is not None and storage_state_path is not None:
            storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            self.context.storage_state(path=str(storage_state_path))
        if self.context is not None:
            self.context.close()
        if self.browser is not None:
            self.browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self.page = None
        self.context = None
        self.browser = None
        self._playwright = None
        self._playwright_cm = None

    def fetch_html(self, url: str) -> str:
        if self.page is None:
            raise RuntimeError("Browser session is not open")
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=self.config.timeout_ms)
        except Exception:
            pass
        attempts = max(self.config.timeout_ms // 1000, 1)
        html = self.page.content()
        for _ in range(attempts):
            if not _looks_like_cloudflare_challenge(html):
                return html
            self.page.wait_for_timeout(1000)
            html = self.page.content()
        raise TrackingAccessBlockedError(
            "MKRI browser mode still sees a Cloudflare challenge; try headful mode or reuse a browser storage state."
        )

    def download_from_current_page(self, target_url: str, destination: str | Path) -> Path:
        if self.page is None:
            raise RuntimeError("Browser session is not open")
        if self.context is None:
            raise RuntimeError("Browser session context is not open")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        hrefs = self.page.eval_on_selector_all(
            "a[href]",
            "(links) => links.map((item) => item.href).filter(Boolean)",
        )
        resolved_url = next((href for href in hrefs if _download_url_matches(href, target_url)), None)
        if resolved_url is None:
            raise FileNotFoundError(f"Decision link not found on current tracking page: {target_url}")

        try:
            with self.page.expect_download(timeout=self.config.timeout_ms) as download_info:
                clicked = self.page.evaluate(
                    """(resolvedUrl) => {
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        const target = links.find((item) => item.href === resolvedUrl);
                        if (!target) return false;
                        target.removeAttribute('target');
                        target.click();
                        return true;
                    }""",
                    resolved_url,
                )
                if not clicked:
                    raise FileNotFoundError(f"Decision link not found on current tracking page: {resolved_url}")
            download = download_info.value
            download.save_as(str(destination))
            return destination
        except Exception:
            response = self.context.request.get(
                resolved_url,
                timeout=self.config.timeout_ms,
                headers={"Referer": self.page.url},
            )
            if not response.ok:
                raise RuntimeError(f"Decision download failed with HTTP {response.status} for {resolved_url}")
            destination.write_bytes(response.body())
            return destination

    def download_url(self, target_url: str, destination: str | Path) -> Path:
        if self.context is None:
            raise RuntimeError("Browser session context is not open")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = self.context.request.get(target_url, timeout=self.config.timeout_ms)
        if not response.ok:
            raise RuntimeError(f"Decision download failed with HTTP {response.status} for {target_url}")
        destination.write_bytes(response.body())
        return destination

    def _storage_state_path(self) -> Path | None:
        if self.config.storage_state_path is None:
            return None
        return Path(self.config.storage_state_path)


def create_browser_session(
    *,
    headless: bool = True,
    timeout_ms: int = 30000,
    storage_state_path: str | Path | None = None,
) -> MkriBrowserSession:
    return MkriBrowserSession(
        BrowserSessionConfig(
            headless=headless,
            timeout_ms=timeout_ms,
            storage_state_path=storage_state_path,
        )
    )
