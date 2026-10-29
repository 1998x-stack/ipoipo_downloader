# Offline source fixtures

These synthetic, non-copyright HTML fixtures intentionally resemble the DOM
selectors used by ipoipo.cn. They contain no actual downloaded reports and do
not require network access.

- category_page.html: one valid report card.
- download_page.html: one allowed ZIP link.
- empty_page.html: explicit empty-paged result.

ZIP fixtures are generated in memory in test_artifacts_v3.py and
test_pipeline_v3.py to cover successful multi-file archives, invalid signatures,
path traversal, extraction limits and content hashing.
