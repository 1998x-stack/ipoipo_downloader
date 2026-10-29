"""Category pagination, with explicit end-of-list detection."""
from ipoipo.sources.base import ListingPage
from ipoipo.sources.ipoipo_cn.categories import BASE_URL
from ipoipo.sources.ipoipo_cn.parser import ParseError, parse_listing
from ipoipo.transport.http import FetchError, HttpClient


class ListingClient:
    def __init__(self, http: HttpClient):
        self.http = http

    def page(self, category_id: str, category_name: str, number: int) -> ListingPage:
        if not category_id.isdigit() or number < 1:
            raise ValueError("Invalid category or page")
        url = (f"{BASE_URL}/tags-{category_id}.html" if number == 1
               else f"{BASE_URL}/tags-{category_id}_{number}.html")
        try:
            html = self.http.get_html(url)
        except FetchError as exc:
            if "HTTP 404" in str(exc) or "HTTP 410" in str(exc):
                if number > 1:
                    return ListingPage([], is_end=True)
            raise
        reports = parse_listing(html, category_id, category_name)
        if not reports:
            # An empty first page indicates selector drift or a site problem.
            if number == 1:
                raise ParseError(f"First category page has no recognizable reports: {url}")
            return ListingPage([], is_end=True)
        return ListingPage(reports)
