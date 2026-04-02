import re
import urllib.parse
from typing import List

import cloudscraper

from app.core.config import settings
from app.log import logger

from .models import SeedHubConfig, SeedHubLinkItem, SeedHubLinksResult, SeedHubSearchItem


class SeedHubService:
    _base_url = "https://www.seedhub.cc"

    def __init__(self, config: SeedHubConfig):
        self._config = config

    def _create_scraper(self):
        return cloudscraper.create_scraper()

    def _request(self, url: str, timeout: int | None = None) -> str:
        scraper = self._create_scraper()
        res = scraper.get(
            url,
            timeout=timeout or self._config.timeout,
            proxies=settings.PROXY if self._config.proxy else None,
        )
        if res.status_code != 200:
            raise Exception(f"HTTP error: {res.status_code}")
        return res.text

    def search(self, keyword: str, limit: int | None = None) -> List[SeedHubSearchItem]:
        actual_limit = limit or self._config.search_limit
        url = f"{self._base_url}/s/{urllib.parse.quote(keyword)}/"
        html = self._request(url)

        movies = re.findall(
            r'title="([^"]+)"[^>]*class="image"[^>]*href="(/movies/\d+)/?"',
            html
        )
        infos = re.findall(
            r"<li>(\d{4}\s*/\s*(?:电影|剧集|动漫)[^<]*)</li>",
            html
        )
        ratings = re.findall(
            r'豆瓣评分:\s*<a[^>]*>([^<]+)</a>',
            html
        )

        results: List[SeedHubSearchItem] = []
        for index, (title, path) in enumerate(movies[:actual_limit]):
            movie_id_match = re.search(r"/movies/(\d+)/?", path)
            movie_id = movie_id_match.group(1) if movie_id_match else "unknown"
            results.append(
                SeedHubSearchItem(
                    id=movie_id,
                    title=title,
                    info=infos[index].strip() if index < len(infos) else "",
                    rating=ratings[index] if index < len(ratings) else "?",
                    url=f"{self._base_url}/movies/{movie_id}/",
                )
            )
        return results

    def get_links(self, movie_id: str, quark_limit: int | None = None) -> SeedHubLinksResult:
        actual_quark_limit = quark_limit or self._config.quark_limit
        normalized_id = movie_id.strip("/").split("/")[-1]
        url = f"{self._base_url}/movies/{normalized_id}/"
        html = self._request(url)

        title_match = re.search(r"<h1[^>]*>.*?#</a>\s*([^<]+)", html)
        title = title_match.group(1).strip() if title_match else "未知标题"

        all_hrefs = re.findall(
            r'href="(/link_start/\?redirect_to=pan_id_\d+&movie_title=[^"]+)"',
            html
        )

        seen = set()
        unique_links = []
        for link in all_hrefs:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        result = SeedHubLinksResult(
            title=title,
            magnet=re.findall(r'(magnet:\?xt=[^\s<"]+)', html),
            thunder=re.findall(r'(thunder://[^\s<"]+)', html),
            ed2k=re.findall(r'(ed2k://[^\s<"]+)', html),
        )

        for link in unique_links:
            context = self._extract_link_context(html, link)
            if not context:
                continue
            link_type = self._extract_link_type(context)
            desc = self._extract_link_desc(context)
            item = SeedHubLinkItem(path=link, desc=desc)

            if "quark" in link_type:
                result.quark.append(item)
            elif "baidu" in link_type:
                result.baidu.append(item)
            elif "alipan" in link_type or "aliyun" in link_type:
                result.aliyun.append(item)
            elif "uc" in link_type:
                result.uc.append(item)
            elif "xunlei" in link_type:
                result.xunlei.append(item)

        result.quark_resolved = self._resolve_quark_links(result.quark[:actual_quark_limit])
        return result

    @staticmethod
    def clean_desc(desc: str, max_len: int = 60) -> str:
        desc = re.sub(r"今天|昨天|提取码[^\s]*", "", desc).strip()
        desc = desc.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return desc[:max_len] if len(desc) > max_len else desc

    @staticmethod
    def _extract_link_context(html: str, link: str) -> str | None:
        escaped_link = re.escape(link)
        pattern = rf'(.{{0,300}}href="{escaped_link}".{{0,100}})'
        match = re.search(pattern, html)
        return match.group(1) if match else None

    @staticmethod
    def _extract_link_type(context: str) -> str:
        match = re.search(r'data-link="([^"]+)"', context)
        return (match.group(1) if match else "unknown").lower()

    @staticmethod
    def _extract_link_desc(context: str) -> str:
        match = re.search(r'title="([^"]+)"', context)
        return match.group(1) if match else ""

    def _resolve_quark_links(self, items: List[SeedHubLinkItem]) -> List[SeedHubLinkItem]:
        scraper = self._create_scraper()
        resolved: List[SeedHubLinkItem] = []

        for item in items:
            if not item.path:
                continue
            try:
                redirect_url = f"{self._base_url}{item.path}"
                response = scraper.get(
                    redirect_url,
                    allow_redirects=True,
                    timeout=min(self._config.timeout, 10),
                    proxies=settings.PROXY if self._config.proxy else None,
                )
                actual_links = re.findall(r'(https?://pan\.quark\.cn[^\s<"]+)', response.text)
                if actual_links:
                    resolved.append(
                        SeedHubLinkItem(
                            path=item.path,
                            desc=item.desc,
                            url=actual_links[0],
                        )
                    )
            except Exception as err:
                logger.warn(f"SeedHub quark resolve failed: {err}")
        return resolved
