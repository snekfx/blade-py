#!/usr/bin/env python3
"""
Test boxy themes with colored stats content to see how they interact
"""

import subprocess
import shutil

# Static stats output with full original coloring (from repos.py stats command)
stats_output_with_colors = """\033[33m📈 Overview:\033[0m
  \033[36m•\033[0m Total Repos: \033[38;5;10m20\033[0m
  \033[36m•\033[0m Hub Using Repos: \033[38;5;10m0\033[0m
  \033[36m•\033[0m Total Deps: \033[38;5;10m184\033[0m
  \033[36m•\033[0m Total Packages: \033[38;5;10m74\033[0m
  \033[36m•\033[0m Breaking Updates: \033[38;5;10m23\033[0m
  \033[36m•\033[0m Safe Updates: \033[38;5;10m124\033[0m

\033[33m📦 Top 10 Most Used Packages:\033[0m
  rsb                  \033[38;5;10m██████████████████████████████\033[0m (12)
  serde                \033[38;5;10m███████████████████████████\033[0m (11)
  chrono               \033[38;5;10m████████████████████\033[0m (8)
  rand                 \033[38;5;10m███████████████\033[0m (6)

\033[33m⚠️  Issues:\033[0m
  \033[36m•\033[0m Version Conflicts: \033[38;5;9m15\033[0m
  \033[36m•\033[0m Breaking Updates Available: \033[33m10\033[0m

\033[33m🏗️  Hub Integration:\033[0m
  \033[36m•\033[0m Hub Packages: \033[38;5;10m0\033[0m
  \033[36m•\033[0m Hub Gaps: \033[33m62\033[0m"""

def test_theme(theme_name, content):
    """Test a specific boxy theme with colored content"""
    boxy_path = shutil.which("boxy")
    if not boxy_path:
        return f"Boxy not found for theme {theme_name}"

    try:
        cmd = [boxy_path, "--use", theme_name, "--title", f"📊 Stats with {theme_name}", "--width", "80"]

        result = subprocess.run(
            cmd,
            input=content.encode('utf-8'),
            capture_output=True,
            text=False,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.decode('utf-8', errors='replace')
        else:
            return f"Error with {theme_name}: {result.stderr.decode()}"
    except Exception as e:
        return f"Exception with {theme_name}: {e}"

# List of themes to test
themes_to_test = [
    "base",
    "base_rounded",
    "info",
    "warning",
    "success",
    "error",
    "critical",
    "magic",
    "blueprint",
    "debug"
]

print("TESTING BOXY THEMES WITH COLORED STATS CONTENT")
print("=" * 60)
print("Original content has:")
print("- Yellow headers (📈 Overview)")
print("- Blue bullets (•)")
print("- Green values and bars")
print("- Red conflicts")
print("- Various semantic colors")
print()

for theme in themes_to_test:
    print(f"\n{'='*20} THEME: {theme.upper()} {'='*20}")
    result = test_theme(theme, stats_output_with_colors)
    print(result)
    print()

print("\n" + "="*60)
print("ANALYSIS: Check how each theme affects the colored content")
print("- Does it preserve original colors?")
print("- Does it override with theme colors?")
print("- Which themes work best with existing colors?")