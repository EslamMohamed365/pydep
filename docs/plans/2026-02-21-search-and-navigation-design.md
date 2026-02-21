# PyPI JSON search + full panel cycling

Date: 2026-02-21
Status: Approved

## Goals
- Fix PyPI search so it works reliably without HTML scraping.
- Use ``requests`` for all PyPI JSON calls.
- Remove obsolete HTTP/HTML search code.
- Make ``Tab``/``Shift+Tab`` cycle all panels, including Details.
- Add a confirmation step after selecting a search result.

## Non-goals
- Fuzzy search or partial matching beyond exact package name.
- ``h``/``l`` panel navigation (explicitly not requested).
- Multiple post-search actions (open docs/download).

## Current issues
- PyPI HTML search returns a Cloudflare “Client Challenge” page, so regex parsing yields no results.
- Details panel is not focusable and is excluded from panel cycling.

## Design

### HTTP + Search
- Replace all ``httpx`` usage with ``requests`` across:
  - ``validate_pypi``
  - ``_fetch_latest_versions``
  - ``_fetch_pypi_metadata``
  - ``SearchPyPIModal._search_pypi``
- Introduce a shared async helper to fetch PyPI JSON using ``requests`` in a thread:
  - ``async def _get_pypi_json(name: str) -> dict[str, Any] | None``
  - Uses ``asyncio.to_thread`` to avoid blocking the event loop.
  - Returns ``None`` for non-200 responses or request errors.
- Search becomes exact-name JSON lookup:
  - If JSON is found, show one result (name/version/summary).
  - Otherwise show “No results found.”
- Remove HTML search parser and related code.
- Drop ``httpx`` dependency from ``pyproject.toml`` and add ``requests``.

### Panel cycling
- Update panel cycle list to include Status, Sources, Packages, Details.
- Make Details panel focusable (``can_focus = True``).
- ``Tab``/``Shift+Tab`` cycle through all panels.
- ``1/2/3`` key jumps remain unchanged for Status/Sources/Packages.

### Search confirm flow
- After selecting a search result, show ``ConfirmModal``:
  - Prompt: “Add <package> to project?”
  - Yes → open AddPackageModal (prefilled).
  - No → return to search modal.

## Error handling
- JSON lookup errors map to status “Network error” and no results.
- 404 or missing data results in “No results found.”

## Testing
- Replace ``mock_httpx`` with ``mock_requests`` in tests.
- Update existing HTTP-related tests to use ``requests`` mocks.
- Add tests for:
  - ``Tab``/``Shift+Tab`` cycling includes Details panel.
  - Search JSON success path (one result).
  - ConfirmModal is shown after selection.
