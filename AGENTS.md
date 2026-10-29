# AGENTS.md — v3 Engineering Contract

Python >=3.11, src-layout package `ipoipo`. The v3 code is under `src/ipoipo/`; legacy top-level modules are retained temporarily. Avoid adding new logic to legacy modules.

## Core commands

```bash
python -m pip install -e ".[dev]"
ruff check src/ipoipo --select E4,E7,E9,F
python -m pytest tests/unit tests/integration tests/e2e tests/property -q
python main.py --stage1 --data-dir /tmp/ipoipo-test
python main.py --stats --data-dir /tmp/ipoipo-test
```

## Non-negotiable invariants

1. No success state before verified files and manifest are atomically published.
2. Each report identity is stable and repeated discovery never resets completed tasks.
3. Failures have bounded retries and explicit terminal states; no infinite retry loop.
4. SQLite task claims and changes use transactions; worker ownership checked before transitions.
5. ZIP members must be size bounded, path-safe and not symlinks.
6. File extensions reflect actual document types; never overwrite two attachments with a common generated name.
7. HTTP must validate HTTPS allowlist and every redirect. Do not attempt to circumvent authentication or authorization.
8. CI uses offline fixtures only; never require live website requests to run tests.
9. A missing artifact or expired lease must recover to an explicit, auditable state.
10. CLI options preserve clear budget and category semantics.

## Review checklist

- Include a regression test for each behavioral change and each error path.
- Run static checks and tests locally or on CI before marking as verified.
- Update architecture/data-contract/recovery docs when changing state or storage.
- Retain backward compatibility where feasible; document breaking changes.
- Never commit downloaded datasets, credential-bearing proxy configs or runtime databases.
