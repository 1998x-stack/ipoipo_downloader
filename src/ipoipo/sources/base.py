"""Protocol for source adapters and page fetch results."""
from dataclasses import dataclass
from typing import Protocol

from ipoipo.domain.models import Report


@dataclass(frozen=True)
class ListingPage:
    reports: list[Report]
    is_end: bool = False


class ReportSource(Protocol):
    def categories(self) -> dict[str, str]: ...
    def list_page(self, category_id: str, category_name: str, page: int) -> ListingPage: ...
    def resolve(self, post_id: str) -> str: ...
