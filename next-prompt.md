A modular Python terminal UI for managing project dependencies, inspired by lazygit — dark, sophisticated, and fully keyboard-driven with a Tokyo Night color palette.

**DESIGN SYSTEM (REQUIRED):**
- Platform: Terminal (TUI), Python Textual framework, desktop-only
- Theme: Dark, high-contrast accents on deep backgrounds, subtle glow on focus
- Background: Storm Night (#1a1b26) for main surface
- Surface: Deep Navy (#24283b) for panels, modals, bottom bar
- Highlight: Muted Indigo (#292e42) for hover/selection rows
- Primary Accent: Soft Blue (#7aa2f7) for active panel borders, focused inputs, links
- Success: Jade Green (#9ece6a) for ok buttons, passing status, current-version badges
- Error: Coral Red (#f7768e) for cancel buttons, error toasts, delete confirmations
- Warning: Amber Gold (#e0af68) for filter-active borders, outdated badges, warning toasts
- Secondary Accent: Lavender Purple (#bb9af7) for source-select modals, secondary highlights
- Tertiary Accent: Sky Cyan (#7dcfff) for search modals, info badges
- Text Primary: Cool White (#c0caf5) for all body text
- Text Secondary: Muted Slate (#565f89) for hints, placeholders, disabled labels
- Text Inactive: Dim Gray (#414868) for panel borders when unfocused
- Border: Twilight Gray (#3b4261) for default panel and input borders
- Odd Row: Night Shade (#1e2030) for alternating list backgrounds
- Borders: Rounded (tall/wide), 1px solid default, thick accent for modals
- Typography: Monospace (terminal native), bold for section headers and active items
- Spacing: Dense but readable — 1-line padding inside panels, 0 gaps between panels

**Page Structure:**
1. **Left Column (1/3 width, stacked vertically):**
   - **Status Panel:** Project name, Python version, uv version, venv status, package/source/outdated counts — rounded border, active = blue (#7aa2f7)
   - **Sources Panel:** Filterable list of dependency sources (pyproject.toml, requirements.txt, etc.) — Vim j/k navigation, active source highlighted with accent
   - **Packages Panel:** Scrollable list of all dependencies, showing name + installed version — alternating row backgrounds (#1a1b26 / #1e2030), selection row uses highlight (#292e42)

2. **Right Column (2/3 width, full height):**
   - **Details Panel:** Shows selected package info — name, installed version, latest version, outdated status badge, per-source version map, PyPI summary text

3. **Bottom Hint Bar (full width, 1 row):**
   - Persistent keybinding hints in muted slate (#565f89) on surface (#24283b) — e.g. "Tab:switch  j/k:nav  /:filter  a:add  d:del  u:upd  s:sync  p:search  ?:help"

4. **Modal Overlays (centered, floating over content):**
   - **Add Package Modal:** Input field + version constraint picker (==, >=, ~=) — cyan (#7dcfff) thick border
   - **Search Modal:** Input + scrollable results list with j/k nav — cyan thick border
   - **Confirm Modal:** Yes/No buttons (red/blue) — red (#f7768e) thick border
   - **Help Modal:** Keybinding reference grid — blue (#7aa2f7) thick border
   - **Source Select Modal:** Radio list of sources — purple (#bb9af7) thick border
   - All modals: dark surface background (#24283b), rounded corners, centered on screen

5. **Toast Notifications (bottom-right, floating):**
   - Color-coded borders: error = red, warning = amber, info = blue, success = green
   - Auto-dismiss after 3 seconds

**Interaction & Focus Model:**
- Panel focus cycles via Tab (Status → Sources → Packages → Details → repeat)
- Active panel: blue (#7aa2f7) border glow; inactive panels: default twilight gray (#3b4261)
- Vim motions within lists: j/k up/down, G last, gg first
- Filter mode: typing in filter bar highlights matching packages in real time; border turns amber (#e0af68)
- All actions are keyboard-driven — no mouse interactions, no hover tooltips

**Modular Architecture Constraints:**
- Each panel is an independent widget subclassing a shared PanelWidget base
- Panels communicate through the parent App via message passing, not direct references
- Data layer (Package, DepSource dataclasses) is decoupled from presentation
- Each dependency source has its own parser function — one parser per file format
- PackageManager wraps all uv subprocess calls behind an async interface
- Modals are separate ModalScreen subclasses, not inline DOM manipulation
