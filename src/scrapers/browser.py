from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mkri_tracking import DEFAULT_USER_AGENT, TrackingAccessBlockedError, _looks_like_cloudflare_challenge


class BrowserAutomationUnavailableError(RuntimeError):
    pass


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
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.page.expect_download(timeout=self.config.timeout_ms) as download_info:
            link_exists = self.page.evaluate(
                """(targetUrl) => {
                    const links = Array.from(document.querySelectorAll('a'));
                    const target = links.find((item) => item.href === targetUrl);
                    if (!target) return false;
                    target.click();
                    return true;
                }""",
                target_url,
            )
            if not link_exists:
                raise FileNotFoundError(f"Decision link not found on current tracking page: {target_url}")
        download = download_info.value
        download.save_as(str(destination))
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
