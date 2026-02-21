# PyDep Demo
# Cinematic walkthrough of the PyDep TUI dependency manager

Output demo.gif

Set Shell "bash"
Set FontSize 13
Set Width 1400
Set Height 750
Set Theme "TokyoNight"
Set Padding 16
Set TypingSpeed 60ms
Set PlaybackSpeed 1
Set CursorBlink false

# ── Launch ──────────────────────────────────────────────────────
Type "uv run python app.py"
Enter
Sleep 4s

# ── Panel navigation with number keys ───────────────────────────
Sleep 800ms
Type "1"
Sleep 600ms
Type "2"
Sleep 600ms
Type "3"
Sleep 800ms

# ── Vim navigation in Packages ──────────────────────────────────
Type "j"
Sleep 350ms
Type "j"
Sleep 350ms
Type "j"
Sleep 350ms
Type "j"
Sleep 350ms
Type "j"
Sleep 350ms

# Jump to bottom
Type "G"
Sleep 900ms

# Jump to top
Type "gg"
Sleep 900ms

# ── Source filtering ─────────────────────────────────────────────
Type "2"
Sleep 600ms
Type "j"
Sleep 400ms
Enter
Sleep 1200ms

# Back to all sources
Type "gg"
Sleep 400ms
Enter
Sleep 800ms

# ── Filter mode ──────────────────────────────────────────────────
Type "3"
Sleep 600ms
Type "/"
Sleep 500ms
Type "textual"
Sleep 1200ms
Escape
Sleep 800ms

# ── PyPI search ──────────────────────────────────────────────────
Type "p"
Sleep 1s
Type "requests"
Enter
Sleep 4s
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Escape
Sleep 900ms

# ── Check outdated ───────────────────────────────────────────────
Type "o"
Sleep 7s

# ── Help overlay ─────────────────────────────────────────────────
Type "?"
Sleep 2500ms
Escape
Sleep 800ms

# ── Quit ─────────────────────────────────────────────────────────
Type "q"
Sleep 800ms
