# PyDep Demo
# Animated demo of the PyDep TUI dependency manager

Output demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 600
Set Theme "TokyoNight"
Set Padding 10
Set TypingSpeed 80ms
Set PlaybackSpeed 1

# Launch PyDep
Type "uv run python app.py"
Enter
Sleep 3s

# Navigate with Vim motions
Sleep 1s
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "k"
Sleep 400ms

# Jump to bottom with G
Type "G"
Sleep 1s

# Jump to top with gg
Type "gg"
Sleep 1s

# Search mode
Type "/"
Sleep 500ms
Type "httpx"
Sleep 1.5s

# Clear search and return
Ctrl+A
Backspace
Sleep 500ms
Escape
Sleep 1s

# Check outdated packages
Type "o"
Sleep 5s

# Open help
Type "?"
Sleep 2s
Escape
Sleep 1s

# Quit
Type "q"
Sleep 1s
