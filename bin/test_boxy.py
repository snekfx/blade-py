#!/usr/bin/env python3
"""
Demo script showing Boxy integration with repos.py views
"""

import subprocess
import shutil
import os

def render_with_boxy(content: str, title: str = "", theme: str = "info", header: str = "", width: str = "80") -> str:
    """Render content with boxy if available"""
    boxy_path = shutil.which("boxy")
    if not boxy_path:
        return content

    try:
        cmd = [boxy_path, "--theme", theme]
        if title:
            cmd.extend(["--title", title])
        if header:
            cmd.extend(["--header", header])
        if width:
            cmd.extend(["--width", str(width)])

        result = subprocess.run(
            cmd,
            input=content.encode('utf-8'),
            capture_output=True,
            text=False,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Error: {e}")

    return content

# Test ecosystem statistics output
stats_output = """📈 Overview:
  • Total Repos: 20
  • Hub Using Repos: 0
  • Total Deps: 184
  • Total Packages: 74
  • Git Packages: 1
  • Local Packages: 4
  • Breaking Updates: 23
  • Safe Updates: 124"""

conflicts_output = """Version Conflicts Found:
  • serde: 1.0 vs 1
  • libc: 0.2 vs 0.2.153
  • rand: 0.9 vs 0.9.2
  • criterion: 0.5 vs 0.7"""

outdated_output = """Packages with Updates:
  ⚠️ Breaking: 13
  📦 Minor: 45
  ✅ Patches: 12"""

# Demo different themes
print("\n=== STATS VIEW WITH BOXY ===")
print(render_with_boxy(stats_output, title="📊 Ecosystem Statistics", theme="info", header="Hub Repository Analysis"))

print("\n=== CONFLICTS VIEW WITH BOXY ===")
print(render_with_boxy(conflicts_output, title="⚠️ Version Conflicts", theme="warning", header="Dependency Analysis"))

print("\n=== OUTDATED VIEW WITH BOXY ===")
print(render_with_boxy(outdated_output, title="🔄 Update Summary", theme="success", header="Package Updates"))

# Demo error theme
error_output = """❌ Critical Issues:
  • 5 packages have security vulnerabilities
  • 3 repositories failed to build
  • 2 circular dependencies detected"""

print("\n=== ERROR VIEW WITH BOXY ===")
print(render_with_boxy(error_output, title="🚨 Critical Issues", theme="error", header="System Health Check"))

print("\n\nTo enable Boxy in repos.py, set environment variable:")
print("export REPOS_USE_BOXY=0  # Shell convention: 0=enable, 1=disable")