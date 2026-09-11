from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DynamicPageSelectors:
    item: str
    title: str
    signal: str | None = None


class SeleniumSocialTrendCollector:
    """Optional adapter for approved JS-only sources; not used in the default graph.

    A URL and selectors must be explicitly configured for a source whose terms allow
    automation. WebDriverWait is used instead of fixed sleeps.
    """

    def __init__(self, driver, timeout: int = 10):
        self.driver = driver
        self.timeout = timeout

    def collect(self, url: str, selectors: DynamicPageSelectors) -> list[dict]:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.support.ui import WebDriverWait

        self.driver.get(url)
        items = WebDriverWait(self.driver, self.timeout).until(
            ec.presence_of_all_elements_located((By.CSS_SELECTOR, selectors.item))
        )
        trends = []
        for item in items:
            title = item.find_element(By.CSS_SELECTOR, selectors.title).text.strip()
            signal_text = ""
            if selectors.signal:
                signal_text = item.find_element(By.CSS_SELECTOR, selectors.signal).text.strip()
            if title:
                trends.append({"topic": title, "signal_text": signal_text, "source": url})
        return trends

