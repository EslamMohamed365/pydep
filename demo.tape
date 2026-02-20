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

# Panel navigation with Tab
Sleep 1s
Tab
Sleep 600ms
Tab
Sleep 600ms
Tab
Sleep 600ms

# Jump to panels with number keys
Type "1"
Sleep 500ms
Type "2"
Sleep 500ms
Type "3"
Sleep 500ms

# Navigate packages with Vim motions
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

# Switch to sources panel and navigate
Type "2"
Sleep 500ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Enter
Sleep 1s

# Back to all sources
Type "gg"
Sleep 400ms
Enter
Sleep 1s

# Filter mode
Type "3"
Sleep 500ms
Type "/"
Sleep 500ms
Type "httpx"
Sleep 1.5s

# Close filter keeping text
Enter
Sleep 500ms

# Clear filter
Type "/"
Sleep 300ms
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
