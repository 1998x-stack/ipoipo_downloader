"""Pure HTML parsing. Never equate network errors with zero results."""
import re
from bs4 import BeautifulSoup

from ipoipo.domain.models import Report


class ParseError(RuntimeError):
    pass


def parse_listing(html: str, category_id: str, category_name: str) -> list[Report]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.wapost.card")
    reports = []
    for card in cards:
        link = card.select_one("h2.multi-ellipsis a[href]")
        if not link:
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        match = re.search(r"/post/(\d+)\.html", href)
        if not match:
            continue
        raw_title = link.get("title")
        title = (raw_title if isinstance(raw_title, str) else link.get_text(strip=True)).strip()
        if not title:
            continue
        img = card.select_one("img.img-cover")
        desc = card.select_one("p.text")
        views = card.select_one("span.view-num")
        date = card.select_one("span.edit")
        count = re.search(r"\d+", views.get_text(strip=True)) if views else None
        thumbnail = img.get("src") if img else ""
        thumbnail = thumbnail if isinstance(thumbnail, str) else ""
        reports.append(Report(
            post_id=match.group(1), title=title, category_id=category_id,
            category_name=category_name,
            detail_url=f"https://ipoipo.cn/post/{match.group(1)}.html",
            publish_date=date.get_text(strip=True) if date else "",
            thumbnail_url=thumbnail,
            description=desc.get_text(strip=True) if desc else "",
            view_count=int(count.group(0)) if count else 0))
    if cards and not reports:
        raise ParseError("Report cards found but none could be parsed: likely selector drift")
    return reports
