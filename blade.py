#!/usr/bin/env python3
"""
Rust dependency analyzer - Enhanced with commands for export, review, package analysis, and dependency updates
Commands:
  python repos.py                   # Default analysis view
  python repos.py export            # Export raw data to XDG data directory (~/.local/share/snek/blade/)
  python repos.py review            # Detailed review with latest versions
  python repos.py pkg <package>     # Analyze specific package usage
  python repos.py latest <package>  # Check latest version from crates.io
  python repos.py update <repo> [--dry-run] [--force-commit] [--force]  # Update dependencies in specific repository
  python repos.py eco [--dry-run] [--force-commit] [--force]            # Update dependencies across all repositories

Flags:
  --dry-run        Show what would be updated without making changes
  --force-commit   Automatically commit changes with "auto:hub bump" message
  --force          Bypass git safety checks (main branch requirement and clean working directory)
"""

import os
import sys
try:
    import tomllib
    def load_toml(file_or_string, is_string=False):
        if is_string:
            return tomllib.loads(file_or_string)
        else:
            with open(file_or_string, 'rb') as f:
                return tomllib.load(f)
except ImportError:
    import toml
    def load_toml(file_or_string, is_string=False):
        if is_string:
            return toml.loads(file_or_string)
        else:
            return toml.load(file_or_string)
import json
import argparse
import time
import threading
import signal
import termios
import tty
import io
import hashlib
from pathlib import Path
from collections import defaultdict
from packaging import version
from packaging import version as pkg_version
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass

# ============================================================================
# Logo and Version
# ============================================================================

BLADE_LOGO = """┏┓ ╻  ┏━┓╺┳┓┏━╸
┣┻┓┃  ┣━┫ ┃┃┣╸
┗━┛┗━╸╹ ╹╺┻┛┗━╸py"""


class VersionAction(argparse.Action):
    """Custom version action that displays logo and version info."""

    def __call__(self, parser, namespace, values, option_string=None):
        print(BLADE_LOGO)
        print(f"\nVersion: {__version__} | License: MIT")
        print("Copyright © 2025 Qodeninja/SnekFX")
        print("\n🗡️  Advanced Dependency Management for Rust Ecosystems")
        parser.exit()

# ============================================================================
# Version utilities for proper canonicalization and pre-release handling
# ============================================================================

def canonicalize_version(ver_str):
    """
    Parse and canonicalize a version string.

    Returns a normalized packaging.version.Version object that treats
    equivalent versions like 2.0 and 2.0.0 as equal.

    Args:
        ver_str: Version string (e.g., "2.0", "2.0.0", "1.0.0-rc1")

    Returns:
        packaging.version.Version object or None if parsing fails
    """
    if not ver_str or ver_str == 'path' or 'workspace' in str(ver_str):
        return None

    # Clean up version string
    ver_str = str(ver_str).strip('"').split()[0]

    # Handle leading '='
    if ver_str.startswith('='):
        ver_str = ver_str[1:]

    try:
        # packaging.version.Version automatically normalizes versions
        # so 2.0 and 2.0.0 become the same object
        return pkg_version.parse(ver_str)
    except (pkg_version.InvalidVersion, ValueError):
        return None


def is_prerelease(ver_obj):
    """
    Check if a version is a pre-release (alpha, beta, rc, etc.).

    Args:
        ver_obj: packaging.version.Version object or version string

    Returns:
        True if pre-release, False otherwise
    """
    if isinstance(ver_obj, str):
        parsed = canonicalize_version(ver_obj)
        if not parsed:
            return False
        ver_obj = parsed

    if ver_obj is None:
        return False

    return ver_obj.is_prerelease


def filter_prerelease(versions):
    """
    Filter out pre-release versions from a list.

    Args:
        versions: List of packaging.version.Version objects or version strings

    Returns:
        List of stable versions only
    """
    stable = []
    for ver in versions:
        if isinstance(ver, str):
            parsed = canonicalize_version(ver)
            if parsed and not parsed.is_prerelease:
                stable.append(parsed)
        else:
            if ver and not ver.is_prerelease:
                stable.append(ver)
    return stable


def get_latest_stable(versions):
    """
    Get the latest stable (non-prerelease) version from a list.

    Args:
        versions: List of packaging.version.Version objects or version strings

    Returns:
        Latest stable version or None if no stable versions found
    """
    stable = filter_prerelease(versions)
    if not stable:
        return None

    # packaging.version.Version objects support comparison operators
    return max(stable)


def parse_version_metadata(ver_str):
    """
    Parse version metadata (e.g., v2.0.0-deprecated).

    Args:
        ver_str: Version string possibly with metadata

    Returns:
        Dict with 'version' (Version object) and 'metadata' (string) keys
    """
    if not ver_str:
        return {'version': None, 'metadata': None}

    ver_str = str(ver_str).strip()

    # Handle leading 'v'
    if ver_str.startswith('v'):
        ver_str = ver_str[1:]

    # Check for metadata after hyphen (outside of pre-release markers)
    # e.g., "2.0.0-deprecated" -> version="2.0.0", metadata="deprecated"
    # BUT "2.0.0-rc1" -> this is a pre-release, not metadata

    try:
        parsed = pkg_version.parse(ver_str)

        # If there's a local version identifier, that's our metadata
        if parsed.local:
            return {
                'version': parsed,
                'metadata': parsed.local
            }

        return {
            'version': parsed,
            'metadata': None
        }
    except (pkg_version.InvalidVersion, ValueError):
        return {'version': None, 'metadata': None}


def versions_equal(ver1, ver2):
    """
    Check if two versions are equivalent.

    Args:
        ver1, ver2: Version strings or packaging.version.Version objects

    Returns:
        True if versions are equal, False otherwise
    """
    # Parse if strings
    if isinstance(ver1, str):
        parsed1 = canonicalize_version(ver1)
    else:
        parsed1 = ver1

    if isinstance(ver2, str):
        parsed2 = canonicalize_version(ver2)
    else:
        parsed2 = ver2

    # Handle None cases
    if parsed1 is None or parsed2 is None:
        return parsed1 == parsed2

    # Use packaging's built-in equality (handles 2.0 == 2.0.0)
    return parsed1 == parsed2

# ============================================================================

def get_version():
    """Read version from pyproject.toml or fallback to header comment.

    When deployed, the version is injected as a comment in the script header
    by deploy.sh in the format: # version:X.Y.Z
    """
    # First try pyproject.toml (for development)
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            pyproject_data = load_toml(pyproject_path)
            version = pyproject_data.get('project', {}).get('version')
            if version:
                return version
    except Exception:
        pass

    # Fallback to reading version comment from this script (for deployed version)
    try:
        with open(__file__, 'r') as f:
            for line in f:
                if line.startswith('# version:'):
                    return line.split(':', 1)[1].strip()
                # Only check first ~20 lines of header
                if not line.startswith('#') and line.strip():
                    break
    except Exception:
        pass

    return 'unknown'

__version__ = get_version()
from typing import List, Dict, Set, Optional, Tuple
import shutil
import tempfile

# XDG Base Directory support with snekfx structure
def get_xdg_data_home():
    """Get XDG data directory, preferring XDG_DB_HOME, falling back to XDG_DATA_HOME, defaulting to ~/.local/share"""
    return os.environ.get('XDG_DB_HOME',
                         os.environ.get('XDG_DATA_HOME',
                                       os.path.expanduser('~/.local/share')))

def get_xdg_config_home():
    """Get XDG config directory, defaulting to ~/.config"""
    return os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))

def get_xdg_cache_home():
    """Get XDG cache directory, defaulting to ~/.cache"""
    return os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))

def get_blade_data_dir():
    """Get the blade data directory following snekfx XDG Base Directory specification"""
    data_home = get_xdg_data_home()
    blade_dir = os.path.join(data_home, 'snek', 'blade')
    os.makedirs(blade_dir, exist_ok=True)
    return blade_dir

def get_blade_config_dir():
    """Get the blade config directory following snekfx XDG Base Directory specification"""
    config_home = get_xdg_config_home()
    blade_dir = os.path.join(config_home, 'snek', 'blade')
    os.makedirs(blade_dir, exist_ok=True)
    return blade_dir

def get_blade_cache_dir():
    """Get the blade cache directory following snekfx XDG Base Directory specification"""
    cache_home = get_xdg_cache_home()
    blade_dir = os.path.join(cache_home, 'snek', 'blade')
    os.makedirs(blade_dir, exist_ok=True)
    return blade_dir

def get_data_file_path(filename):
    """Get full path for a data file in the blade data directory"""
    return os.path.join(get_blade_data_dir(), filename)

def get_config_file_path(filename):
    """Get full path for a config file in the blade config directory"""
    return os.path.join(get_blade_config_dir(), filename)

def get_cache_file_path(filename):
    """Get full path for a cache file in the blade cache directory"""
    return os.path.join(get_blade_cache_dir(), filename)

# Boxy integration helper
USE_BOXY = os.environ.get('REPOS_USE_BOXY', '0') == '0'  # Shell convention: 0=true (default enabled), 1=false
BOXY_AVAILABLE = False

def check_boxy_availability():
    """Check if boxy is available and working"""
    global BOXY_AVAILABLE
    if not USE_BOXY:
        return False

    boxy_path = shutil.which("boxy")
    if not boxy_path:
        return False

    # Test if boxy actually works
    try:
        result = subprocess.run(
            [boxy_path, "--version"],
            capture_output=True,
            timeout=2
        )
        BOXY_AVAILABLE = result.returncode == 0
        return BOXY_AVAILABLE
    except:
        BOXY_AVAILABLE = False
        return False

# Check once at startup
check_boxy_availability()

def render_with_boxy(content: str, title: str = "", theme: str = "info", header: str = "", width: str = "max") -> str:
    """Render content with boxy using appropriate themes"""
    if not BOXY_AVAILABLE:
        return content

    boxy_path = shutil.which("boxy")
    if not boxy_path:
        return content

    try:
        cmd = [boxy_path, "--use", theme]
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
    except Exception:
        pass

    return content

# Theme mapping for different command contexts
def get_command_theme(command_type: str, content_type: str = "normal") -> str:
    """Get appropriate boxy theme for command and content type"""
    theme_map = {
        # Stats and general info
        "stats": "blueprint",           # Clean ASCII borders that preserve original colors
        "deps": "base_rounded",         # Clean rounded borders
        "search": "magic",              # Search results
        "graph": "base_rounded",        # Relationships

        # Status-based themes
        "conflicts": "warning",         # Version conflicts
        "outdated_breaking": "critical", # Breaking updates
        "outdated_minor": "warning",    # Minor updates
        "outdated_success": "success",  # Up to date

        # Result types
        "success": "success",
        "error": "error",
        "warning": "warning",
        "debug": "debug",
        "fatal": "fatal"
    }

    return theme_map.get(command_type, "info")

# Get RUST_REPO_ROOT environment variable or auto-detect
RUST_REPO_ROOT = os.environ.get('RUST_REPO_ROOT')
if not RUST_REPO_ROOT:
    # Auto-detect by finding 'rust' directory in the current path
    current_path = Path.cwd()
    for parent in [current_path] + list(current_path.parents):
        if parent.name == 'rust' or (parent / 'rust').exists():
            if parent.name == 'rust':
                RUST_REPO_ROOT = str(parent)
            else:
                RUST_REPO_ROOT = str(parent / 'rust')
            break

    if not RUST_REPO_ROOT:
        # Fallback: try to find rust directory from common patterns
        possible_paths = [
            Path.home() / 'repos' / 'code' / 'rust',
            Path('/home/xnull/repos/code/rust'),
            Path.cwd().parent.parent.parent.parent  # Assume we're deeper in the tree
        ]
        for path in possible_paths:
            if path.exists() and path.name == 'rust':
                RUST_REPO_ROOT = str(path)
                break

# Get HUB_PATH environment variable or auto-detect
# Prioritize HUB_HOME (user's standard var) over HUB_PATH
HUB_PATH = os.environ.get('HUB_HOME') or os.environ.get('HUB_PATH')
if not HUB_PATH and RUST_REPO_ROOT:
    # Try common hub locations
    hub_search_paths = [
        Path(RUST_REPO_ROOT) / "prods" / "oodx" / "hub",  # New location
        Path(RUST_REPO_ROOT) / "oodx" / "projects" / "hub",  # Old location
        Path(RUST_REPO_ROOT) / "oodx" / "hub",
        Path(RUST_REPO_ROOT) / "hub"
    ]
    for hub_path in hub_search_paths:
        if hub_path.exists() and (hub_path / "Cargo.toml").exists():
            HUB_PATH = str(hub_path)
            break

# Legacy color palette from colors.rs
class Colors:
    # Core legacy colors (v0.5.0)
    RED = '\x1B[38;5;9m'      # red - bright red
    GREEN = '\x1B[38;5;10m'   # green - bright green
    YELLOW = '\x1B[33m'       # yellow - standard yellow
    BLUE = '\x1B[36m'         # blue - cyan-ish blue
    PURPLE = '\x1B[38;5;141m' # purple2 - light purple
    CYAN = '\x1B[38;5;14m'    # cyan - bright cyan
    WHITE = '\x1B[38;5;250m'  # white - softer bright white
    LIGHT_GRAY = '\x1B[38;5;245m'  # light gray - between white and gray
    GRAY = '\x1B[38;5;242m'   # grey - medium gray

    # Extended colors for semantic meaning
    ORANGE = '\x1B[38;5;214m' # orange - warnings/attention
    AMBER = '\x1B[38;5;220m'  # amber - golden orange
    EMERALD = '\x1B[38;5;34m' # emerald - pure green for success
    CRIMSON = '\x1B[38;5;196m' # crimson - pure red for critical errors
    RED2 = '\x1B[38;5;124m'    # red2 - darker red for secondary breaking

    # Style modifiers
    BOLD = '\x1B[1m'
    DIM = '\x1B[2m'
    END = '\x1B[0m'
    RESET = '\x1B[0m'

class ProgressSpinner:
    """Progress bar with spinner for showing detailed progress"""
    def __init__(self, message="Working", total=100, fast_mode=False):
        self.message = message
        self.total = total
        self.current = 0
        self.fast_mode = fast_mode
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.idx = 0
        self.stop_spinner = False
        self.spinner_thread = None
        self.max_line_length = 0
        if not fast_mode:
            self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful exit"""
        signal.signal(signal.SIGINT, self._signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, self._signal_handler)  # Termination
        # Note: SIGTSTP (Ctrl+Z) is handled by the shell and suspends the process

    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully"""
        self.stop_spinner = True
        if self.spinner_thread and self.spinner_thread.is_alive():
            # Clean up display
            clear_line = ' ' * (self.max_line_length + 20)
            sys.stdout.write('\r')  # Move to start of current line
            sys.stdout.write('\033[1A')  # Move up one line
            sys.stdout.write(f'\r{clear_line}\n{clear_line}')  # Clear both lines
            sys.stdout.write('\r')  # Move cursor to start
            sys.stdout.write('\033[1A')  # Move up one line
            sys.stdout.flush()

        print(f"\n{Colors.YELLOW}⚠️  Operation interrupted by user{Colors.END}")
        sys.exit(0)

    def _draw_progress_bar(self, width=40):
        """Draw a progress bar"""
        if self.total == 0:
            return "[" + "?" * width + "]"

        filled = int(width * self.current / self.total)
        bar = "█" * filled + "▒" * (width - filled)
        return f"[{bar}]"

    def _get_percentage(self):
        """Get percentage as string"""
        if self.total == 0:
            return "?%"
        return f"{int(100 * self.current / self.total)}%"

    def spin(self):
        first_iteration = True
        while not self.stop_spinner:
            char = self.spinner_chars[self.idx % len(self.spinner_chars)]

            # Progress bar line
            progress_bar = self._draw_progress_bar()
            percentage = self._get_percentage()
            progress_line = f"{Colors.BLUE}{progress_bar}{Colors.END} {Colors.WHITE}{percentage}{Colors.END} ({self.current}/{self.total})"

            # Spinner line
            spinner_line = f"{Colors.CYAN}{char}{Colors.END} {self.message}"

            # Track max length for clearing
            current_length = max(len(progress_line), len(spinner_line))
            self.max_line_length = max(self.max_line_length, current_length)

            if first_iteration:
                # First time, just write the lines
                sys.stdout.write(f'{progress_line}\n\r{spinner_line}')
                first_iteration = False
            else:
                # Move to start of line, clear both lines, then rewrite
                sys.stdout.write('\033[1A')  # Move up to progress line
                sys.stdout.write('\r')  # Move to start of line
                sys.stdout.write('\033[K')  # Clear entire line
                sys.stdout.write(f'{progress_line}\n\r')
                sys.stdout.write('\033[K')  # Clear entire line
                sys.stdout.write(f'{spinner_line}')

            sys.stdout.flush()

            self.idx += 1
            time.sleep(0.1)

    def start(self):
        if self.fast_mode:
            return
        self.stop_spinner = False
        # Save terminal settings and disable canonical mode (but keep signal handling)
        try:
            self.old_terminal_settings = termios.tcgetattr(sys.stdin)
            # Get current settings
            new_settings = termios.tcgetattr(sys.stdin)
            # Disable canonical mode and echo (but keep signal handling)
            new_settings[3] &= ~(termios.ICANON | termios.ECHO)
            termios.tcsetattr(sys.stdin, termios.TCSANOW, new_settings)
        except (termios.error, io.UnsupportedOperation):
            self.old_terminal_settings = None

        # Hide cursor during animation
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()
        self.spinner_thread = threading.Thread(target=self.spin)
        self.spinner_thread.start()

    def update(self, current, message=None):
        """Update progress"""
        if self.fast_mode:
            return
        self.current = current
        if message:
            self.message = message

    def stop(self, final_message=None):
        if self.fast_mode:
            if final_message:
                print(final_message)
            return
        self.stop_spinner = True
        if self.spinner_thread:
            self.spinner_thread.join()

        # Move up to progress line and clear both lines
        sys.stdout.write('\033[1A')  # Move up to progress line
        sys.stdout.write('\r')  # Move to start of line
        clear_line = ' ' * (self.max_line_length + 20)
        sys.stdout.write(f'{clear_line}\n{clear_line}')  # Clear both lines
        sys.stdout.write('\033[1A')  # Move back up to where progress line was
        sys.stdout.write('\r')  # Move to start of line

        # Restore terminal settings
        if hasattr(self, 'old_terminal_settings') and self.old_terminal_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_terminal_settings)
            except (termios.error, io.UnsupportedOperation):
                pass

        # Show cursor again
        sys.stdout.write('\033[?25h')

        if final_message:
            print(final_message)
        sys.stdout.flush()

def parse_version(ver_str):
    """Parse and canonicalize version string.

    Handles workspace and path dependencies, and normalizes version formats
    so that 2.0 and 2.0.0 are treated as equivalent.
    """
    return canonicalize_version(ver_str)

def is_breaking_change(from_version, to_version):
    """Check if version change represents a breaking change according to Rust SemVer"""
    if not from_version or not to_version:
        return False

    from_ver = parse_version(from_version) if isinstance(from_version, str) else from_version
    to_ver = parse_version(to_version) if isinstance(to_version, str) else to_version

    if not from_ver or not to_ver:
        return False

    # Major version bump is always breaking
    if to_ver.major > from_ver.major:
        return True

    # For 0.x versions, minor bump is potentially breaking
    if from_ver.major == 0 and to_ver.minor > from_ver.minor:
        return True

    return False

def get_version_risk(ver):
    """Get risk level for a version"""
    parsed = parse_version(ver) if isinstance(ver, str) else ver
    if not parsed:
        return "unknown", Colors.GRAY

    # Pre-release versions
    if parsed.is_prerelease:
        return "pre-release", Colors.YELLOW

    # 0.x versions are inherently unstable
    if parsed.major == 0:
        return "unstable", Colors.ORANGE

    return "stable", Colors.GREEN

def get_latest_version(package_name):
    """Get latest version from crates.io"""
    try:
        url = f"https://crates.io/api/v1/crates/{package_name}"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data['crate']['max_version']
    except KeyboardInterrupt:
        # Re-raise to let the main handler deal with it
        raise
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError):
        return None

def get_latest_stable_version(package_name):
    """Get latest stable version from crates.io (excluding pre-releases).

    Explicitly verifies returned version is not a pre-release.
    """
    try:
        url = f"https://crates.io/api/v1/crates/{package_name}"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())

            # Use the max_stable_version field if available, otherwise fallback to max_version
            stable_ver = data['crate'].get('max_stable_version') or data['crate']['max_version']

            # Verify it's actually stable (not a pre-release)
            if stable_ver and not is_prerelease(stable_ver):
                return stable_ver

            # If fallback was a pre-release, scan versions list for latest stable
            versions = data['crate'].get('versions', [])
            for ver in versions:
                ver_num = ver.get('num')
                if ver_num and not is_prerelease(ver_num):
                    return ver_num

            # Last resort: return the stable field value even if it looks like prerelease
            return stable_ver

    except KeyboardInterrupt:
        # Re-raise to let the main handler deal with it
        raise
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError):
        return None

def get_parent_repo(cargo_path):
    """Get parent.repo format - parent folder + project name using relative paths"""
    # Use relative path from RUST_REPO_ROOT
    rel_path = get_relative_path(cargo_path)
    rel_cargo_path = Path(rel_path)

    project_name = rel_cargo_path.parent.name
    parent_name = rel_cargo_path.parent.parent.name

    # Handle edge cases
    if parent_name == '.':
        parent_name = 'root'

    return f"{parent_name}.{project_name}"

def find_cargo_files(root_dir):
    """Find all Cargo.toml files, excluding target, ref, _arch, archive, bak, dev, and howto directories"""
    cargo_files = []
    for root, dirs, files in os.walk(root_dir):
        # Get relative path from root_dir for checking
        rel_path = Path(root).relative_to(root_dir) if str(root).startswith(str(root_dir)) else Path(root)
        rel_parts = rel_path.parts if rel_path != Path('.') else []

        # Skip if in ref, howto, or contains _arch/archive/bak/dev
        if rel_parts and (rel_parts[0] == 'ref' or
                         rel_parts[0] == 'howto' or
                         any('_arch' in part or 'archive' in part or 'bak' in part or 'dev' in part for part in rel_parts)):
            dirs[:] = []  # Don't descend into subdirectories
            continue

        # Skip target and backup/dev/archive directories
        dirs[:] = [d for d in dirs if d != 'target' and d != 'ref' and d != 'howto'
                   and '_arch' not in d and 'archive' not in d and 'bak' not in d and 'dev' not in d]

        if 'Cargo.toml' in files:
            cargo_path = Path(root) / 'Cargo.toml'
            cargo_files.append(cargo_path)

    return cargo_files

def get_relative_path(file_path):
    """Convert absolute path to relative path from RUST_REPO_ROOT"""
    if not RUST_REPO_ROOT:
        return str(file_path)

    try:
        abs_path = Path(file_path).resolve()
        rust_root = Path(RUST_REPO_ROOT).resolve()

        # Check if file is under RUST_REPO_ROOT
        if str(abs_path).startswith(str(rust_root)):
            rel_path = abs_path.relative_to(rust_root)
            return str(rel_path)
        else:
            # File is outside RUST_REPO_ROOT, return full path
            return str(file_path)
    except (ValueError, OSError):
        # Fallback to original path if there's any issue
        return str(file_path)

def analyze_dependencies():
    """Main analysis function"""
    if not RUST_REPO_ROOT:
        print(f"{Colors.RED}❌ Could not determine RUST_REPO_ROOT. Please set the environment variable or run from within a rust project directory.{Colors.END}")
        return {}

    rust_dir = Path(RUST_REPO_ROOT)
    if not rust_dir.exists():
        print(f"{Colors.RED}❌ RUST_REPO_ROOT directory does not exist: {rust_dir}{Colors.END}")
        return {}

    print(f"{Colors.BLUE}🔍 Using RUST_REPO_ROOT: {Colors.BOLD}{rust_dir}{Colors.END}")
    cargo_files = find_cargo_files(rust_dir)

    # Data structure: dep_name -> [(parent.repo, version, dep_type, cargo_path), ...]
    dependencies = defaultdict(list)

    print(f"{Colors.CYAN}{Colors.BOLD}🔍 Analyzing {len(cargo_files)} Rust projects...{Colors.END}\n")

    for cargo_path in cargo_files:
        try:
            cargo_data = load_toml(cargo_path)

            parent_repo = get_parent_repo(cargo_path)

            # Parse regular dependencies
            if 'dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dependencies'].items():
                    if isinstance(dep_info, str):
                        # Simple version: dep = "1.0"
                        dependencies[dep_name].append((parent_repo, dep_info, 'dep', cargo_path))
                    elif isinstance(dep_info, dict):
                        # Complex dependency: dep = { version = "1.0", features = [...] }
                        if 'version' in dep_info:
                            dependencies[dep_name].append((parent_repo, dep_info['version'], 'dep', cargo_path))
                        elif 'path' in dep_info:
                            dependencies[dep_name].append((parent_repo, 'path', 'dep', cargo_path))
                        elif 'workspace' in dep_info and dep_info['workspace']:
                            dependencies[dep_name].append((parent_repo, 'workspace', 'dep', cargo_path))

            # Parse dev-dependencies
            if 'dev-dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dev-dependencies'].items():
                    if isinstance(dep_info, str):
                        dependencies[dep_name].append((parent_repo, dep_info, 'dev', cargo_path))
                    elif isinstance(dep_info, dict) and 'version' in dep_info:
                        dependencies[dep_name].append((parent_repo, dep_info['version'], 'dev', cargo_path))

        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Warning: Could not parse {cargo_path}: {e}{Colors.END}")

    return dependencies

def format_version_analysis(dependencies):
    """Format the dependency analysis with colors and columns"""

    # Filter out dependencies with only path/workspace references
    filtered_deps = {}
    for dep_name, usages in dependencies.items():
        version_usages = [(parent_repo, ver, typ, path) for parent_repo, ver, typ, path in usages
                         if ver not in ['path', 'workspace']]
        if version_usages:
            filtered_deps[dep_name] = version_usages

    # Sort by dependency name
    sorted_deps = sorted(filtered_deps.items())

    print(f"{Colors.BLUE}{Colors.BOLD}📊 DEPENDENCY VERSION ANALYSIS{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")

    conflicts_found = 0

    # Load latest versions from data file if it exists
    latest_cache = {}
    data_file = Path(get_data_file_path("deps_data.txt"))
    if data_file.exists():
        print(f"{Colors.GRAY}Loading latest versions from data cache...{Colors.END}\n")
        with open(data_file, 'r') as f:
            for line in f:
                if line.startswith("DEPENDENCY:"):
                    parts = line.strip().split(", LATEST: ")
                    if len(parts) == 2:
                        dep_name = parts[0].replace("DEPENDENCY: ", "")
                        latest_version = parts[1]
                        latest_cache[dep_name] = latest_version
    else:
        print(f"{Colors.GRAY}No cache found - fetching latest versions from crates.io...{Colors.END}")

    for dep_name, usages in sorted_deps:
        # Get unique versions
        versions = set()
        version_map = {}  # version -> [(parent_repo, type), ...]

        for parent_repo, ver_str, dep_type, cargo_path in usages:
            parsed_ver = parse_version(ver_str)
            if parsed_ver:
                versions.add(parsed_ver)
                if parsed_ver not in version_map:
                    version_map[parsed_ver] = []
                version_map[parsed_ver].append((parent_repo, dep_type))

        if not versions:
            continue

        # Get latest version from cache (no API call)
        latest_version = latest_cache.get(dep_name)

        # Check for conflicts (multiple versions)
        has_conflict = len(versions) > 1
        if has_conflict:
            conflicts_found += 1

        # Sort versions
        sorted_versions = sorted(versions)
        min_version = min(sorted_versions) if sorted_versions else None
        max_version = max(sorted_versions) if sorted_versions else None

        # Check for breaking changes in this dependency
        has_breaking = False
        if latest_version and len(versions) > 1:
            has_breaking = is_breaking_change(str(min_version), latest_version)
        elif latest_version and len(versions) == 1:
            has_breaking = is_breaking_change(str(max_version), latest_version)

        # Header with breaking change indicators
        if has_conflict and has_breaking:
            conflict_indicator = f"{Colors.CRIMSON}⚠️ BREAKING CONFLICT"
        elif has_conflict:
            conflict_indicator = f"{Colors.RED}⚠️ CONFLICT"
        elif latest_version and has_breaking:
            conflict_indicator = f"{Colors.ORANGE}⚠️ BREAKING UPDATE"
        else:
            conflict_indicator = f"{Colors.GREEN}✅"

        latest_str = f" (latest: {Colors.CYAN}{latest_version}{Colors.END})" if latest_version else ""
        version_info = f" ({len(versions)} versions)" if has_conflict else ""
        print(f"{conflict_indicator} {Colors.BOLD}{dep_name}{Colors.END}{latest_str}{version_info}")

        # Show versions in columns
        for ver in sorted_versions:
            # Color coding with version risk assessment
            risk_level, risk_color = get_version_risk(ver)

            if len(sorted_versions) > 1:
                if ver == min_version:
                    ver_color = Colors.RED  # Oldest version
                elif ver == max_version:
                    ver_color = Colors.GREEN  # Newest version
                else:
                    ver_color = Colors.YELLOW  # Middle version
            else:
                ver_color = risk_color  # Single version - show risk level

            projects_with_version = version_map[ver]
            projects_str = ', '.join([f"{proj}({typ})" if typ == 'dev' else proj
                                    for proj, typ in projects_with_version])

            # Add risk indicator for unstable/pre-release versions
            risk_level, _ = get_version_risk(ver)
            risk_indicator = ""
            if risk_level == "unstable":
                risk_indicator = f" {Colors.YELLOW}◐{Colors.END}"  # 0.x indicator
            elif risk_level == "pre-release":
                risk_indicator = f" {Colors.YELLOW}◑{Colors.END}"  # pre-release indicator

            print(f"  {ver_color}{str(ver):<12}{Colors.END}{risk_indicator} → {projects_str}")

        print()

    # Summary
    print(f"{Colors.PURPLE}{Colors.BOLD}📈 SUMMARY{Colors.END}")
    print(f"{Colors.PURPLE}{'='*40}{Colors.END}")
    print(f"Total dependencies analyzed: {Colors.BOLD}{len(sorted_deps)}{Colors.END}")
    print(f"Dependencies with version conflicts: {Colors.RED}{Colors.BOLD}{conflicts_found}{Colors.END}")
    print(f"Clean dependencies (single version): {Colors.GREEN}{Colors.BOLD}{len(sorted_deps) - conflicts_found}{Colors.END}")

    # Count breaking change issues
    breaking_conflicts = 0
    breaking_updates = 0
    for dep_name, usages in sorted_deps:
        versions = set()
        for parent_repo, ver_str, dep_type, cargo_path in usages:
            parsed_ver = parse_version(ver_str)
            if parsed_ver:
                versions.add(parsed_ver)

        if versions:
            min_version = min(versions)
            max_version = max(versions)
            latest_version = latest_cache.get(dep_name)

            if len(versions) > 1 and latest_version:
                if is_breaking_change(str(min_version), latest_version):
                    breaking_conflicts += 1
            elif len(versions) == 1 and latest_version:
                if is_breaking_change(str(max_version), latest_version):
                    breaking_updates += 1

    if conflicts_found > 0 or breaking_conflicts > 0 or breaking_updates > 0:
        print(f"\n{Colors.RED}{Colors.BOLD}🚨 Hub integration will resolve {conflicts_found} conflicts!{Colors.END}")
        if breaking_conflicts > 0:
            print(f"{Colors.CRIMSON}{Colors.BOLD}⚠️  {breaking_conflicts} dependencies have BREAKING CHANGE conflicts{Colors.END}")
        if breaking_updates > 0:
            print(f"{Colors.ORANGE}{Colors.BOLD}⚠️  {breaking_updates} dependencies have breaking updates available{Colors.END}")
    else:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✨ No version conflicts detected - ecosystem is clean!{Colors.END}")

def export_raw_data(dependencies):
    """Export raw dependency data to text file"""
    output_file = get_data_file_path("deps_data.txt")

    # Filter dependencies with actual versions
    filtered_deps = {}
    for dep_name, usages in dependencies.items():
        version_usages = [(parent_repo, ver, typ, path) for parent_repo, ver, typ, path in usages
                         if ver not in ['path', 'workspace']]
        if version_usages:
            filtered_deps[dep_name] = version_usages

    total_deps = len(filtered_deps)

    # Start progress spinner
    progress = ProgressSpinner("Initializing export...", total_deps)
    progress.start()

    # Cache for latest versions
    latest_cache = {}
    processed = 0

    try:
        with open(output_file, 'w') as f:
            f.write("Raw Dependency Data Export\n")
            f.write("=" * 50 + "\n\n")

            for dep_name, usages in sorted(filtered_deps.items()):
                processed += 1

                # Update progress with current dependency
                progress.update(processed, f"Fetching latest version for {dep_name}...")

                # Get latest version from crates.io
                if dep_name not in latest_cache:
                    latest_version = get_latest_version(dep_name)
                    latest_cache[dep_name] = latest_version
                else:
                    latest_version = latest_cache[dep_name]

                # Update progress message for writing
                progress.update(processed, f"Writing {dep_name} to file...")

                latest_str = f", LATEST: {latest_version}" if latest_version else ""
                f.write(f"DEPENDENCY: {dep_name}{latest_str}\n")
                for parent_repo, ver_str, dep_type, cargo_path in usages:
                    rel_path = get_relative_path(cargo_path)
                    f.write(f"  {parent_repo:<25} {ver_str:<12} {dep_type:<4} {rel_path}\n")
                f.write("\n")

        # Stop progress and show success
        progress.stop(f"{Colors.GREEN}✅ Raw data exported to {Colors.BOLD}{output_file}{Colors.END} ({total_deps} dependencies)")

    except Exception as e:
        progress.stop(f"{Colors.RED}❌ Export failed: {e}{Colors.END}")
        raise

def detailed_review(dependencies):
    """Show detailed review with latest versions across entire ecosystem"""
    print(f"{Colors.WHITE}{Colors.BOLD}📋 ECOSYSTEM DEPENDENCY REVIEW{Colors.END}")
    print(f"{Colors.GRAY}Status of each dependency across all Rust projects (ignoring hub){Colors.END}")
    print(f"{Colors.GRAY}{'='*80}{Colors.END}\n")

    # Load latest versions from data file if it exists
    latest_cache = {}
    data_file = Path(get_data_file_path("deps_data.txt"))
    if data_file.exists():
        print(f"{Colors.GRAY}Loading latest versions from data cache (run 'export' to refresh)...{Colors.END}\n")
        with open(data_file, 'r') as f:
            for line in f:
                if line.startswith("DEPENDENCY:"):
                    parts = line.strip().split(", LATEST: ")
                    if len(parts) == 2:
                        dep_name = parts[0].replace("DEPENDENCY: ", "")
                        latest_version = parts[1]
                        latest_cache[dep_name] = latest_version
    else:
        print(f"{Colors.YELLOW}⚠️  No data cache found. Run 'repos.py export' first to cache latest versions.{Colors.END}\n")

    # Filter and sort dependencies
    filtered_deps = {}
    for dep_name, usages in dependencies.items():
        version_usages = [(parent_repo, ver, typ, path) for parent_repo, ver, typ, path in usages
                         if ver not in ['path', 'workspace']]
        if version_usages:
            filtered_deps[dep_name] = version_usages

    # Sort by usage count (descending), then alphabetically by package name
    def sort_key(item):
        dep_name, usages = item
        # Count unique repos using this dependency
        repo_count = len(set(parent_repo for parent_repo, _, _, _ in usages))
        return (-repo_count, dep_name)  # Negative for descending order

    sorted_deps = sorted(filtered_deps.items(), key=sort_key)

    # Header
    print(f"{Colors.WHITE}{Colors.BOLD}{'Package':<20} {'#U':<4} {'Ecosystem':<14} {'Latest':<20} {'Breaking'}{Colors.END}")
    print(f"{Colors.GRAY}{'-' * 105}{Colors.END}")

    for dep_name, usages in sorted_deps:
        # Get versions used in ecosystem
        versions = set()
        for parent_repo, ver_str, dep_type, cargo_path in usages:
            parsed_ver = parse_version(ver_str)
            if parsed_ver:
                versions.add(parsed_ver)

        if not versions:
            continue

        sorted_versions = sorted(versions)
        min_version = min(sorted_versions)
        max_version = max(sorted_versions)
        ecosystem_version = str(max_version)

        # Get latest version from cache or fetch if not available
        if dep_name not in latest_cache:
            latest_version = get_latest_version(dep_name)
            latest_cache[dep_name] = latest_version
        else:
            latest_version = latest_cache[dep_name]

        # Status and smart coloring logic
        has_conflict = len(versions) > 1
        latest_str = latest_version if latest_version else "unknown"

        # Check for breaking changes
        has_breaking = False
        if latest_version and has_conflict:
            # Check if update from min to latest would be breaking
            has_breaking = is_breaking_change(str(min_version), latest_version)

        # Get version risk for ecosystem version
        risk_level, risk_color = get_version_risk(max_version)

        # Determine block color for ecosystem version (simplified - breaking info in separate column)
        if has_conflict:
            status_block = f"{Colors.RED}■{Colors.END}"  # Conflict
        elif latest_version and parse_version(latest_version) and parse_version(latest_version) > max_version:
            status_block = f"{Colors.ORANGE}■{Colors.END}"  # Update available
        elif risk_level == "unstable":
            status_block = f"{Colors.YELLOW}◐{Colors.END}"  # 0.x version
        elif risk_level == "pre-release":
            status_block = f"{Colors.YELLOW}◑{Colors.END}"  # Pre-release
        else:
            status_block = f"{Colors.GRAY}■{Colors.END}"  # Stable and current

        # Count repos using this dependency
        repo_count = len(set(parent_repo for parent_repo, _, _, _ in usages))

        # Check for breaking changes
        breaking_status = ""
        if latest_version and latest_str != "unknown":
            if has_conflict:
                # Check if update from min to latest would be breaking
                if is_breaking_change(str(min_version), latest_version):
                    breaking_status = f"{Colors.CRIMSON}BREAKING{Colors.END}"
                else:
                    breaking_status = f"{Colors.GREEN}safe{Colors.END}"
            else:
                # Single version - check if update would be breaking
                if is_breaking_change(str(max_version), latest_version):
                    if parse_version(latest_version) > max_version:
                        breaking_status = f"{Colors.ORANGE}BREAKING{Colors.END}"
                    else:
                        breaking_status = f"{Colors.GRAY}current{Colors.END}"
                else:
                    if parse_version(latest_version) > max_version:
                        breaking_status = f"{Colors.GREEN}safe{Colors.END}"
                    else:
                        breaking_status = f"{Colors.GRAY}current{Colors.END}"
        else:
            breaking_status = f"{Colors.GRAY}unknown{Colors.END}"

        # Smart version coloring - only highlight differences
        # Compare parsed versions to handle "0.9" vs "0.9.0" properly
        ecosystem_parsed = parse_version(ecosystem_version)
        latest_parsed = parse_version(latest_str) if latest_str != "unknown" else None
        versions_match = (ecosystem_parsed and latest_parsed and ecosystem_parsed == latest_parsed)

        if versions_match:
            # Versions match - keep latest gray, but eco still gets block
            eco_with_block = f"{status_block} {Colors.GRAY}{ecosystem_version:<12}{Colors.END}"
            latest_colored = f"{Colors.GRAY}{latest_str:<18}{Colors.END}"
        else:
            # Versions differ - color ecosystem by status, latest in blue
            if has_conflict:
                eco_with_block = f"{status_block} {Colors.RED}{ecosystem_version:<12}{Colors.END}"
            elif latest_version and parse_version(latest_version) and parse_version(latest_version) > max_version:
                eco_with_block = f"{status_block} {Colors.ORANGE}{ecosystem_version:<12}{Colors.END}"
            else:
                eco_with_block = f"{status_block} {Colors.GRAY}{ecosystem_version:<12}{Colors.END}"

            latest_colored = f"{Colors.CYAN}{latest_str:<18}{Colors.END}"

        # Print gray row with block in front of ecosystem version and breaking status
        print(f"{Colors.GRAY}{dep_name:<20} "
              f"{repo_count:<4} "
              f"{Colors.END}{eco_with_block} "
              f"{latest_colored} "
              f"{breaking_status}")

    print(f"\n{Colors.PURPLE}{Colors.BOLD}Legend:{Colors.END}")
    print(f"{Colors.GRAY}■{Colors.END} UPDATED   - Using latest version, no conflicts")
    print(f"{Colors.ORANGE}■{Colors.END} OUTDATED  - Newer version available (safe update)")
    print(f"{Colors.ORANGE}⚠{Colors.END} BREAKING  - Breaking change update available")
    print(f"{Colors.RED}■{Colors.END} CONFLICT  - Multiple versions in ecosystem")
    print(f"{Colors.CRIMSON}⚠{Colors.END} CRITICAL  - Breaking change conflicts")
    print(f"{Colors.YELLOW}◐{Colors.END} UNSTABLE  - 0.x version (minor bumps can break)")
    print(f"{Colors.YELLOW}◑{Colors.END} PREREL    - Pre-release version")
    print(f"\nBreaking: {Colors.CRIMSON}BREAKING{Colors.END} (conflicts), {Colors.ORANGE}BREAKING{Colors.END} (updates), {Colors.GREEN}safe{Colors.END}, {Colors.GRAY}current{Colors.END}")
    print(f"Versions: Only colored when {Colors.ORANGE}ecosystem{Colors.END} ≠ {Colors.CYAN}latest{Colors.END}")

def analyze_package(dependencies, package_name):
    """Analyze specific package usage across ecosystem"""
    if package_name not in dependencies:
        print(f"{Colors.RED}❌ Package '{package_name}' not found in ecosystem{Colors.END}")
        return

    usages = dependencies[package_name]
    version_usages = [(parent_repo, ver, typ, path) for parent_repo, ver, typ, path in usages
                     if ver not in ['path', 'workspace']]

    if not version_usages:
        print(f"{Colors.YELLOW}⚠️  Package '{package_name}' only has path/workspace dependencies{Colors.END}")
        return

    print(f"{Colors.CYAN}{Colors.BOLD}📦 PACKAGE ANALYSIS: {package_name}{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}\n")

    # Get latest version
    latest_version = get_latest_version(package_name)
    if latest_version:
        print(f"{Colors.CYAN}Latest on crates.io: {Colors.BOLD}{latest_version}{Colors.END}\n")

    # Collect versions
    versions = set()
    version_map = {}

    for parent_repo, ver_str, dep_type, cargo_path in version_usages:
        parsed_ver = parse_version(ver_str)
        if parsed_ver:
            versions.add(parsed_ver)
            if parsed_ver not in version_map:
                version_map[parsed_ver] = []
            version_map[parsed_ver].append((parent_repo, dep_type))

    sorted_versions = sorted(versions)
    min_version = min(sorted_versions) if sorted_versions else None
    max_version = max(sorted_versions) if sorted_versions else None

    # Header
    print(f"{Colors.WHITE}{Colors.BOLD}{'Version':<12} {'Type':<6} {'Parent.Repo':<25} {'Status'}{Colors.END}")
    print(f"{Colors.GRAY}{'-' * 60}{Colors.END}")

    for ver in sorted_versions:
        # Color for version (min=red, max=green, middle=yellow)
        if len(sorted_versions) > 1:
            if ver == min_version:
                ver_color = Colors.RED
                status = "OLDEST"
            elif ver == max_version:
                ver_color = Colors.GREEN
                status = "NEWEST"
            else:
                ver_color = Colors.YELLOW
                status = "MIDDLE"
        else:
            ver_color = Colors.WHITE
            status = "ONLY"

        repos_with_version = version_map[ver]
        for parent_repo, dep_type in repos_with_version:
            type_color = Colors.GRAY if dep_type == 'dev' else Colors.WHITE
            print(f"{ver_color}{str(ver):<12}{Colors.END} "
                  f"{type_color}{dep_type:<6}{Colors.END} "
                  f"{Colors.WHITE}{parent_repo:<25}{Colors.END} "
                  f"{ver_color}{status}{Colors.END}")

    # Summary
    print(f"\n{Colors.PURPLE}{Colors.BOLD}Summary for {package_name}:{Colors.END}")
    print(f"Versions in ecosystem: {Colors.BOLD}{len(versions)}{Colors.END}")
    print(f"Total usage count: {Colors.BOLD}{len(version_usages)}{Colors.END}")
    print(f"Repositories using: {Colors.BOLD}{len(set(repo for repo, _, _ in [(r, t, p) for r, v, t, p in version_usages]))}{Colors.END}")

    if len(versions) > 1:
        print(f"{Colors.RED}⚠️  Version conflict detected - Hub will resolve to {max_version}{Colors.END}")
    else:
        print(f"{Colors.GREEN}✅ No version conflicts{Colors.END}")

def analyze_hub_status(dependencies):
    """Analyze hub's current package status"""
    print(f"{Colors.PURPLE}{Colors.BOLD}🎯 HUB PACKAGE STATUS{Colors.END}")
    print(f"{Colors.PURPLE}{'='*80}{Colors.END}\n")

    # Get hub dependencies
    hub_deps = get_hub_dependencies()

    if not hub_deps:
        print(f"{Colors.RED}❌ No hub dependencies found or could not read hub's Cargo.toml{Colors.END}")
        return

    # Load latest versions from cache
    latest_cache = {}
    data_file = Path(get_data_file_path("deps_data.txt"))
    if data_file.exists():
        with open(data_file, 'r') as f:
            for line in f:
                if line.startswith("DEPENDENCY:"):
                    parts = line.strip().split(", LATEST: ")
                    if len(parts) == 2:
                        dep_name = parts[0].replace("DEPENDENCY: ", "")
                        latest_version = parts[1]
                        latest_cache[dep_name] = latest_version

    # Count usage for all packages in ecosystem
    package_usage = {}
    for dep_name, usages in dependencies.items():
        version_usages = [(parent_repo, ver, typ, path) for parent_repo, ver, typ, path in usages
                         if ver not in ['path', 'workspace']]
        if version_usages:
            unique_repos = set(parent_repo.split('.')[1] for parent_repo, _, _, _ in version_usages)
            package_usage[dep_name] = len(unique_repos)

    # Analyze hub packages
    hub_current = []
    hub_outdated = []

    for dep_name, hub_version_str in hub_deps.items():
        hub_version = parse_version(hub_version_str)
        latest_version = parse_version(latest_cache.get(dep_name, ""))
        usage_count = package_usage.get(dep_name, 0)

        if latest_version and hub_version and hub_version < latest_version:
            hub_outdated.append((dep_name, hub_version_str, latest_cache.get(dep_name, "unknown"), usage_count))
        else:
            hub_current.append((dep_name, hub_version_str, latest_cache.get(dep_name, hub_version_str), usage_count))

    # Sort by usage count
    hub_current.sort(key=lambda x: x[3], reverse=True)
    hub_outdated.sort(key=lambda x: x[3], reverse=True)

    # Print current packages in columns
    if hub_current:
        print(f"{Colors.PURPLE}{Colors.BOLD}CURRENT PACKAGES:{Colors.END}")
        print(f"{Colors.WHITE}{'Package':<20} {'Hub Version':<15} {'Latest':<15} {'Usage':<10}{Colors.END}")
        print(f"{Colors.GRAY}{'-' * 60}{Colors.END}")

        for dep_name, hub_ver, latest_ver, usage in hub_current:
            usage_color = Colors.GREEN if usage >= 5 else Colors.WHITE if usage >= 3 else Colors.GRAY
            print(f"  {Colors.WHITE}{dep_name:<20}{Colors.END} "
                  f"{Colors.WHITE}{hub_ver:<15}{Colors.END} "
                  f"{Colors.CYAN}{latest_ver:<15}{Colors.END} "
                  f"{usage_color}({usage} projects){Colors.END}")
        print()

    # Print outdated packages
    if hub_outdated:
        print(f"{Colors.PURPLE}{Colors.BOLD}OUTDATED PACKAGES:{Colors.END}")
        print(f"{Colors.WHITE}{'Package':<20} {'Hub Version':<15} {'Latest':<15} {'Usage':<10}{Colors.END}")
        print(f"{Colors.GRAY}{'-' * 60}{Colors.END}")

        for dep_name, hub_ver, latest_ver, usage in hub_outdated:
            usage_color = Colors.GREEN if usage >= 5 else Colors.WHITE if usage >= 3 else Colors.GRAY
            print(f"  {Colors.WHITE}{dep_name:<20}{Colors.END} "
                  f"{Colors.YELLOW}{hub_ver:<15}{Colors.END} "
                  f"{Colors.CYAN}{latest_ver:<15}{Colors.END} "
                  f"{usage_color}({usage} projects){Colors.END}")
        print()

    # Find opportunities (5+ usage packages not in hub)
    opportunities = []
    for dep_name, usage_count in package_usage.items():
        # Filter: exclude rsb and hub themselves from opportunities
        if usage_count >= 5 and dep_name not in hub_deps and dep_name not in ['rsb', 'hub']:
            latest_ver = latest_cache.get(dep_name, "unknown")
            opportunities.append((dep_name, usage_count, latest_ver))

    opportunities.sort(key=lambda x: x[1], reverse=True)

    # Print opportunities in columns
    if opportunities:
        print(f"{Colors.PURPLE}{Colors.BOLD}PACKAGE OPPORTUNITIES (5+ usage, not in hub):{Colors.END}")
        print(f"{Colors.GRAY}{'-' * 80}{Colors.END}")
        col_width = 30
        cols = 3

        for i in range(0, len(opportunities), cols):
            row = "  "
            for j in range(cols):
                if i + j < len(opportunities):
                    dep_name, usage, latest_ver = opportunities[i + j]
                    text = f"{dep_name}({usage})"
                    colored = f"{Colors.GREEN}{text}{Colors.END}"  # Changed to green to match Gap color
                    # Pad based on actual text length, not colored string
                    padding = " " * max(0, col_width - len(text))
                    row += colored + padding
            print(row.rstrip())
        print()

    # Summary using hub-only mode (no High/Med/Low categories)
    # Convert package_usage to the format expected by calculate_hub_status
    package_consumers_format = {dep_name: (count, []) for dep_name, count in package_usage.items()}
    hub_status = calculate_hub_status(package_consumers_format, hub_deps, latest_cache)

    print_summary_table(hub_status=hub_status, hub_only=True)

def check_latest(package_name):
    """Check latest version of a specific package"""
    print(f"{Colors.CYAN}{Colors.BOLD}🔍 CHECKING LATEST VERSION: {package_name}{Colors.END}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}\n")

    latest_version = get_latest_version(package_name)

    if latest_version:
        print(f"{Colors.CYAN}Latest version on crates.io: {Colors.BOLD}{latest_version}{Colors.END}")
        print(f"{Colors.GRAY}URL: https://crates.io/crates/{package_name}{Colors.END}")
    else:
        print(f"{Colors.RED}❌ Could not fetch latest version for '{package_name}'")
        print(f"{Colors.GRAY}Package may not exist on crates.io or network error{Colors.END}")

def calculate_hub_status(package_consumers, hub_deps, latest_cache):
    """Calculate hub status metrics"""
    hub_current = []  # In hub and up-to-date
    hub_outdated = []  # In hub but outdated
    hub_unused = []   # In hub but not used anywhere
    hub_gap_high = []  # High usage packages not in hub
    hub_unique = []  # All packages not in hub

    # First, check what's actually used in the ecosystem
    for dep_name, (count, _) in package_consumers.items():
        if dep_name in hub_deps:
            hub_version = parse_version(hub_deps[dep_name])
            latest_version = parse_version(latest_cache.get(dep_name, ""))
            if latest_version and hub_version and hub_version < latest_version:
                hub_outdated.append(dep_name)
            else:
                hub_current.append(dep_name)
        else:
            hub_unique.append(dep_name)
            if count >= 5:
                hub_gap_high.append(dep_name)

    # Check for hub packages that aren't used anywhere
    used_packages = set(package_consumers.keys())
    for dep_name in hub_deps:
        if dep_name not in used_packages:
            hub_unused.append(dep_name)

    return hub_current, hub_outdated, hub_unused, hub_gap_high, hub_unique

def print_summary_table(high_usage=None, medium_usage=None, low_usage=None, package_consumers=None, hub_status=None, hub_only=False):
    """Print summary table with package counts and optional hub status"""
    col_width = 12

    # Only show package counts if not hub_only mode
    if not hub_only and high_usage is not None:
        print(f"{Colors.PURPLE}{Colors.BOLD}SUMMARY:{Colors.END}")
        # Package counts
        labels = ["High", "Med", "Low", "Total"]
        values = [len(high_usage), len(medium_usage), len(low_usage), len(package_consumers)]
        colors = [Colors.WHITE, Colors.WHITE, Colors.GRAY, Colors.BOLD]

        row = "  "
        for label in labels:
            row += f"{label:<{col_width}}"
        print(row)

        row = "  "
        for i, (value, color) in enumerate(zip(values, colors)):
            text = str(value)
            colored = f"{color}{text}{Colors.END}"
            padding = " " * (col_width - len(text))
            row += colored + padding
        print(row)

        print()

    # Hub status (if provided)
    if hub_status:
        hub_current, hub_outdated, hub_unused, hub_gap_high, hub_unique = hub_status

        # Use different title if hub_only mode
        title = "HUB STATUS:" if not hub_only else "HUB PACKAGES:"
        print(f"{Colors.PURPLE}{Colors.BOLD}{title}{Colors.END}")

        hub_labels = ["Current", "Outdated", "Gap", "Unused", "Unique"]
        hub_values = [len(hub_current), len(hub_outdated), len(hub_gap_high), len(hub_unused), len(hub_unique)]
        hub_colors = [Colors.BLUE, Colors.ORANGE, Colors.GREEN, Colors.RED, Colors.GRAY]

        row = "  "
        for label in hub_labels:
            row += f"{label:<{col_width}}"
        print(row)

        row = "  "
        for i, (value, color) in enumerate(zip(hub_values, hub_colors)):
            text = str(value)
            colored = f"{color}■{Colors.END} {color}{text}{Colors.END}"
            # Calculate padding based on visible text (■ + space + number)
            visible_len = 1 + 1 + len(text)  # block + space + number
            padding = " " * (col_width - visible_len)
            row += colored + padding
        print(row)

        print()

# Data structures for structured cache
@dataclass
class RepoData:
    repo_id: int
    repo_name: str
    path: str
    parent: str
    last_update: int
    cargo_version: str
    hub_usage: str  # "1.0.0" or "path" or "NONE"
    hub_status: str  # "using", "path", "none"
    is_internal: str = "false"  # "true"/"false" - whether it's internal vs external
    org: str = ""  # Organization/owner from path or metadata
    group: str = ""  # Group/category from path structure
    library_type: str = "project"  # "binary", "library", "workspace", "project"

@dataclass
class DepData:
    dep_id: int
    repo_id: int
    pkg_name: str
    pkg_version: str
    dep_type: str
    features: str

@dataclass
class LatestData:
    pkg_id: int
    pkg_name: str
    latest_version: str
    latest_stable_version: str  # Latest stable version (excluding pre-releases)
    source_type: str  # "crate", "local", "git", "workspace"
    source_value: str  # crates.io version, local path, git repo, or "WORKSPACE"
    hub_version: str  # Hub's version or "NONE"
    hub_status: str   # "current", "outdated", "gap", "none"
    git_status: str = "OK"  # For git deps: "OK", "AUTH_REQUIRED", "NOT_FOUND", "TIMEOUT", "HTTPS_WARNING"

@dataclass
class VersionMapData:
    map_id: int
    dep_id: int
    pkg_id: int
    repo_id: int
    version_state: str
    breaking_type: str
    ecosystem_status: str

@dataclass
class HubInfo:
    """Hub repository information container"""
    path: str
    version: str
    dependencies: Dict[str, str]  # pkg_name -> version
    last_update: int

# Helper functions for data cache generation
def find_all_cargo_files_fast() -> List[Path]:
    """Fast discovery of all Cargo.toml files using find command"""
    if not RUST_REPO_ROOT:
        return []

    try:
        # Use find command for speed, exclude target and backup/dev/archive directories
        cmd = [
            'find', RUST_REPO_ROOT,
            '-name', 'Cargo.toml',
            '-not', '-path', '*/target/*',
            '-not', '-path', '*/ref/*',
            '-not', '-path', '*/howto/*',
            '-not', '-path', '*/_arch/*',
            '-not', '-path', '*/archive/*',
            '-not', '-path', '*/bak/*',
            '-not', '-path', '*/dev/*'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            paths = [Path(line.strip()) for line in result.stdout.strip().split('\n') if line.strip()]
            return paths
        else:
            print(f"{Colors.YELLOW}⚠️  find command failed, falling back to Python search{Colors.END}")
            return find_cargo_files(RUST_REPO_ROOT)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"{Colors.YELLOW}⚠️  find command not available, using Python search{Colors.END}")
        return find_cargo_files(RUST_REPO_ROOT)

def compute_tree_md5(cargo_files: List[Path]) -> str:
    """Compute MD5 hash of the Cargo.toml file list for cache validation.

    This identifies the current state of the repository tree. If the list of
    Cargo.toml files hasn't changed, we can reuse cached data.
    """
    hasher = hashlib.md5()
    # Sort paths for consistent hashing across runs
    for cargo_path in sorted(str(p) for p in cargo_files):
        hasher.update(cargo_path.encode())
    return hasher.hexdigest()


def get_tree_metadata_path() -> str:
    """Get path to tree metadata file (stores MD5 of last scan)"""
    return get_cache_file_path("tree_metadata.json")


def load_tree_metadata() -> Optional[dict]:
    """Load cached tree metadata including MD5 and timestamp"""
    metadata_path = get_tree_metadata_path()
    if not Path(metadata_path).exists():
        return None
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_tree_metadata(cargo_files: List[Path], processing_time: float):
    """Save tree metadata for future cache validation"""
    metadata = {
        'tree_md5': compute_tree_md5(cargo_files),
        'file_count': len(cargo_files),
        'timestamp': time.time(),
        'processing_time': processing_time
    }
    metadata_path = get_tree_metadata_path()
    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    except IOError as e:
        print(f"{Colors.YELLOW}⚠️  Could not save tree metadata: {e}{Colors.END}")


def should_use_cached_data(cargo_files: List[Path]) -> bool:
    """Check if cached data is valid (tree hasn't changed)

    Returns True if:
    1. Cache files exist
    2. Tree MD5 matches current scan
    3. Cached data is not too old (optional: < 1 day)
    """
    # Check if cache files exist
    cache_file = Path(get_data_file_path("deps_cache.tsv"))
    if not cache_file.exists():
        return False

    # Load and compare tree metadata
    metadata = load_tree_metadata()
    if not metadata:
        return False

    current_md5 = compute_tree_md5(cargo_files)
    cached_md5 = metadata.get('tree_md5')

    if current_md5 != cached_md5:
        return False

    # Optional: Check cache age (keep cache valid for up to 24 hours)
    cache_age = time.time() - metadata.get('timestamp', 0)
    if cache_age > 86400:  # 24 hours
        return False

    return True


def detect_internal_library(cargo_data: Dict) -> bool:
    """Detect if a library is internal (not published to crates.io).

    Indicators of internal libraries:
    - publish = false in Cargo.toml
    - License = "None (Private)" or similar
    - Private git repository URLs
    - Path dependencies (workspace members)
    """
    package_info = cargo_data.get('package', {})

    # Check publish flag
    if 'publish' in package_info:
        publish = package_info['publish']
        if isinstance(publish, bool):
            return not publish
        if isinstance(publish, list) and len(publish) == 0:
            return True  # publish = [] means unpublished

    # Check license for "Private" marker
    license_val = str(package_info.get('license', '')).lower()
    if 'private' in license_val or 'none' in license_val:
        return True

    # Check repository for private git servers
    repo_val = package_info.get('repository', '')
    # Repository can be string or dict, handle both
    repo_url = str(repo_val).lower() if repo_val else ""
    if any(marker in repo_url for marker in ['gitlab', 'ssh://', 'internal', 'private']):
        return True

    return False


def extract_org_group(rel_path: str) -> Tuple[str, str]:
    """Extract organization and group from repository path.

    Example paths:
    - prods/meteordb/xstream/Cargo.toml → org="meteordb", group="xstream"
    - code/rust/prods/meteordb/turbine/Cargo.toml → org="meteordb", group="turbine"
    - code/rust/howto/01-pty/cage/Cargo.toml → org="01-pty", group="cage"
    - code/python/snekfx/blade-py/Cargo.toml → org="snekfx", group="blade-py"

    Returns (org, group) tuple. Group is the project directory name.
    """
    # Split path into components and remove Cargo.toml filename
    parts = rel_path.split('/')

    # Remove 'Cargo.toml' if it's the last part
    if parts[-1] == 'Cargo.toml':
        parts = parts[:-1]

    # Now extract org and group from remaining parts
    if len(parts) >= 3:
        # Pattern: .../category/org/project
        # Example: prods/meteordb/xstream → org="meteordb", group="xstream"
        group = parts[-1]  # Last part is project/group
        org = parts[-2]    # Second-to-last is org
        return org, group
    elif len(parts) == 2:
        # Pattern: .../org/project
        return parts[0], parts[1]
    elif len(parts) == 1:
        return "", parts[0]
    else:
        return "", ""


def detect_library_type(cargo_data: Dict) -> str:
    """Detect library type: binary, library, workspace, or project.

    Returns one of: "binary", "library", "workspace", "project"
    """
    package_info = cargo_data.get('package', {})

    # Check if it's a workspace
    if 'workspace' in cargo_data:
        return 'workspace'

    # Check lib section
    if 'lib' in cargo_data:
        return 'library'

    # Check bin sections - if only one binary with default name, might be application
    bins = cargo_data.get('bin', [])
    if bins:
        # Multiple binaries or custom names = application
        if len(bins) > 1:
            return 'binary'
        # Single binary with main.rs = typical binary application
        return 'binary'

    # Default based on what's most common
    return 'project'


def get_repo_info(cargo_path: Path) -> Optional[Dict]:
    """Get repository information from Cargo.toml file"""
    try:
        cargo_data = load_toml(cargo_path)

        # Get basic package info
        package_info = cargo_data.get('package', {})
        repo_name = package_info.get('name', cargo_path.parent.name)
        version = package_info.get('version', '0.0.0')

        # Extract dependencies
        dependencies = {}
        deps_section = cargo_data.get('dependencies', {})
        for dep_name, dep_info in deps_section.items():
            if isinstance(dep_info, str):
                dependencies[dep_name] = dep_info
            elif isinstance(dep_info, dict) and 'version' in dep_info:
                dependencies[dep_name] = dep_info['version']

        # Get last update time
        last_update = int(cargo_path.stat().st_mtime)

        # Get relative path
        rel_path = get_relative_path(cargo_path)

        # Get hub metadata if present
        hub_meta = cargo_data.get('package', {}).get('metadata', {}).get('hub', {})

        return {
            'cargo_path': cargo_path,
            'repo_name': repo_name,
            'version': version,
            'dependencies': dependencies,
            'last_update': last_update,
            'hub_meta': hub_meta,
            'rel_path': rel_path
        }
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Could not load repo info from {cargo_path}: {e}{Colors.END}")
        return None

def get_hub_info() -> Optional[HubInfo]:
    """Get hub repository information using the general repo helper"""
    if not HUB_PATH:
        return None

    # Use configured HUB_PATH
    hub_path = Path(HUB_PATH)
    cargo_path = hub_path / "Cargo.toml"

    if cargo_path.exists():
        repo_info = get_repo_info(cargo_path)
        if repo_info:
            return HubInfo(
                path=repo_info['rel_path'],
                version=repo_info['version'],
                dependencies=repo_info['dependencies'],
                last_update=repo_info['last_update']
            )

    return None

def detect_hub_usage(cargo_path: Path, hub_info: Optional[HubInfo]) -> Tuple[str, str]:
    """Detect if a repo uses hub and return (usage, status)"""
    if not hub_info:
        return "NONE", "none"

    try:
        cargo_data = load_toml(cargo_path)

        deps_section = cargo_data.get('dependencies', {})

        # Check for hub dependency
        if 'hub' in deps_section:
            hub_dep = deps_section['hub']
            if isinstance(hub_dep, str):
                return hub_dep, "using"
            elif isinstance(hub_dep, dict):
                if 'path' in hub_dep:
                    return "path", "path"
                elif 'version' in hub_dep:
                    return hub_dep['version'], "using"
                elif 'workspace' in hub_dep and hub_dep['workspace']:
                    return "workspace", "workspace"

        return "NONE", "none"
    except Exception:
        return "NONE", "none"

def extract_repo_metadata_batch(cargo_files: List[Path], hub_info: Optional[HubInfo]) -> List[RepoData]:
    """Extract repository metadata from all Cargo.toml files, excluding hub itself"""
    repos = []
    repo_id = 100

    for cargo_path in cargo_files:
        repo_info = get_repo_info(cargo_path)
        if not repo_info:
            continue

        # Include hub in analysis (hub is part of the ecosystem)

        # Get parent repo info
        parent_repo = get_parent_repo(cargo_path)

        # Detect hub usage
        hub_usage, hub_status = detect_hub_usage(cargo_path, hub_info)

        # Load cargo data for internal/org/group detection
        try:
            cargo_data = load_toml(cargo_path)
        except:
            cargo_data = {}

        # Detect if internal library
        is_internal = detect_internal_library(cargo_data)

        # Extract org and group from path
        org, group = extract_org_group(repo_info['rel_path'])

        # Detect library type
        library_type = detect_library_type(cargo_data)

        repos.append(RepoData(
            repo_id=repo_id,
            repo_name=repo_info['repo_name'],
            path=repo_info['rel_path'],
            parent=parent_repo.split('.')[0],  # Just parent part
            last_update=repo_info['last_update'],
            cargo_version=repo_info['version'],
            hub_usage=hub_usage,
            hub_status=hub_status,
            is_internal="true" if is_internal else "false",
            org=org,
            group=group,
            library_type=library_type
        ))
        repo_id += 1

    return repos

def extract_dependencies_batch(cargo_files: List[Path]) -> List[DepData]:
    """Extract all dependencies from all Cargo.toml files"""
    deps = []
    dep_id = 1000

    # Create repo_id lookup - only for valid repos (apply same filtering as extract_repo_metadata_batch)
    repo_lookup = {}
    repo_id = 100

    for cargo_path in cargo_files:
        repo_info = get_repo_info(cargo_path)
        if not repo_info:
            continue

        # Check if repo has hub_sync = "false" - skip dependency scanning but include in repo list
        hub_meta = repo_info.get('hub_meta', {})
        if hub_meta.get('hub_sync') == 'false':
            print(f"{Colors.YELLOW}⚠️  Skipping dependency scan for {repo_info['repo_name']} (hub_sync=false){Colors.END}")
            continue

        # Include hub in dependency analysis (consistent with repo metadata)

        repo_lookup[str(cargo_path)] = repo_id
        repo_id += 1

    for cargo_path in cargo_files:
        try:
            # Skip if this cargo file was filtered out during repo_lookup creation
            if str(cargo_path) not in repo_lookup:
                continue

            cargo_data = load_toml(cargo_path)
            current_repo_id = repo_lookup[str(cargo_path)]

            # Process regular dependencies
            if 'dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dependencies'].items():
                    dep_version, features, source_type, source_value = parse_dependency_info(dep_info, cargo_path)
                    if dep_version:  # Include all deps, even path/workspace
                        deps.append(DepData(
                            dep_id=dep_id,
                            repo_id=current_repo_id,
                            pkg_name=dep_name,
                            pkg_version=dep_version,
                            dep_type='dep',
                            features=features
                        ))
                        dep_id += 1

            # Process dev-dependencies
            if 'dev-dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dev-dependencies'].items():
                    dep_version, features, source_type, source_value = parse_dependency_info(dep_info, cargo_path)
                    if dep_version:
                        deps.append(DepData(
                            dep_id=dep_id,
                            repo_id=current_repo_id,
                            pkg_name=dep_name,
                            pkg_version=dep_version,
                            dep_type='dev-dep',
                            features=features
                        ))
                        dep_id += 1

        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Warning: Could not parse dependencies in {cargo_path}: {e}{Colors.END}")

    return deps

def parse_dependency_info(dep_info, cargo_path: Path) -> Tuple[Optional[str], str, str, str]:
    """Parse dependency info and return (version, features, source_type, source_value)"""
    if isinstance(dep_info, str):
        # Simple version string: serde = "1.0"
        return dep_info, "NONE", "crate", dep_info
    elif isinstance(dep_info, dict):
        features = ','.join(dep_info.get('features', [])) or "NONE"

        if 'version' in dep_info:
            # Standard crate: serde = { version = "1.0", features = [...] }
            return dep_info['version'], features, "crate", dep_info['version']
        elif 'path' in dep_info:
            # Local path dependency: my-lib = { path = "../my-lib" }
            path_value = dep_info['path']
            local_version = resolve_local_version(cargo_path, path_value)
            return local_version, features, "local", path_value
        elif 'workspace' in dep_info and dep_info['workspace']:
            # Workspace dependency: serde = { workspace = true }
            workspace_version = resolve_workspace_version(cargo_path, dep_info)
            return workspace_version, features, "workspace", "WORKSPACE"
        elif 'git' in dep_info:
            # Git dependency: some-crate = { git = "https://..." }
            git_repo = dep_info['git']
            git_ref = dep_info.get('rev', dep_info.get('branch', dep_info.get('tag', 'HEAD')))
            # Don't resolve version during parsing - will be resolved in batch_fetch_latest_versions
            # This avoids hanging during the dependency extraction phase
            return "git", features, "git", f"{git_repo}#{git_ref}"
    return None, "NONE", "unknown", "NONE"

def resolve_local_version(cargo_path: Path, relative_path: str) -> str:
    """Resolve version from local path dependency using get_repo_info"""
    try:
        # Resolve relative path from current Cargo.toml location
        local_cargo_path = (cargo_path.parent / relative_path / "Cargo.toml").resolve()
        if local_cargo_path.exists():
            repo_info = get_repo_info(local_cargo_path)
            if repo_info:
                return repo_info['version']
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Could not resolve local version for {relative_path}: {e}{Colors.END}")
    return "LOCAL"

def resolve_workspace_version(cargo_path: Path, dep_info: dict) -> str:
    """Resolve version from workspace dependency (placeholder for now)"""
    # TODO: Implement workspace version resolution
    # Would need to find workspace root and resolve the actual version
    return "WORKSPACE"

def resolve_git_version(git_repo: str, git_ref: str) -> str:
    """Resolve version from git dependency - handles both public and private repos"""
    import subprocess

    try:
        # Method 1: Try GitHub API for public GitHub repos
        if "github.com/" in git_repo:
            repo_path = None
            if git_repo.startswith("git@github.com:"):
                repo_path = git_repo.replace("git@github.com:", "").replace(".git", "")
            elif git_repo.startswith("https://github.com/"):
                repo_path = git_repo.replace("https://github.com/", "").replace(".git", "")
            elif git_repo.startswith("ssh://git@github.com/"):
                repo_path = git_repo.replace("ssh://git@github.com/", "").replace(".git", "")

            if repo_path:
                try:
                    import base64
                    result = subprocess.run([
                        "gh", "api", f"repos/{repo_path}/contents/Cargo.toml",
                        "--jq", ".content"
                    ], capture_output=True, text=True, timeout=10)

                    if result.returncode == 0:
                        content = base64.b64decode(result.stdout.strip()).decode('utf-8')
                        cargo_data = load_toml(content, is_string=True)
                        if 'package' in cargo_data and 'version' in cargo_data['package']:
                            return cargo_data['package']['version']
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
                    pass

        # Method 2: Try git ls-remote for any git repo (SSH or HTTPS)
        # Use GIT_TERMINAL_PROMPT=0 to prevent credential prompts
        try:
            # Test if we can access the repo
            # Set GIT_TERMINAL_PROMPT=0 to disable credential prompts
            git_env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}

            result = subprocess.run(
                ['git', 'ls-remote', '--heads', git_repo],
                capture_output=True,
                text=True,
                timeout=5,
                env=git_env,
                stdin=subprocess.DEVNULL  # Block any credential prompts
            )

            if result.returncode == 0:
                # Repo is accessible - try to get Cargo.toml via git archive
                try:
                    # Use git archive to get just Cargo.toml
                    archive_result = subprocess.run(
                        ['git', 'archive', '--remote', git_repo, git_ref, 'Cargo.toml'],
                        capture_output=True,
                        timeout=5,
                        env=git_env,
                        stdin=subprocess.DEVNULL  # Block any credential prompts
                    )

                    if archive_result.returncode == 0:
                        # Extract and parse Cargo.toml from tar
                        import tarfile
                        import io
                        tar_data = io.BytesIO(archive_result.stdout)
                        with tarfile.open(fileobj=tar_data, mode='r') as tar:
                            cargo_toml = tar.extractfile('Cargo.toml')
                            if cargo_toml:
                                content = cargo_toml.read().decode('utf-8')
                                cargo_data = load_toml(content, is_string=True)
                                if 'package' in cargo_data and 'version' in cargo_data['package']:
                                    return cargo_data['package']['version']
                except Exception:
                    pass

                # Repo accessible but couldn't get version - return ref indicator
                return f"GIT#{git_ref[:8] if len(git_ref) > 8 else git_ref}"
            else:
                # Check if it's an auth issue
                error_msg = result.stderr.lower()
                if 'permission denied' in error_msg or 'authentication failed' in error_msg:
                    return "AUTH_REQUIRED"
                elif 'not found' in error_msg or 'could not read' in error_msg:
                    return "NOT_FOUND"
                else:
                    return "GIT_ERROR"
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except Exception:
            pass

        # Ultimate fallback
        return "0.0.0"

    except Exception as e:
        return "0.0.0"

def collect_unique_packages_with_sources(cargo_files: List[Path]) -> Dict[str, Tuple[str, str]]:
    """Collect unique package names with their source info (source_type, source_value)"""
    packages = {}  # pkg_name -> (source_type, source_value)

    for cargo_path in cargo_files:
        try:
            cargo_data = load_toml(cargo_path)

            # Process regular dependencies
            if 'dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dependencies'].items():
                    dep_version, features, source_type, source_value = parse_dependency_info(dep_info, cargo_path)
                    if dep_version and dep_name not in packages:
                        packages[dep_name] = (source_type, source_value)

            # Process dev-dependencies
            if 'dev-dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dev-dependencies'].items():
                    dep_version, features, source_type, source_value = parse_dependency_info(dep_info, cargo_path)
                    if dep_version and dep_name not in packages:
                        packages[dep_name] = (source_type, source_value)

        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Warning: Could not parse dependencies in {cargo_path}: {e}{Colors.END}")

    return packages

def collect_unique_packages(deps: List[DepData]) -> Set[str]:
    """Collect unique package names (legacy function for compatibility)"""
    packages = set()
    for dep in deps:
        packages.add(dep.pkg_name)
    return packages

def create_local_repo_lookup(repos: List[RepoData]) -> Dict[str, tuple]:
    """Create a lookup map from package names to (path, version)"""
    local_lookup = {}
    for repo in repos:
        # Map repo name to (path, version) for LOCAL flag and version detection
        local_lookup[repo.repo_name] = (repo.path, repo.cargo_version)
    return local_lookup

def batch_fetch_latest_versions(packages_with_sources: Dict[str, Tuple[str, str]], hub_info: Optional[HubInfo] = None, repos: Optional[List[RepoData]] = None, fast_mode: bool = False) -> Dict[str, LatestData]:
    """Batch fetch latest versions for all packages with source information"""
    latest_data = {}
    pkg_id = 200

    # Create local repo lookup for LOCAL flag detection
    local_lookup = create_local_repo_lookup(repos) if repos else {}

    total = len(packages_with_sources)
    progress = ProgressSpinner(f"Fetching latest versions...", total, fast_mode)
    progress.start()

    try:
        processed = 0
        for pkg_name, (source_type, source_value) in sorted(packages_with_sources.items()):
            processed += 1
            progress.update(processed, f"Fetching {pkg_name}...")

            # Fetch version based on source type
            git_dep_status = "OK"  # Default status for non-git deps

            if source_type == "crate":
                latest_version = get_latest_version(pkg_name)
                latest_stable_version = get_latest_stable_version(pkg_name)
            elif source_type == "git":
                # For git dependencies, extract the repo URL and resolve the version
                if "#" in source_value:
                    repo_url, git_ref = source_value.split("#", 1)
                else:
                    repo_url, git_ref = source_value, "main"

                # Check if this git repo is available locally first
                if pkg_name in local_lookup:
                    # Use version from local repo (already parsed in RepoData)
                    local_path, local_version = local_lookup[pkg_name]
                    latest_version = local_version
                    latest_stable_version = local_version
                    git_dep_status = "OK"
                else:
                    # Try to resolve version from remote git (works for both SSH and HTTPS)
                    latest_version = resolve_git_version(repo_url, git_ref)
                    latest_stable_version = latest_version  # For git, stable = latest

                    # Determine git status from version string - warn only on actual failures
                    if latest_version in ["AUTH_REQUIRED", "NOT_FOUND", "TIMEOUT", "GIT_ERROR"]:
                        git_dep_status = latest_version
                    elif latest_version == "0.0.0":
                        # Couldn't resolve version - repo may not exist or be inaccessible
                        git_dep_status = "UNREACHABLE"
                    elif latest_version.startswith("GIT#"):
                        git_dep_status = "NO_VERSION"
                    else:
                        git_dep_status = "OK"
            elif source_type == "local":
                # For local dependencies, we'll need to resolve from the local path
                latest_version = "LOCAL"
                latest_stable_version = "LOCAL"
            elif source_type == "workspace":
                latest_version = "WORKSPACE"
                latest_stable_version = "WORKSPACE"
            else:
                latest_version = "UNKNOWN"
                latest_stable_version = "UNKNOWN"

            if latest_version or source_type != "crate":
                # Check if git repos are also available locally
                final_source_value = source_value
                if source_type == "git" and pkg_name in local_lookup:
                    # Git repo is also available locally - add LOCAL flag with path
                    local_path, _ = local_lookup[pkg_name]
                    final_source_value = f"{source_value} (LOCAL: {local_path})"

                # Check if package is in hub
                if hub_info and pkg_name in hub_info.dependencies:
                    hub_version = hub_info.dependencies[pkg_name]
                    # Determine hub status (only compare for crate dependencies)
                    if source_type == "crate" and latest_version != "N/A":
                        hub_ver = parse_version(hub_version)
                        latest_ver = parse_version(latest_version)
                        if hub_ver and latest_ver:
                            if hub_ver == latest_ver:
                                hub_status = "current"
                            elif hub_ver < latest_ver:
                                hub_status = "outdated"
                            else:
                                hub_status = "ahead"
                        else:
                            hub_status = "unknown"
                    else:
                        hub_status = "local"  # Local/git deps in hub
                else:
                    hub_version = "NONE"
                    hub_status = "gap"

                latest_data[pkg_name] = LatestData(
                    pkg_id=pkg_id,
                    pkg_name=pkg_name,
                    latest_version=latest_version,
                    latest_stable_version=latest_stable_version,
                    source_type=source_type,
                    source_value=final_source_value,
                    hub_version=hub_version,
                    hub_status=hub_status,
                    git_status=git_dep_status
                )
                pkg_id += 1

        progress.stop(f"{Colors.GREEN}✅ Fetched {len(latest_data)} latest versions{Colors.END}")

    except Exception as e:
        progress.stop(f"{Colors.RED}❌ Failed to fetch versions: {e}{Colors.END}")

    return latest_data

def generate_version_analysis(deps: List[DepData], repos: List[RepoData], latest_versions: Dict[str, LatestData]) -> List[VersionMapData]:
    """Generate version analysis mapping"""
    version_maps = []
    map_id = 300

    for dep in deps:
        # Find corresponding repo and latest version data
        repo = next((r for r in repos if r.repo_id == dep.repo_id), None)
        latest = latest_versions.get(dep.pkg_name)

        if repo and latest:
            # Defensive: Ensure pkg_version is a string (handle workspace/local dicts)
            pkg_version = str(dep.pkg_version) if not isinstance(dep.pkg_version, str) else dep.pkg_version

            # Determine version state
            version_state = get_version_stability(pkg_version)

            # Determine breaking type
            breaking_type = "unknown"
            if not pkg_version.startswith(('path:', 'git:', 'workspace:')):
                breaking_type = determine_breaking_type(pkg_version, latest.latest_version)

            # Determine ecosystem status (simplified for now)
            ecosystem_status = "normal"

            version_maps.append(VersionMapData(
                map_id=map_id,
                dep_id=dep.dep_id,
                pkg_id=latest.pkg_id,
                repo_id=dep.repo_id,
                version_state=version_state,
                breaking_type=breaking_type,
                ecosystem_status=ecosystem_status
            ))
            map_id += 1

    return version_maps

def determine_breaking_type(current_version: str, latest_version: str) -> str:
    """Determine if update would be breaking"""
    if is_breaking_change(current_version, latest_version):
        return "BREAKING"
    elif parse_version(latest_version) and parse_version(current_version):
        if parse_version(latest_version) > parse_version(current_version):
            return "safe"
        else:
            return "current"
    return "unknown"

def get_version_stability(version_str: str) -> str:
    """Get version stability status"""
    # Defensive: Convert non-string to string (handle workspace/local dicts)
    if not isinstance(version_str, str):
        version_str = str(version_str)

    if version_str.startswith(('path:', 'git:', 'workspace:')):
        return "local"

    parsed = parse_version(version_str)
    if not parsed:
        return "unknown"

    if parsed.is_prerelease:
        return "pre-release"
    elif parsed.major == 0:
        return "unstable"
    else:
        return "stable"

def write_tsv_cache(repos: List[RepoData], deps: List[DepData], latest_versions: Dict[str, LatestData], version_maps: List[VersionMapData], output_file: str):
    """Write structured TSV cache file"""
    with open(output_file, 'w') as f:
        # Section 0: AGGREGATION METRICS
        f.write("#------ SECTION : AGGREGATION METRICS --------#\n")
        f.write("KEY\tVALUE\n")

        # Repository metrics
        f.write(f"total_repos\t{len(repos)}\n")
        hub_using_repos = len([r for r in repos if r.hub_status in ['using', 'path']])
        f.write(f"hub_using_repos\t{hub_using_repos}\n")

        # Dependency metrics
        f.write(f"total_deps\t{len(deps)}\n")
        f.write(f"total_packages\t{len(latest_versions)}\n")

        # Package source breakdown
        git_packages = len([p for p in latest_versions.values() if p.source_type == 'git'])
        local_packages = len([p for p in latest_versions.values() if p.source_type == 'local'])
        crate_packages = len([p for p in latest_versions.values() if p.source_type == 'crate'])
        workspace_packages = len([p for p in latest_versions.values() if p.source_type == 'workspace'])
        f.write(f"git_packages\t{git_packages}\n")
        f.write(f"local_packages\t{local_packages}\n")
        f.write(f"crate_packages\t{crate_packages}\n")
        f.write(f"workspace_packages\t{workspace_packages}\n")

        # Hub status breakdown
        current_packages = len([p for p in latest_versions.values() if p.hub_status == 'current'])
        outdated_packages = len([p for p in latest_versions.values() if p.hub_status == 'outdated'])
        gap_packages = len([p for p in latest_versions.values() if p.hub_status == 'gap'])
        local_hub_packages = len([p for p in latest_versions.values() if p.hub_status == 'local'])
        f.write(f"hub_current\t{current_packages}\n")
        f.write(f"hub_outdated\t{outdated_packages}\n")
        f.write(f"hub_gap\t{gap_packages}\n")
        f.write(f"hub_local\t{local_hub_packages}\n")

        # Breaking change analysis
        breaking_deps = len([v for v in version_maps if v.breaking_type == 'BREAKING'])
        safe_deps = len([v for v in version_maps if v.breaking_type == 'safe'])
        unknown_deps = len([v for v in version_maps if v.breaking_type == 'unknown'])
        f.write(f"breaking_updates\t{breaking_deps}\n")
        f.write(f"safe_updates\t{safe_deps}\n")
        f.write(f"unknown_updates\t{unknown_deps}\n")

        # Version state analysis
        stable_deps = len([v for v in version_maps if v.version_state == 'stable'])
        unstable_deps = len([v for v in version_maps if v.version_state == 'unstable'])
        f.write(f"stable_versions\t{stable_deps}\n")
        f.write(f"unstable_versions\t{unstable_deps}\n")

        f.write("\n")

    with open(output_file, 'a') as f:
        # Section 1: REPO LIST
        f.write("#------ SECTION : REPO LIST --------#\n")
        f.write("REPO_ID\tREPO_NAME\tPATH\tPARENT\tLAST_UPDATE\tCARGO_VERSION\tHUB_USAGE\tHUB_STATUS\tIS_INTERNAL\tORG\tGROUP\tLIBRARY_TYPE\n")
        for repo in repos:
            f.write(f"{repo.repo_id}\t{repo.repo_name}\t{repo.path}\t{repo.parent}\t{repo.last_update}\t{repo.cargo_version}\t{repo.hub_usage}\t{repo.hub_status}\t{repo.is_internal}\t{repo.org}\t{repo.group}\t{repo.library_type}\n")
        f.write("\n")

        # Section 2: DEPS VERSIONS LIST
        f.write("#------ SECTION : DEP VERSIONS LIST --------#\n")
        f.write("DEP_ID\tREPO_ID\tPKG_NAME\tPKG_VERSION\tDEP_TYPE\tFEATURES\n")
        for dep in deps:
            f.write(f"{dep.dep_id}\t{dep.repo_id}\t{dep.pkg_name}\t{dep.pkg_version}\t{dep.dep_type}\t{dep.features}\n")
        f.write("\n")

        # Section 3: LATEST LIST
        f.write("#------ SECTION : DEP LATEST LIST --------#\n")
        f.write("PKG_ID\tPKG_NAME\tLATEST_VERSION\tLATEST_STABLE_VERSION\tSOURCE_TYPE\tSOURCE_VALUE\tHUB_VERSION\tHUB_STATUS\tGIT_STATUS\n")
        for latest in latest_versions.values():
            f.write(f"{latest.pkg_id}\t{latest.pkg_name}\t{latest.latest_version}\t{latest.latest_stable_version}\t{latest.source_type}\t{latest.source_value}\t{latest.hub_version}\t{latest.hub_status}\t{latest.git_status}\n")
        f.write("\n")

        # Section 4: VERSION MAP LIST
        f.write("#------ SECTION : VERSION MAP LIST --------#\n")
        f.write("MAP_ID\tDEP_ID\tPKG_ID\tREPO_ID\tVERSION_STATE\tBREAKING_TYPE\tECOSYSTEM_STATUS\n")
        for vm in version_maps:
            f.write(f"{vm.map_id}\t{vm.dep_id}\t{vm.pkg_id}\t{vm.repo_id}\t{vm.version_state}\t{vm.breaking_type}\t{vm.ecosystem_status}\n")

# === TSV HYDRATION FUNCTIONS ===

@dataclass
class EcosystemData:
    """Hydrated ecosystem data from TSV cache"""
    aggregation: Dict[str, str]
    repos: Dict[int, RepoData]
    deps: Dict[int, DepData]
    latest: Dict[str, LatestData]  # keyed by pkg_name
    version_maps: Dict[int, VersionMapData]

def hydrate_tsv_cache(cache_file: str = None) -> EcosystemData:
    """Load and parse structured TSV cache into organized data structures"""
    if cache_file is None:
        cache_file = get_data_file_path("deps_cache.tsv")
    if not Path(cache_file).exists():
        raise FileNotFoundError(f"Cache file {cache_file} not found. Run 'repos.py data' to generate it.")

    aggregation = {}
    repos = {}
    deps = {}
    latest = {}
    version_maps = {}

    current_section = None

    with open(cache_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Section headers
            if line.startswith("#------ SECTION :"):
                if "AGGREGATION METRICS" in line:
                    current_section = "aggregation"
                elif "REPO LIST" in line:
                    current_section = "repos"
                elif "DEP VERSIONS LIST" in line:
                    current_section = "deps"
                elif "DEP LATEST LIST" in line:
                    current_section = "latest"
                elif "VERSION MAP LIST" in line:
                    current_section = "version_maps"
                continue

            # Skip header rows
            if "\t" in line and (line.startswith("KEY\t") or line.startswith("REPO_ID\t") or
                                line.startswith("DEP_ID\t") or line.startswith("PKG_ID\t") or
                                line.startswith("MAP_ID\t")):
                continue

            # Parse data rows
            parts = line.split("\t")

            try:
                if current_section == "aggregation" and len(parts) >= 2:
                    key, value = parts[0], parts[1]
                    aggregation[key] = value

                elif current_section == "repos" and len(parts) >= 8:
                    # Handle backward compatibility - old cache files might not have new fields
                    is_internal = parts[8] if len(parts) >= 9 else "false"
                    org = parts[9] if len(parts) >= 10 else ""
                    group = parts[10] if len(parts) >= 11 else ""
                    library_type = parts[11] if len(parts) >= 12 else "project"

                    repo = RepoData(
                        repo_id=int(parts[0]),
                        repo_name=parts[1],
                        path=parts[2],
                        parent=parts[3],
                        last_update=int(parts[4]),
                        cargo_version=parts[5],
                        hub_usage=parts[6],
                        hub_status=parts[7],
                        is_internal=is_internal,
                        org=org,
                        group=group,
                        library_type=library_type
                    )
                    repos[repo.repo_id] = repo

                elif current_section == "deps" and len(parts) >= 6:
                    dep = DepData(
                        dep_id=int(parts[0]),
                        repo_id=int(parts[1]),
                        pkg_name=parts[2],
                        pkg_version=parts[3],
                        dep_type=parts[4],
                        features=parts[5]
                    )
                    deps[dep.dep_id] = dep

                elif current_section == "latest" and len(parts) >= 8:
                    # Handle backward compatibility - old cache files don't have git_status
                    git_status = parts[8] if len(parts) >= 9 else "OK"
                    latest_data = LatestData(
                        pkg_id=int(parts[0]),
                        pkg_name=parts[1],
                        latest_version=parts[2],
                        latest_stable_version=parts[3],
                        source_type=parts[4],
                        source_value=parts[5],
                        hub_version=parts[6],
                        hub_status=parts[7],
                        git_status=git_status
                    )
                    latest[latest_data.pkg_name] = latest_data

                elif current_section == "version_maps" and len(parts) >= 7:
                    vm = VersionMapData(
                        map_id=int(parts[0]),
                        dep_id=int(parts[1]),
                        pkg_id=int(parts[2]),
                        repo_id=int(parts[3]),
                        version_state=parts[4],
                        breaking_type=parts[5],
                        ecosystem_status=parts[6]
                    )
                    version_maps[vm.map_id] = vm

            except (ValueError, IndexError) as e:
                print(f"{Colors.YELLOW}⚠️  Skipping malformed line {line_num}: {line[:50]}... ({e}){Colors.END}")
                continue

    return EcosystemData(
        aggregation=aggregation,
        repos=repos,
        deps=deps,
        latest=latest,
        version_maps=version_maps
    )

# === VIEW HELPER FUNCTIONS ===

def get_hub_repo_id(ecosystem: EcosystemData) -> Optional[int]:
    """Get the hub repository ID from ecosystem data.

    Instead of hard-coding repo_id 103, derive it from RepoData
    by finding the repo with repo_name == "hub".
    """
    for repo in ecosystem.repos.values():
        if repo.repo_name == "hub":
            return repo.repo_id
    return None


def is_local_or_workspace_dep(dep: DepData) -> bool:
    """Check if a dependency is a local or workspace dependency.

    Handles both legacy ('path', 'workspace') and new ('LOCAL', 'WORKSPACE') formats.
    """
    return dep.pkg_version in ['path', 'workspace', 'LOCAL', 'WORKSPACE']


def should_exclude_from_stats(dep: DepData, hub_repo_id: Optional[int]) -> bool:
    """Check if a dependency should be excluded from stats/usage calculations.

    Excludes:
    1. Local/workspace dependencies
    2. Dependencies from the hub repository itself
    """
    # Skip local/workspace dependencies
    if is_local_or_workspace_dep(dep):
        return True

    # Skip dependencies from hub repository
    if hub_repo_id is not None and dep.repo_id == hub_repo_id:
        return True

    return False


def get_package_usage_count(ecosystem: EcosystemData, pkg_name: str) -> int:
    """Get count of repositories using a specific package, excluding hub and local/workspace deps"""
    hub_repo_id = get_hub_repo_id(ecosystem)
    return len([dep for dep in ecosystem.deps.values()
                if dep.pkg_name == pkg_name and not should_exclude_from_stats(dep, hub_repo_id)])

def get_packages_by_usage(ecosystem: EcosystemData) -> List[Tuple[str, int]]:
    """Get packages sorted by usage count, excluding hub and local/workspace deps"""
    hub_repo_id = get_hub_repo_id(ecosystem)
    usage_counts = {}
    for dep in ecosystem.deps.values():
        if not should_exclude_from_stats(dep, hub_repo_id):
            usage_counts[dep.pkg_name] = usage_counts.get(dep.pkg_name, 0) + 1

    return sorted(usage_counts.items(), key=lambda x: (-x[1], x[0]))

def get_version_conflicts(ecosystem: EcosystemData) -> Dict[str, List[str]]:
    """Get packages with version conflicts (multiple versions in ecosystem)"""
    package_versions = {}
    for dep in ecosystem.deps.values():
        if dep.pkg_name not in package_versions:
            package_versions[dep.pkg_name] = set()
        package_versions[dep.pkg_name].add(dep.pkg_version)

    return {pkg: sorted(list(versions)) for pkg, versions in package_versions.items() if len(versions) > 1}

def get_breaking_updates(ecosystem: EcosystemData) -> List[Tuple[str, str, str]]:
    """Get packages with breaking updates available. Returns [(pkg_name, current_version, latest_version)]"""
    breaking = []
    for latest in ecosystem.latest.values():
        if latest.source_type == "crate":  # Only check crates.io packages
            pkg_versions = [dep.pkg_version for dep in ecosystem.deps.values() if dep.pkg_name == latest.pkg_name]
            if pkg_versions:
                current_version = max(pkg_versions, key=parse_version)
                if is_breaking_change(current_version, latest.latest_version):
                    breaking.append((latest.pkg_name, current_version, latest.latest_version))

    return breaking

def get_hub_gaps(ecosystem: EcosystemData) -> List[str]:
    """Get packages used in ecosystem but missing from hub"""
    return [latest.pkg_name for latest in ecosystem.latest.values() if latest.hub_status == "gap"]

def get_repos_using_package(ecosystem: EcosystemData, pkg_name: str) -> List[RepoData]:
    """Get repositories that use a specific package"""
    repo_ids = set()
    for dep in ecosystem.deps.values():
        if dep.pkg_name == pkg_name:
            repo_ids.add(dep.repo_id)

    return [ecosystem.repos[repo_id] for repo_id in repo_ids if repo_id in ecosystem.repos]

def format_aggregation_summary(ecosystem: EcosystemData) -> str:
    """Format aggregation metrics into a readable summary"""
    agg = ecosystem.aggregation
    lines = []
    lines.append(f"📊 **Ecosystem Overview**")
    lines.append(f"   Repositories: {agg.get('total_repos', '?')}")
    lines.append(f"   Dependencies: {agg.get('total_deps', '?')}")
    lines.append(f"   Unique Packages: {agg.get('total_packages', '?')}")
    lines.append(f"")
    lines.append(f"🔗 **Package Sources**")
    lines.append(f"   Crates.io: {agg.get('crate_packages', '?')}")
    lines.append(f"   Git: {agg.get('git_packages', '?')}")
    lines.append(f"   Local: {agg.get('local_packages', '?')}")
    lines.append(f"   Workspace: {agg.get('workspace_packages', '?')}")
    lines.append(f"")
    lines.append(f"🎯 **Hub Integration**")
    lines.append(f"   Using Hub: {agg.get('hub_using_repos', '?')} repos")
    lines.append(f"   Current: {agg.get('hub_current', '?')} packages")
    lines.append(f"   Outdated: {agg.get('hub_outdated', '?')} packages")
    lines.append(f"   Gaps: {agg.get('hub_gap', '?')} packages")
    lines.append(f"")
    lines.append(f"⚠️ **Breaking Changes**")
    lines.append(f"   Breaking Updates: {agg.get('breaking_updates', '?')}")
    lines.append(f"   Safe Updates: {agg.get('safe_updates', '?')}")

    return "\n".join(lines)

def get_hub_dependencies():
    """Get dependencies from hub's Cargo.toml"""
    hub_deps = {}

    if not HUB_PATH:
        return hub_deps

    hub_cargo_path = Path(HUB_PATH) / "Cargo.toml"

    if hub_cargo_path.exists():
        try:
            cargo_data = load_toml(hub_cargo_path)

            # Parse regular dependencies
            if 'dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dependencies'].items():
                    if isinstance(dep_info, dict) and 'version' in dep_info:
                        hub_deps[dep_name] = dep_info['version']
                    elif isinstance(dep_info, str):
                        hub_deps[dep_name] = dep_info

            # Parse dev-dependencies
            if 'dev-dependencies' in cargo_data:
                for dep_name, dep_info in cargo_data['dev-dependencies'].items():
                    if isinstance(dep_info, dict) and 'version' in dep_info:
                        hub_deps[dep_name] = dep_info['version']
                    elif isinstance(dep_info, str):
                        hub_deps[dep_name] = dep_info
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Could not read hub's Cargo.toml: {e}{Colors.END}")

    return hub_deps

def analyze_package_usage(dependencies):
    """Analyze package usage across the ecosystem"""
    print(f"{Colors.PURPLE}{Colors.BOLD}📊 PACKAGE USAGE ANALYSIS{Colors.END}")
    print(f"{Colors.PURPLE}{'='*80}{Colors.END}\n")

    # Get hub dependencies
    hub_deps = get_hub_dependencies()

    # Load latest versions from cache
    latest_cache = {}
    data_file = Path(get_data_file_path("deps_data.txt"))
    if data_file.exists():
        with open(data_file, 'r') as f:
            for line in f:
                if line.startswith("DEPENDENCY:"):
                    parts = line.strip().split(", LATEST: ")
                    if len(parts) == 2:
                        dep_name = parts[0].replace("DEPENDENCY: ", "")
                        latest_version = parts[1]
                        latest_cache[dep_name] = latest_version

    # Count consumers for each package
    package_consumers = {}
    for dep_name, usages in dependencies.items():
        # Filter out path/workspace dependencies
        version_usages = [(parent_repo, ver, typ, path) for parent_repo, ver, typ, path in usages
                         if ver not in ['path', 'workspace']]
        if version_usages:
            # Get unique parent repos
            unique_repos = set(parent_repo.split('.')[1] for parent_repo, _, _, _ in version_usages)
            package_consumers[dep_name] = (len(unique_repos), version_usages)

    # Categorize packages
    high_usage = []  # 5+ consumers
    medium_usage = []  # 3-4 consumers
    low_usage = []  # 1-2 consumers

    for dep_name, (consumer_count, usages) in package_consumers.items():
        if consumer_count >= 5:
            high_usage.append((dep_name, consumer_count, usages))
        elif consumer_count >= 3:
            medium_usage.append((dep_name, consumer_count, usages))
        else:
            low_usage.append((dep_name, consumer_count, usages))

    # Sort each category: hub packages first, then by usage count
    def sort_key(item):
        dep_name, count, _ = item
        in_hub = dep_name in hub_deps
        # Return tuple: (0 if in hub else 1, -count) for sorting
        # This puts hub packages first, then sorts by count descending
        return (0 if in_hub else 1, -count)

    high_usage.sort(key=sort_key)
    medium_usage.sort(key=sort_key)
    low_usage.sort(key=sort_key)

    # Print summary at the top (package counts only for query view)
    print_summary_table(high_usage, medium_usage, low_usage, package_consumers)

    # Print high usage packages (5+) in columns
    if high_usage:
        print(f"{Colors.PURPLE}{Colors.BOLD}HIGH USAGE (5+ projects):{Colors.END}")
        print(f"{Colors.GRAY}{'-' * 80}{Colors.END}")
        col_width = 25
        cols = 3
        for i in range(0, len(high_usage), cols):
            row = "  "
            for j in range(cols):
                if i + j < len(high_usage):
                    dep_name, count, _ = high_usage[i + j]
                    in_hub = dep_name in hub_deps
                    if in_hub:
                        hub_version = parse_version(hub_deps[dep_name])
                        latest_version = parse_version(latest_cache.get(dep_name, ""))
                        star = "*" if latest_version and hub_version and hub_version < latest_version else ""
                        text = f"{dep_name}({count}){star}"
                        colored = f"{Colors.BLUE}{text}{Colors.END}"
                    else:
                        text = f"{dep_name}({count})"
                        colored = f"{Colors.GREEN}{text}{Colors.END}"
                    # Pad based on actual text length, not colored string
                    padding = " " * max(0, col_width - len(text))
                    row += colored + padding
            print(row.rstrip())
        print()

    # Print medium usage packages (3-4) in columns
    if medium_usage:
        print(f"{Colors.PURPLE}{Colors.BOLD}MEDIUM USAGE (3-4 projects):{Colors.END}")
        print(f"{Colors.GRAY}{'-' * 80}{Colors.END}")
        col_width = 25
        cols = 3
        for i in range(0, len(medium_usage), cols):
            row = "  "
            for j in range(cols):
                if i + j < len(medium_usage):
                    dep_name, count, _ = medium_usage[i + j]
                    in_hub = dep_name in hub_deps
                    if in_hub:
                        hub_version = parse_version(hub_deps[dep_name])
                        latest_version = parse_version(latest_cache.get(dep_name, ""))
                        star = "*" if latest_version and hub_version and hub_version < latest_version else ""
                        text = f"{dep_name}({count}){star}"
                        colored = f"{Colors.BLUE}{text}{Colors.END}"
                    else:
                        text = f"{dep_name}({count})"
                        colored = f"{Colors.WHITE}{text}{Colors.END}"
                    # Pad based on actual text length, not colored string
                    padding = " " * max(0, col_width - len(text))
                    row += colored + padding
            print(row.rstrip())
        print()

    # Print low usage packages (1-2) in 3 columns
    if low_usage:
        print(f"{Colors.PURPLE}{Colors.BOLD}LOW USAGE (1-2 projects):{Colors.END}")
        print(f"{Colors.GRAY}{'-' * 80}{Colors.END}")
        col_width = 25
        cols = 3
        for i in range(0, len(low_usage), cols):
            row = "  "
            for j in range(cols):
                if i + j < len(low_usage):
                    dep_name, count, _ = low_usage[i + j]
                    in_hub = dep_name in hub_deps
                    if in_hub:
                        hub_version = parse_version(hub_deps[dep_name])
                        latest_version = parse_version(latest_cache.get(dep_name, ""))
                        star = "*" if latest_version and hub_version and hub_version < latest_version else ""
                        text = f"{dep_name}({count}){star}"
                        colored = f"{Colors.BLUE}{text}{Colors.END}"
                    else:
                        text = f"{dep_name}({count})"
                        colored = f"{Colors.GRAY}{text}{Colors.END}"
                    # Pad based on actual text length, not colored string
                    padding = " " * max(0, col_width - len(text))
                    row += colored + padding
            print(row.rstrip())
        print()

    # Calculate and show hub status at the bottom
    hub_status = calculate_hub_status(package_consumers, hub_deps, latest_cache)
    hub_current, hub_outdated, hub_unused, hub_gap_high, hub_unique = hub_status

    print(f"{Colors.PURPLE}{Colors.BOLD}HUB STATUS:{Colors.END}")
    col_width = 12

    hub_labels = ["Current", "Outdated", "Gap", "Unused", "Unique"]
    hub_values = [len(hub_current), len(hub_outdated), len(hub_gap_high), len(hub_unused), len(hub_unique)]
    hub_colors = [Colors.BLUE, Colors.ORANGE, Colors.GREEN, Colors.RED, Colors.GRAY]

    row = "  "
    for label in hub_labels:
        row += f"{label:<{col_width}}"
    print(row)

    row = "  "
    for i, (value, color) in enumerate(zip(hub_values, hub_colors)):
        text = str(value)
        colored = f"{color}■{Colors.END} {color}{text}{Colors.END}"
        # Calculate padding based on visible text (■ + space + number)
        visible_len = 1 + 1 + len(text)  # block + space + number
        padding = " " * (col_width - visible_len)
        row += colored + padding
    print(row)

def generate_data_cache(dependencies, fast_mode=False):
    """Generate structured TSV data cache for fast view rendering"""
    print(f"{Colors.PURPLE}{Colors.BOLD}📊 GENERATING STRUCTURED DATA CACHE{Colors.END}")
    print(f"{Colors.PURPLE}{'='*80}{Colors.END}\n")

    # Phase 0: Get hub information first (separate container)
    print(f"{Colors.CYAN}Phase 0: Loading hub information...{Colors.END}")
    hub_info = get_hub_info()
    if hub_info:
        print(f"Found hub at {hub_info.path} (v{hub_info.version}) with {len(hub_info.dependencies)} dependencies")
    else:
        print("No hub found in standard locations")

    # Phase 1: Discovery
    print(f"{Colors.CYAN}Phase 1: Discovering Cargo.toml files...{Colors.END}")
    start_time = time.time()
    cargo_files = find_all_cargo_files_fast()
    print(f"Found {len(cargo_files)} Cargo.toml files")

    # MD5 CACHE CHECK: If tree hasn't changed, use cached data
    if should_use_cached_data(cargo_files):
        metadata = load_tree_metadata()
        cache_age_hours = (time.time() - metadata.get('timestamp', 0)) / 3600
        print(f"\n{Colors.GREEN}✨ Cache is valid! Tree structure unchanged.{Colors.END}")
        print(f"   MD5 matches current scan (cached {cache_age_hours:.1f}h ago)")
        print(f"   Previous processing took {metadata.get('processing_time', 0):.1f}s")
        output_file = get_data_file_path("deps_cache.tsv")
        print(f"   Using cached data from {output_file}\n")
        return

    # Phase 2: Extract repo metadata (excluding hub)
    print(f"{Colors.CYAN}Phase 2: Extracting repository metadata...{Colors.END}")
    repos = extract_repo_metadata_batch(cargo_files, hub_info)
    print(f"Processed {len(repos)} repositories (hub excluded)")

    # Phase 3: Extract dependencies
    print(f"{Colors.CYAN}Phase 3: Extracting dependencies...{Colors.END}")
    print(f"  Processing {len(cargo_files)} Cargo.toml files...")
    deps = extract_dependencies_batch(cargo_files)
    print(f"  Extracted {len(deps)} dependencies")
    print(f"  Collecting unique packages...")
    packages_with_sources = collect_unique_packages_with_sources(cargo_files)
    print(f"  Collected {len(packages_with_sources)} unique packages")
    hub_using_repos = len([r for r in repos if r.hub_status in ['using', 'path', 'workspace']])
    print(f"Found {len(deps)} dependency entries, {len(packages_with_sources)} unique packages, {hub_using_repos} repos using hub")

    # Phase 4: Batch fetch latest versions with source info
    print(f"{Colors.CYAN}Phase 4: Fetching latest versions...{Colors.END}")
    latest_versions = batch_fetch_latest_versions(packages_with_sources, hub_info, repos, fast_mode)
    print(f"Fetched latest versions for {len(latest_versions)} packages")

    # Phase 5: Generate analysis data
    print(f"{Colors.CYAN}Phase 5: Analyzing version status...{Colors.END}")
    version_maps = generate_version_analysis(deps, repos, latest_versions)
    print(f"Generated {len(version_maps)} version analysis entries")

    # Phase 6: Write TSV cache
    output_file = get_data_file_path("deps_cache.tsv")
    print(f"{Colors.CYAN}Phase 6: Writing cache to {output_file}...{Colors.END}")
    write_tsv_cache(repos, deps, latest_versions, version_maps, output_file)

    # Save tree metadata for future cache validation
    processing_time = time.time() - start_time
    save_tree_metadata(cargo_files, processing_time)

    print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Data cache generated: {output_file}{Colors.END}")
    print(f"   Processed in {processing_time:.2f}s")

# ============================================================================
# OPTIMIZED VIEW FUNCTIONS - Using hydrated TSV data for lightning-fast analysis
# ============================================================================

def view_conflicts(ecosystem: EcosystemData) -> None:
    """Lightning-fast version conflict analysis using hydrated data

    Replaces format_version_analysis() with ~100x performance improvement
    """
    print(f"{Colors.CYAN}{Colors.BOLD}🔍 VERSION CONFLICT ANALYSIS{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")

    conflicts = {}

    # Group deps by package name using pre-indexed data (instant lookup)
    for dep_id, dep in ecosystem.deps.items():
        if dep.pkg_name not in conflicts:
            conflicts[dep.pkg_name] = []

        repo = ecosystem.repos[dep.repo_id]
        conflicts[dep.pkg_name].append({
            'repo': repo.repo_name,
            'version': dep.pkg_version,
            'type': dep.dep_type,
            'repo_parent': repo.parent
        })

    # Filter to only packages with conflicts (>1 version)
    conflict_packages = {k: v for k, v in conflicts.items()
                        if len(set(item['version'] for item in v)) > 1}

    if not conflict_packages:
        print(f"\n{Colors.GREEN}✅ No version conflicts found in ecosystem!{Colors.END}")
        return

    print(f"\n{Colors.RED}📊 Found {len(conflict_packages)} packages with version conflicts:{Colors.END}")

    # Sort by package name for consistent output
    for pkg_name in sorted(conflict_packages.keys()):
        usages = conflict_packages[pkg_name]
        versions = set(item['version'] for item in usages)
        latest_info = ecosystem.latest.get(pkg_name)

        # For local/git dependencies, use the highest version actually in use
        # instead of the potentially outdated latest from external sources
        has_local_versions = any(not v.startswith(('path:', 'git:', 'workspace:')) and v not in ['LOCAL', 'WORKSPACE']
                               for v in versions)

        if has_local_versions and latest_info and latest_info.source_type in ['git', 'local']:
            # Use the maximum version actually in use for local packages
            numeric_versions = []
            for v in versions:
                if not v.startswith(('path:', 'git:', 'workspace:')) and v not in ['LOCAL', 'WORKSPACE']:
                    parsed_v = parse_version(v)
                    if parsed_v:
                        numeric_versions.append((v, parsed_v))

            if numeric_versions:
                latest_version = max(numeric_versions, key=lambda x: x[1])[0]
            else:
                latest_version = latest_info.latest_version if latest_info else "unknown"
        else:
            latest_version = latest_info.latest_version if latest_info else "unknown"

        print(f"\n{Colors.YELLOW}{Colors.BOLD}📦 {pkg_name}{Colors.END} (latest: {Colors.GREEN}{latest_version}{Colors.END})")
        print(f"{Colors.GRAY}   {'Version':<15} Repositories{Colors.END}")
        print(f"{Colors.GRAY}   {'-'*50}{Colors.END}")

        # Group by version for structured display
        by_version = {}
        for usage in usages:
            ver = usage['version']
            if ver not in by_version:
                by_version[ver] = []
            by_version[ver].append(usage)

        # Sort versions (handle different version formats)
        try:
            sorted_versions = sorted(by_version.keys(), key=lambda x: [int(i) if i.isdigit() else i for i in x.split('.')])
        except:
            sorted_versions = sorted(by_version.keys())

        for version in sorted_versions:
            repos_using = by_version[version]
            repo_names = sorted([f"{item['repo']}" for item in repos_using])
            dep_types = sorted(set(item['type'] for item in repos_using))

            # For LOCAL dependencies, try to resolve actual version
            display_version = version
            if version == "LOCAL":
                # Try to resolve from first repo using this LOCAL dep
                first_repo = repos_using[0]
                repo_obj = None
                for repo_id, repo in ecosystem.repos.items():
                    if repo.repo_name == first_repo['repo']:
                        repo_obj = repo
                        break

                if repo_obj:
                    # Find the dependency entry to get the path
                    for dep_id, dep in ecosystem.deps.items():
                        if dep.repo_id == repo_obj.repo_id and dep.pkg_name == pkg_name and dep.pkg_version == "LOCAL":
                            # Try to resolve using the path from TSV or attempt resolution
                            display_version = f"LOCAL (path issue)"
                            break

            # Color code version based on currency
            version_color = Colors.GREEN if display_version == latest_version else Colors.YELLOW if 'LOCAL' not in display_version else Colors.BLUE

            version_str = f"{version_color}{display_version:<15}{Colors.END}"
            repo_str = f"{Colors.WHITE}{', '.join(repo_names)}{Colors.END}"
            type_str = f"{Colors.GRAY}({', '.join(dep_types)}){Colors.END}"

            print(f"   {version_str} {repo_str} {type_str}")

    # Summary statistics
    total_conflicts = sum(len(set(item['version'] for item in usages)) for usages in conflict_packages.values())
    print(f"\n{Colors.PURPLE}{Colors.BOLD}Conflict Summary:{Colors.END}")
    print(f"  Packages with conflicts: {Colors.BOLD}{len(conflict_packages)}{Colors.END}")
    print(f"  Total version variants: {Colors.BOLD}{total_conflicts}{Colors.END}")
    print(f"  Ecosystem health: {Colors.YELLOW}⚠️  Requires attention{Colors.END}")


def view_repos(ecosystem: EcosystemData) -> None:
    """Lightning-fast repository listing using hydrated data"""
    print(f"{Colors.CYAN}{Colors.BOLD}🗂️  RUST ECOSYSTEM REPOSITORIES{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")

    repos_count = len(ecosystem.repos)
    if repos_count == 0:
        print(f"\n{Colors.YELLOW}⚠️  No repositories found in ecosystem{Colors.END}")
        return

    print(f"\n{Colors.GREEN}📊 Found {repos_count} repositories in ecosystem:{Colors.END}")

    # Count dependencies per repo for additional info
    deps_per_repo = {}
    for dep in ecosystem.deps.values():
        repo_id = dep.repo_id
        if repo_id not in deps_per_repo:
            deps_per_repo[repo_id] = 0
        deps_per_repo[repo_id] += 1

    # Group repos by parent project like conflicts view does
    by_parent = {}
    for repo_id, repo in ecosystem.repos.items():
        parent = repo.parent or "standalone"
        if parent not in by_parent:
            by_parent[parent] = []
        by_parent[parent].append((repo_id, repo))

    # Display repos grouped by parent with beautiful formatting like conflicts
    for parent in sorted(by_parent.keys()):
        repos_in_parent = by_parent[parent]

        if parent == "standalone":
            print(f"\n{Colors.PURPLE}{Colors.BOLD}📁 Standalone Projects:{Colors.END}")
        else:
            print(f"\n{Colors.PURPLE}{Colors.BOLD}📁 {parent}:{Colors.END}")

        print(f"{Colors.GRAY}   {'Repository':<20} {'Version':<12} {'Dependencies':<12} {'Path'}{Colors.END}")
        print(f"{Colors.GRAY}   {'-'*70}{Colors.END}")

        for repo_id, repo in sorted(repos_in_parent, key=lambda x: x[1].repo_name):
            repo_name = f"{repo.repo_name:<20}"
            version = f"{repo.cargo_version or 'unknown':<12}"
            dep_count = deps_per_repo.get(repo_id, 0)
            deps_str = f"{dep_count} deps"
            deps_colored = f"{Colors.BLUE}{deps_str:<12}{Colors.END}" if dep_count > 0 else f"{Colors.GRAY}{deps_str:<12}{Colors.END}"
            path_str = f"{Colors.WHITE}{repo.path}{Colors.END}"

            print(f"   {Colors.WHITE}{repo_name}{Colors.END} {Colors.GREEN}{version}{Colors.END} {deps_colored} {path_str}")

    # Summary statistics like conflicts view
    total_deps = sum(deps_per_repo.values())
    avg_deps = total_deps / repos_count if repos_count > 0 else 0

    print(f"\n{Colors.PURPLE}{Colors.BOLD}Repository Summary:{Colors.END}")
    print(f"  Total repositories: {Colors.BOLD}{repos_count}{Colors.END}")
    print(f"  Total dependencies: {Colors.BOLD}{total_deps}{Colors.END}")
    print(f"  Average deps per repo: {Colors.BOLD}{avg_deps:.1f}{Colors.END}")
    print(f"  Parent projects: {Colors.BOLD}{len(by_parent)}{Colors.END}")


def view_package_detail(ecosystem: EcosystemData, pkg_name: str) -> None:
    """Lightning-fast package analysis using hydrated data

    Replaces analyze_package() with instant lookup performance
    """
    print(f"{Colors.CYAN}{Colors.BOLD}📦 PACKAGE ANALYSIS: {pkg_name}{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")

    if pkg_name not in ecosystem.latest:
        print(f"{Colors.RED}❌ Package '{pkg_name}' not found in ecosystem{Colors.END}")
        return

    latest_info = ecosystem.latest[pkg_name]

    # Get all usages using indexed data (instant lookup)
    usages = [dep for dep in ecosystem.deps.values() if dep.pkg_name == pkg_name]

    if not usages:
        print(f"{Colors.YELLOW}⚠️  Package found in latest versions but not used in any repos{Colors.END}")
        return

    print(f"\n{Colors.CYAN}Latest on crates.io: {Colors.BOLD}{latest_info.latest_version}{Colors.END}")

    # Table header matching legacy format
    print(f"\n{Colors.WHITE}{Colors.BOLD}Version      Type   Parent.Repo               Status{Colors.END}")
    print(f"{Colors.GRAY}------------------------------------------------------------{Colors.END}")

    # Group by repository and format like legacy
    by_repo = {}
    for dep in usages:
        repo_id = dep.repo_id
        if repo_id not in by_repo:
            by_repo[repo_id] = []
        by_repo[repo_id].append(dep)

    # Build table rows
    for repo_id, repo_deps in sorted(by_repo.items()):
        repo = ecosystem.repos[repo_id]

        for dep in repo_deps:
            # Format version (left-aligned, 12 chars)
            version_str = f"{dep.pkg_version:<12}"

            # Format dependency type (left-aligned, 6 chars)
            dep_type_str = f"{dep.dep_type:<6}"

            # Format repo name with proper prefix like legacy (left-aligned, 25 chars)
            repo_full_name = f"projects.{repo.repo_name}" if repo.repo_name != "hub" else f"projects.{repo.repo_name}"
            repo_name_str = f"{repo_full_name:<25}"

            # Status - simplified to ONLY for now (matches legacy output)
            status_str = "ONLY"

            print(f"{Colors.WHITE}{version_str} {dep_type_str} {repo_name_str} {status_str}{Colors.END}")

    # Summary section matching legacy format
    versions_in_use = set(dep.pkg_version for dep in usages)
    repos_using = len(set(dep.repo_id for dep in usages))

    print(f"\n{Colors.PURPLE}{Colors.BOLD}Summary for {pkg_name}:{Colors.END}")
    print(f"Versions in ecosystem: {Colors.BOLD}{len(versions_in_use)}{Colors.END}")
    print(f"Total usage count: {Colors.BOLD}{len(usages)}{Colors.END}")
    print(f"Repositories using: {Colors.BOLD}{repos_using}{Colors.END}")

    # Check for version conflicts
    if len(versions_in_use) == 1:
        print(f"{Colors.GREEN}✅ No version conflicts{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  Version conflicts detected{Colors.END}")

def view_hub_dashboard(ecosystem: EcosystemData) -> None:
    """Lightning-fast hub-centric analysis using hydrated data

    Replaces analyze_hub_status() with pre-computed hub metrics
    """
    print(f"{Colors.PURPLE}{Colors.BOLD}🎯 HUB PACKAGE STATUS{Colors.END}")
    print(f"{Colors.PURPLE}{'='*80}{Colors.END}")

    # Get hub packages (packages actually IN hub - current or outdated status)
    hub_packages = {name: info for name, info in ecosystem.latest.items()
                   if info.hub_status in ['current', 'outdated']}

    if not hub_packages:
        print(f"{Colors.YELLOW}⚠️  No hub packages found in ecosystem{Colors.END}")
        return

    # Separate packages by status
    current_packages = []
    outdated_packages = []
    gap_packages = []

    for pkg_name, pkg_info in hub_packages.items():
        # Get usage count INCLUDING hub repository to match legacy hub command behavior
        # (Note: This is inconsistent with review command but matches legacy hub output)
        usage_count = len([dep for dep in ecosystem.deps.values()
                          if dep.pkg_name == pkg_name and dep.pkg_version not in ['path', 'workspace']])

        # Determine breaking change status using pre-computed stable version
        breaking_status = "current"
        if pkg_info.hub_status == 'outdated' and pkg_info.hub_version:
            # Check if latest version is a pre-release
            latest_is_prerelease = any(pre in pkg_info.latest_version.lower() for pre in ['alpha', 'beta', 'rc', 'pre', 'dev']) or '-' in pkg_info.latest_version

            if latest_is_prerelease:
                # Use the pre-computed stable version for assessment
                if pkg_info.latest_stable_version and pkg_info.latest_stable_version != pkg_info.latest_version:
                    # Use stable version for breaking change assessment
                    if is_breaking_change(pkg_info.hub_version, pkg_info.latest_stable_version):
                        breaking_status = "breaking"
                    else:
                        breaking_status = "safe"
                else:
                    # No stable version available, mark as unstable
                    breaking_status = "unstable"
            else:
                # Latest is stable, use it for assessment
                if is_breaking_change(pkg_info.hub_version, pkg_info.latest_version):
                    breaking_status = "breaking"
                else:
                    breaking_status = "safe"

        # Recalculate status based on stable version comparison
        if pkg_info.hub_version and pkg_info.latest_stable_version:
            hub_ver = parse_version(pkg_info.hub_version)
            stable_ver = parse_version(pkg_info.latest_stable_version)
            latest_ver = parse_version(pkg_info.latest_version)

            if hub_ver and stable_ver:
                if hub_ver >= stable_ver:
                    actual_status = 'current'
                else:
                    actual_status = 'outdated'
            else:
                actual_status = pkg_info.hub_status
        else:
            actual_status = pkg_info.hub_status

        # Add "+" notation if there's a pre-release beyond stable
        latest_display = pkg_info.latest_stable_version
        if pkg_info.latest_version != pkg_info.latest_stable_version:
            latest_display += "+"

        # Check git status for broken dependencies
        git_status = pkg_info.git_status if hasattr(pkg_info, 'git_status') else "OK"
        if git_status not in ["OK", ""]:
            if git_status == "AUTH_REQUIRED":
                latest_display = "⚠️  AUTH_REQUIRED"
            elif git_status == "NOT_FOUND":
                latest_display = "❌ NOT_FOUND"
            elif git_status == "TIMEOUT":
                latest_display = "⏱️  TIMEOUT"
            elif git_status == "UNREACHABLE":
                latest_display = "❌ UNREACHABLE"

        package_data = {
            'name': pkg_name,
            'hub_version': pkg_info.hub_version or "unknown",
            'latest_version': latest_display,
            'usage_count': usage_count,
            'status': actual_status,
            'breaking_status': breaking_status
        }

        if actual_status == 'current':
            current_packages.append(package_data)
        elif actual_status == 'outdated':
            outdated_packages.append(package_data)
        else:
            gap_packages.append(package_data)

    # Current packages section
    if current_packages:
        print(f"\n{Colors.PURPLE}{Colors.BOLD}CURRENT PACKAGES:{Colors.END}")
        print(f"{Colors.WHITE}Package              Hub Version     Latest          #   Safety   {Colors.END}")
        print(f"{Colors.GRAY}------------------------------------------------------------------{Colors.END}")

        for pkg in sorted(current_packages, key=lambda x: x['name']):
            pkg_name = f"{pkg['name']:<20}"
            hub_ver = f"{pkg['hub_version']:<15}"
            latest_ver = f"{Colors.CYAN}{pkg['latest_version']:<15}{Colors.END}"

            # White to grey gradient: high=white, medium=light grey, low=grey
            if pkg['usage_count'] >= 8:
                usage_color = Colors.WHITE
            elif pkg['usage_count'] >= 5:
                usage_color = Colors.LIGHT_GRAY
            else:
                usage_color = Colors.GRAY
            usage = f"{usage_color}{pkg['usage_count']:<3}{Colors.END}"

            # Safety status for current packages (always current)
            safety = f"{Colors.GRAY}current{Colors.END}"

            print(f"  {Colors.WHITE}{pkg_name} {hub_ver} {latest_ver} {usage} {safety}")

    # Outdated packages section
    if outdated_packages:
        print(f"\n{Colors.PURPLE}{Colors.BOLD}OUTDATED PACKAGES:{Colors.END}")
        print(f"{Colors.WHITE}Package              Hub Version     Latest          #   Safety   {Colors.END}")
        print(f"{Colors.GRAY}------------------------------------------------------------------{Colors.END}")

        for pkg in sorted(outdated_packages, key=lambda x: -x['usage_count']):
            pkg_name = f"{pkg['name']:<20}"
            hub_ver = f"{Colors.YELLOW}{pkg['hub_version']:<15}{Colors.END}"
            latest_ver = f"{Colors.CYAN}{pkg['latest_version']:<15}{Colors.END}"

            # White to grey gradient: high=white, medium=light grey, low=grey
            if pkg['usage_count'] >= 8:
                usage_color = Colors.WHITE
            elif pkg['usage_count'] >= 5:
                usage_color = Colors.LIGHT_GRAY
            else:
                usage_color = Colors.GRAY
            usage = f"{usage_color}{pkg['usage_count']:<3}{Colors.END}"

            # Safety status based on breaking change analysis
            if pkg['breaking_status'] == 'breaking':
                safety = f"{Colors.RED}breaking{Colors.END}"
            elif pkg['breaking_status'] == 'safe':
                safety = f"{Colors.GREEN}safe{Colors.END}"
            elif pkg['breaking_status'] == 'unstable':
                safety = f"{Colors.ORANGE}unstable{Colors.END}"
            else:
                safety = f"{Colors.GRAY}unknown{Colors.END}"

            print(f"  {Colors.WHITE}{pkg_name} {hub_ver} {latest_ver} {usage} {safety}")

    # Find packages with high usage but not in hub (opportunities)
    # Count usage excluding hub repository like legacy
    hub_repo_id = get_hub_repo_id(ecosystem)
    all_packages = {}
    for dep in ecosystem.deps.values():
        # Skip dependencies that should be excluded
        if should_exclude_from_stats(dep, hub_repo_id):
            continue

        pkg_name = dep.pkg_name
        if pkg_name not in all_packages:
            all_packages[pkg_name] = set()
        all_packages[pkg_name].add(dep.repo_id)

    # Convert to usage counts (unique repos per package)
    package_usage = {pkg: len(repos) for pkg, repos in all_packages.items()}

    # Get packages that are actually IN the hub (current or outdated, not gap)
    actual_hub_packages = {name for name, info in ecosystem.latest.items()
                          if info.hub_status in ['current', 'outdated']}

    opportunities = []
    for pkg_name, usage_count in package_usage.items():
        if usage_count >= 5 and pkg_name not in actual_hub_packages:
            opportunities.append((pkg_name, usage_count))

    if opportunities:
        print(f"\n{Colors.PURPLE}{Colors.BOLD}PACKAGE OPPORTUNITIES (5+ usage, not in hub):{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")

        # Show opportunities in legacy format
        opp_text = "  "
        for i, (pkg_name, count) in enumerate(sorted(opportunities, key=lambda x: -x[1])):
            opp_text += f"{Colors.GREEN}{pkg_name}({count}){Colors.END}"
            if i < len(opportunities) - 1 and i % 2 == 0:
                opp_text += "                  "
            elif i < len(opportunities) - 1:
                opp_text += "\n  "
        print(opp_text)

    # Build package usage map for ecosystem
    package_usage = {}
    for dep in ecosystem.deps.values():
        if not should_exclude_from_stats(dep, hub_repo_id):  # Exclude hub repo and local/workspace
            if dep.pkg_name not in package_usage:
                package_usage[dep.pkg_name] = set()
            package_usage[dep.pkg_name].add(dep.repo_id)

    # Convert to counts
    package_usage = {pkg: len(repos) for pkg, repos in package_usage.items()}

    # Visual summary bar matching legacy
    current_count = len(current_packages)
    outdated_count = len(outdated_packages)
    gap_count = len(opportunities)  # Gap = packages with high usage not in hub
    unused_count = 0  # Packages in hub but not used in ecosystem
    unique_count = len([pkg for pkg in package_usage.keys() if pkg not in hub_packages])  # Packages in ecosystem but not in hub

    print(f"\n{Colors.PURPLE}{Colors.BOLD}HUB PACKAGES:{Colors.END}")
    summary_line = (f"  Current     Outdated    Gap         Unused      Unique      \n"
                   f"  {Colors.BLUE}■{Colors.END} {Colors.BLUE}{current_count}{Colors.END}         "
                   f"{Colors.ORANGE}■{Colors.END} {Colors.ORANGE}{outdated_count}{Colors.END}        "
                   f"{Colors.GREEN}■{Colors.END} {Colors.GREEN}{gap_count}{Colors.END}         "
                   f"{Colors.RED}■{Colors.END} {Colors.RED}{unused_count}{Colors.END}         "
                   f"{Colors.GRAY}■{Colors.END} {Colors.GRAY}{unique_count}{Colors.END}")
    print(summary_line)

def check_git_safety(repo_path: str) -> tuple[bool, str]:
    """Check if repo is safe for auto-update (on main branch, clean working directory)"""
    import subprocess
    import os

    try:
        # Change to repo directory
        original_cwd = os.getcwd()
        os.chdir(repo_path)

        # Check if it's a git repository
        result = subprocess.run(['git', 'rev-parse', '--git-dir'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "Not a git repository"

        # Check current branch
        result = subprocess.run(['git', 'branch', '--show-current'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "Could not determine current branch"

        current_branch = result.stdout.strip()
        if current_branch not in ['main', 'master']:
            return False, f"Not on main branch (currently on '{current_branch}')"

        # Check for uncommitted changes
        result = subprocess.run(['git', 'status', '--porcelain'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "Could not check git status"

        if result.stdout.strip():
            return False, "Repository has uncommitted changes"

        # Check for unpushed commits
        result = subprocess.run(['git', 'log', '@{u}..HEAD', '--oneline'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return False, "Repository has unpushed commits"

        return True, "Repository is safe for auto-update"

    except subprocess.TimeoutExpired:
        return False, "Git command timeout"
    except Exception as e:
        return False, f"Git check error: {str(e)}"
    finally:
        os.chdir(original_cwd)

def auto_commit_changes(repo_dir: str, updates_count: int) -> tuple[bool, str]:
    """Automatically commit dependency updates with auto:hub bump message"""
    import subprocess
    import os

    try:
        original_cwd = os.getcwd()
        os.chdir(repo_dir)

        # Check if there are changes to commit
        result = subprocess.run(['git', 'status', '--porcelain'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, "Could not check git status"

        if not result.stdout.strip():
            return False, "No changes to commit"

        # Stage Cargo.toml
        result = subprocess.run(['git', 'add', 'Cargo.toml'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, "Could not stage Cargo.toml"

        # Create commit message
        commit_msg = f"auto:hub bump {updates_count} dependencies to latest stable versions"

        # Commit changes
        result = subprocess.run(['git', 'commit', '-m', commit_msg],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, f"Commit failed: {result.stderr}"

        return True, f"Created commit: {commit_msg}"

    except subprocess.TimeoutExpired:
        return False, "Git commit timeout"
    except Exception as e:
        return False, f"Git commit error: {str(e)}"
    finally:
        os.chdir(original_cwd)

def update_repo_dependencies(ecosystem: EcosystemData, repo_name: str, dry_run: bool = False, force_commit: bool = False, force: bool = False) -> None:
    """Update safe dependencies in a specific repository"""
    print(f"{Colors.CYAN}{Colors.BOLD}🔄 UPDATING REPOSITORY: {repo_name}{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")

    # Find the repository
    target_repo = None
    for repo in ecosystem.repos.values():
        if repo.repo_name == repo_name:
            target_repo = repo
            break

    if not target_repo:
        print(f"{Colors.RED}❌ Repository '{repo_name}' not found in ecosystem{Colors.END}")
        return

    # Get full path to repository
    repo_path = Path(RUST_REPO_ROOT) / target_repo.path
    repo_dir = repo_path.parent

    print(f"{Colors.CYAN}Repository path: {repo_dir}{Colors.END}")

    if dry_run:
        print(f"{Colors.YELLOW}🔍 DRY-RUN MODE: Skipping git safety checks{Colors.END}")
    elif force:
        print(f"{Colors.YELLOW}⚠️  FORCE MODE: Skipping git safety checks{Colors.END}")
        print(f"{Colors.YELLOW}    Updates will proceed regardless of branch or uncommitted changes{Colors.END}")
    else:
        # Check git safety
        is_safe, safety_message = check_git_safety(str(repo_dir))
        if not is_safe:
            print(f"{Colors.RED}❌ Cannot run auto-update: {safety_message}{Colors.END}")
            print(f"{Colors.YELLOW}💡 To update manually:{Colors.END}")
            print(f"   1. Ensure you're on main branch: git checkout main")
            print(f"   2. Commit or stash changes: git status")
            print(f"   3. Run update again")
            print(f"{Colors.GRAY}   Or use --dry-run to see what would be updated{Colors.END}")
            print(f"{Colors.GRAY}   Or use --force to bypass safety checks{Colors.END}")
            return

        print(f"{Colors.GREEN}✅ Git safety check passed: {safety_message}{Colors.END}")

    # Find dependencies for this repo that have safe updates
    repo_deps = [dep for dep in ecosystem.deps.values() if dep.repo_id == target_repo.repo_id]
    safe_updates = []

    for dep in repo_deps:
        latest_info = ecosystem.latest.get(dep.pkg_name)
        if latest_info and latest_info.hub_status == 'outdated':
            # Check if update would be safe (using stable version)
            if latest_info.latest_stable_version and dep.pkg_version:
                current_version = dep.pkg_version
                stable_version = latest_info.latest_stable_version

                # Skip workspace, path, and git dependencies
                if current_version.startswith(('path:', 'git:', 'workspace:')):
                    continue

                if not is_breaking_change(current_version, stable_version):
                    safe_updates.append({
                        'name': dep.pkg_name,
                        'current': current_version,
                        'stable': stable_version,
                        'dep_type': dep.dep_type
                    })

    if not safe_updates:
        print(f"{Colors.YELLOW}✅ No safe dependency updates available for {repo_name}{Colors.END}")
        return

    print(f"\n{Colors.GREEN}📦 Found {len(safe_updates)} safe updates:{Colors.END}")
    for update in safe_updates:
        dep_type_indicator = " (dev)" if update['dep_type'] == 'dev-dep' else ""
        print(f"  {Colors.BLUE}├─{Colors.END} {update['name']}: {Colors.ORANGE}{update['current']}{Colors.END} → {Colors.GREEN}{update['stable']}{Colors.END}{dep_type_indicator}")

    # Apply updates to Cargo.toml
    cargo_toml_path = repo_path

    if dry_run:
        print(f"\n{Colors.YELLOW}🔍 DRY-RUN: Would update {cargo_toml_path}{Colors.END}")
        print(f"{Colors.YELLOW}✅ Found {len(safe_updates)} safe dependency updates that would be applied{Colors.END}")
        return

    print(f"\n{Colors.CYAN}🔧 Updating {cargo_toml_path}...{Colors.END}")

    try:
        # Read current Cargo.toml
        with open(cargo_toml_path, 'r') as f:
            content = f.read()

        import re
        updated_content = content
        updates_applied = 0

        for update in safe_updates:
            # Pattern to match dependency lines
            # Handles both: dependency = "version" and dependency = { version = "version" }
            patterns = [
                # Simple version: serde = "1.0.123"
                rf'^(\s*{re.escape(update["name"])}\s*=\s*")[^"]*(".*)',
                # Table version: serde = { version = "1.0.123", features = [...] }
                rf'^(\s*{re.escape(update["name"])}\s*=\s*\{{[^}}]*version\s*=\s*")[^"]*(".*)',
            ]

            for pattern in patterns:
                if re.search(pattern, updated_content, re.MULTILINE):
                    updated_content = re.sub(pattern, rf'\g<1>{update["stable"]}\g<2>',
                                           updated_content, flags=re.MULTILINE)
                    updates_applied += 1
                    break

        if updates_applied > 0:
            # Write updated content
            with open(cargo_toml_path, 'w') as f:
                f.write(updated_content)

            print(f"{Colors.GREEN}✅ Applied {updates_applied} updates to Cargo.toml{Colors.END}")

            # Auto-commit changes if force_commit is enabled
            if force_commit:
                print(f"{Colors.CYAN}🔧 Auto-committing changes...{Colors.END}")
                success, commit_message = auto_commit_changes(str(repo_dir), updates_applied)
                if success:
                    print(f"{Colors.GREEN}✅ Auto-commit successful: {commit_message}{Colors.END}")
                else:
                    print(f"{Colors.RED}❌ Auto-commit failed: {commit_message}{Colors.END}")
            else:
                print(f"\n{Colors.YELLOW}📋 Next steps:{Colors.END}")
                print(f"  1. Test the updates: cd {repo_dir} && cargo check")
                print(f"  2. Run tests: cargo test")
                print(f"  3. Commit changes: git add Cargo.toml && git commit -m 'chore: update safe dependencies'")
        else:
            print(f"{Colors.YELLOW}⚠️  No dependency patterns matched in Cargo.toml{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}❌ Error updating Cargo.toml: {str(e)}{Colors.END}")

def update_ecosystem(ecosystem: EcosystemData, dry_run: bool = False, force_commit: bool = False, force: bool = False) -> None:
    """Update safe dependencies across all repositories in the ecosystem (except hub and rsb)"""
    print(f"{Colors.CYAN}{Colors.BOLD}🌍 ECOSYSTEM-WIDE UPDATE{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")

    # Get all repositories except hub and rsb
    excluded_repos = {'hub', 'rsb'}
    target_repos = [repo for repo in ecosystem.repos.values()
                   if repo.repo_name not in excluded_repos]

    if not target_repos:
        print(f"{Colors.YELLOW}✅ No repositories found for ecosystem update{Colors.END}")
        return

    print(f"{Colors.CYAN}📊 Found {len(target_repos)} repositories to update:{Colors.END}")
    for repo in sorted(target_repos, key=lambda r: r.repo_name):
        print(f"  {Colors.BLUE}├─{Colors.END} {repo.repo_name}")

    if dry_run:
        print(f"\n{Colors.YELLOW}🔍 DRY-RUN MODE: Analyzing potential updates...{Colors.END}")
    elif force:
        print(f"\n{Colors.YELLOW}⚠️  FORCE MODE: Starting ecosystem update without git safety checks...{Colors.END}")
    else:
        print(f"\n{Colors.CYAN}🚀 Starting ecosystem update...{Colors.END}")

    # Track results
    updated_repos = []
    failed_repos = []
    skipped_repos = []
    no_updates_repos = []

    for i, repo in enumerate(sorted(target_repos, key=lambda r: r.repo_name), 1):
        print(f"\n{Colors.PURPLE}[{i}/{len(target_repos)}]{Colors.END} Processing {Colors.BOLD}{repo.repo_name}{Colors.END}...")

        # Get full path to repository
        repo_path = Path(RUST_REPO_ROOT) / repo.path
        repo_dir = repo_path.parent

        # Check git safety (unless dry-run or force)
        if not dry_run and not force:
            is_safe, safety_message = check_git_safety(str(repo_dir))
            if not is_safe:
                print(f"  {Colors.RED}❌ Skipped: {safety_message}{Colors.END}")
                skipped_repos.append((repo.repo_name, safety_message))
                continue

        # Find dependencies for this repo that have safe updates
        repo_deps = [dep for dep in ecosystem.deps.values() if dep.repo_id == repo.repo_id]
        safe_updates = []

        for dep in repo_deps:
            latest_info = ecosystem.latest.get(dep.pkg_name)
            if latest_info and latest_info.hub_status == 'outdated':
                # Check if update would be safe (using stable version)
                if latest_info.latest_stable_version and dep.pkg_version:
                    current_version = dep.pkg_version
                    stable_version = latest_info.latest_stable_version

                    # Skip workspace, path, and git dependencies
                    if current_version.startswith(('path:', 'git:', 'workspace:')):
                        continue

                    if not is_breaking_change(current_version, stable_version):
                        safe_updates.append({
                            'name': dep.pkg_name,
                            'current': current_version,
                            'stable': stable_version,
                            'dep_type': dep.dep_type
                        })

        if not safe_updates:
            print(f"  {Colors.GRAY}✅ No safe updates available{Colors.END}")
            no_updates_repos.append(repo.repo_name)
            continue

        print(f"  {Colors.GREEN}📦 Found {len(safe_updates)} safe updates{Colors.END}")

        if dry_run:
            for update in safe_updates[:3]:  # Show first 3
                print(f"    {Colors.BLUE}├─{Colors.END} {update['name']}: {Colors.ORANGE}{update['current']}{Colors.END} → {Colors.GREEN}{update['stable']}{Colors.END}")
            if len(safe_updates) > 3:
                print(f"    {Colors.GRAY}└─ ...and {len(safe_updates) - 3} more{Colors.END}")
            updated_repos.append((repo.repo_name, len(safe_updates)))
            continue

        # Apply updates (real mode)
        try:
            cargo_toml_path = repo_path

            # Read current Cargo.toml
            with open(cargo_toml_path, 'r') as f:
                content = f.read()

            import re
            updated_content = content
            updates_applied = 0

            for update in safe_updates:
                # Pattern to match dependency lines
                patterns = [
                    # Simple version: serde = "1.0.123"
                    rf'^(\s*{re.escape(update["name"])}\s*=\s*")[^"]*(".*)',
                    # Table version: serde = { version = "1.0.123", features = [...] }
                    rf'^(\s*{re.escape(update["name"])}\s*=\s*\{{[^}}]*version\s*=\s*")[^"]*(".*)',
                ]

                for pattern in patterns:
                    if re.search(pattern, updated_content, re.MULTILINE):
                        updated_content = re.sub(pattern, rf'\g<1>{update["stable"]}\g<2>',
                                               updated_content, flags=re.MULTILINE)
                        updates_applied += 1
                        break

            if updates_applied > 0:
                # Write updated content
                with open(cargo_toml_path, 'w') as f:
                    f.write(updated_content)

                print(f"  {Colors.GREEN}✅ Applied {updates_applied} updates{Colors.END}")

                # Auto-commit changes if force_commit is enabled
                if force_commit:
                    print(f"  {Colors.CYAN}🔧 Auto-committing changes...{Colors.END}")
                    success, commit_message = auto_commit_changes(str(repo_dir), updates_applied)
                    if success:
                        print(f"  {Colors.GREEN}✅ Auto-commit successful{Colors.END}")
                    else:
                        print(f"  {Colors.RED}❌ Auto-commit failed: {commit_message}{Colors.END}")

                updated_repos.append((repo.repo_name, updates_applied))
            else:
                print(f"  {Colors.YELLOW}⚠️  No patterns matched in Cargo.toml{Colors.END}")
                failed_repos.append((repo.repo_name, "No patterns matched"))

        except Exception as e:
            print(f"  {Colors.RED}❌ Error: {str(e)}{Colors.END}")
            failed_repos.append((repo.repo_name, str(e)))

    # Summary
    print(f"\n{Colors.PURPLE}{Colors.BOLD}📊 ECOSYSTEM UPDATE SUMMARY{Colors.END}")
    print(f"{Colors.PURPLE}{'='*40}{Colors.END}")

    if updated_repos:
        if dry_run:
            print(f"\n{Colors.GREEN}🔍 Would update {len(updated_repos)} repositories:{Colors.END}")
        else:
            print(f"\n{Colors.GREEN}✅ Updated {len(updated_repos)} repositories:{Colors.END}")
        for repo_name, count in updated_repos:
            print(f"  {Colors.BLUE}├─{Colors.END} {repo_name}: {count} updates")

    if no_updates_repos:
        print(f"\n{Colors.GRAY}📦 No updates needed ({len(no_updates_repos)} repos):{Colors.END}")
        for repo_name in no_updates_repos:
            print(f"  {Colors.GRAY}├─{Colors.END} {repo_name}")

    if skipped_repos:
        print(f"\n{Colors.YELLOW}⚠️  Skipped {len(skipped_repos)} repositories:{Colors.END}")
        for repo_name, reason in skipped_repos:
            print(f"  {Colors.YELLOW}├─{Colors.END} {repo_name}: {reason}")

    if failed_repos:
        print(f"\n{Colors.RED}❌ Failed {len(failed_repos)} repositories:{Colors.END}")
        for repo_name, error in failed_repos:
            print(f"  {Colors.RED}├─{Colors.END} {repo_name}: {error}")

    # Next steps
    if updated_repos and not dry_run:
        if force_commit:
            print(f"\n{Colors.YELLOW}📋 Next steps:{Colors.END}")
            print(f"  1. Test updates: Run cargo check in each updated repository")
            print(f"  2. Run tests: cargo test in critical repositories")
            print(f"  {Colors.GRAY}(Changes have been automatically committed with 'auto:hub bump' messages){Colors.END}")
        else:
            print(f"\n{Colors.YELLOW}📋 Next steps:{Colors.END}")
            print(f"  1. Test updates: Run cargo check in each updated repository")
            print(f"  2. Run tests: cargo test in critical repositories")
            print(f"  3. Commit changes: git add . && git commit -m 'chore: ecosystem dependency updates'")

def view_review(ecosystem: EcosystemData) -> None:
    """Lightning-fast ecosystem dependency review using hydrated data

    Replaces review command with instant analysis
    """
    print(f"{Colors.WHITE}{Colors.BOLD}📋 ECOSYSTEM DEPENDENCY REVIEW{Colors.END}")
    print(f"{Colors.GRAY}Status of each dependency across all Rust projects (ignoring hub){Colors.END}")
    print(f"{Colors.GRAY}{'='*80}{Colors.END}\n")

    print(f"{Colors.GRAY}Loading latest versions from data cache (run 'export' to refresh)...{Colors.END}\n")

    # Table header
    print(f"{Colors.WHITE}{Colors.BOLD}{'Package':<20} {'#U':<4} {'Ecosystem':<14} {'Latest':<20} {'Breaking'}{Colors.END}")
    print(f"{Colors.GRAY}{'-'*85}{Colors.END}")

    # Collect all packages with usage stats, filtering out path/workspace deps and hub repo
    hub_repo_id = get_hub_repo_id(ecosystem)
    package_stats = {}
    for dep in ecosystem.deps.values():
        # Skip dependencies that should be excluded
        if should_exclude_from_stats(dep, hub_repo_id):
            continue

        pkg_name = dep.pkg_name
        if pkg_name not in package_stats:
            package_stats[pkg_name] = {
                'versions': set(),
                'usage_count': 0,
                'repos': set()
            }
        package_stats[pkg_name]['versions'].add(dep.pkg_version)
        package_stats[pkg_name]['usage_count'] += 1
        package_stats[pkg_name]['repos'].add(dep.repo_id)

    # Sort by usage count descending, then alphabetically like legacy
    def sort_key(item):
        pkg_name, stats = item
        # Count unique repos using this dependency
        repo_count = len(stats['repos'])
        return (-repo_count, pkg_name)  # Negative for descending order

    sorted_packages = sorted(package_stats.items(), key=sort_key)

    for pkg_name, stats in sorted_packages:
        # Get latest version info
        latest_info = ecosystem.latest.get(pkg_name)
        latest_version = latest_info.latest_version if latest_info else "unknown"

        # Check git status for broken dependencies
        git_status = latest_info.git_status if latest_info else "OK"
        if git_status not in ["OK", ""]:
            # Add warning indicator for broken git deps
            if git_status == "AUTH_REQUIRED":
                latest_version = f"⚠️  AUTH_REQUIRED"
            elif git_status == "NOT_FOUND":
                latest_version = f"❌ NOT_FOUND"
            elif git_status == "TIMEOUT":
                latest_version = f"⏱️  TIMEOUT"
            elif git_status == "UNREACHABLE":
                latest_version = f"❌ UNREACHABLE"

        # Determine ecosystem version (most common or highest)
        versions_list = list(stats['versions'])
        if len(versions_list) == 1:
            eco_version = versions_list[0]
        else:
            # For conflicts, show the highest version as ecosystem version
            eco_version = sorted(versions_list)[-1]

        # Get version risk and status like legacy does
        from packaging.version import parse as parse_version
        parsed_versions = []
        for v in stats['versions']:
            # Skip git/path/workspace version markers
            if v in ['git', 'path', 'workspace']:
                continue
            try:
                parsed_versions.append(parse_version(v))
            except:
                continue

        # For git dependencies with no parseable version, use special handling
        if not parsed_versions:
            # Check if it's a git dependency by looking at latest_info
            if latest_info and latest_info.source_type == "git":
                # Show git dependency with its status
                ecosystem_version = "git"
                pkg_display = f"{Colors.LIGHT_GRAY}{pkg_name:<20}{Colors.END}"
                usage_display = f"{len(stats['repos']):<4}"
                eco_display = f"{Colors.GRAY}git dependency{Colors.END}"
                latest_display = f"{Colors.CYAN}{latest_version:<20}{Colors.END}" if git_status == "OK" else f"{Colors.RED}{latest_version:<20}{Colors.END}"
                breaking_status = f"{Colors.GRAY}N/A{Colors.END}"
                print(f"{pkg_display} {usage_display} {eco_display:<14} {latest_display} {breaking_status}")
            continue

        sorted_versions = sorted(parsed_versions)
        min_version = min(sorted_versions)
        max_version = max(sorted_versions)
        ecosystem_version = str(max_version)

        # Status and smart coloring logic like legacy
        has_conflicts = len(stats['versions']) > 1
        latest_str = latest_version if latest_version else "unknown"

        # Check for breaking changes like legacy
        has_breaking = False
        if latest_version and has_conflicts:
            # Check if update from min to latest would be breaking
            try:
                min_major = str(min_version).split('.')[0]
                latest_major = latest_version.split('.')[0] if '.' in latest_version else latest_version
                if min_major != latest_major and min_major.isdigit() and latest_major.isdigit():
                    has_breaking = int(latest_major) > int(min_major)
            except:
                pass

        # Determine breaking status with conflict indicators integrated
        if ecosystem_version == latest_version:
            breaking_status = f"{Colors.GRAY}current{Colors.END}"
        elif has_conflicts:
            if has_breaking:
                breaking_status = f"{Colors.RED2}■ BREAKING{Colors.END}"  # RED2 for breaking + conflicts
            else:
                breaking_status = f"{Colors.YELLOW}■ CONFLICT{Colors.END}"
        elif ecosystem_version != latest_version:
            try:
                eco_major = ecosystem_version.split('.')[0] if '.' in ecosystem_version else ecosystem_version
                latest_major = latest_version.split('.')[0] if '.' in latest_version else latest_version
                if eco_major != latest_major and eco_major.isdigit() and latest_major.isdigit():
                    if int(latest_major) > int(eco_major):
                        breaking_status = f"{Colors.RED2}BREAKING{Colors.END}"  # RED2 for breaking without conflicts
                    else:
                        breaking_status = f"{Colors.GREEN}safe{Colors.END}"
                else:
                    breaking_status = f"{Colors.GREEN}safe{Colors.END}"
            except:
                breaking_status = f"{Colors.GREEN}safe{Colors.END}"

        # Ecosystem column color - simple update status only (no red conflicts)
        if ecosystem_version != latest_version:
            eco_color = Colors.ORANGE  # Outdated
        else:
            eco_color = Colors.GRAY    # Current

        # Format output with usage-based coloring for package names
        usage_count = len(stats['repos'])
        if usage_count >= 5:
            pkg_color = Colors.WHITE  # High usage = bright white
        elif usage_count >= 3:
            pkg_color = Colors.LIGHT_GRAY  # Medium usage = light grey
        else:
            pkg_color = Colors.GRAY  # Low usage = grey

        pkg_display = f"{pkg_color}{pkg_name:<20}{Colors.END}"
        usage_display = f"{usage_count:<4}"

        # Format versions with color when different
        if ecosystem_version != latest_version:
            eco_display = f"{eco_color}{ecosystem_version:<14}{Colors.END}"
            latest_display = f"{Colors.CYAN}{latest_version:<20}{Colors.END}"
        else:
            eco_display = f"{Colors.GRAY}{ecosystem_version:<14}{Colors.END}"
            latest_display = f"{Colors.GRAY}{latest_version:<20}{Colors.END}"

        print(f"{pkg_display} {usage_display} {eco_display} {latest_display} {breaking_status}")

    # Legend
    print(f"\n{Colors.PURPLE}{Colors.BOLD}Legend:{Colors.END}")
    print(f"Breaking: {Colors.RED2}■ BREAKING{Colors.END} (breaking + conflicts), {Colors.RED2}BREAKING{Colors.END} (breaking), {Colors.YELLOW}■ CONFLICT{Colors.END} (conflicts), {Colors.GREEN}safe{Colors.END}, {Colors.GRAY}current{Colors.END}")
    print(f"Note: ■ = version conflicts in ecosystem")
    print(f"Versions: Only colored when {Colors.ORANGE}ecosystem{Colors.END} ≠ {Colors.CYAN}latest{Colors.END}")

def view_usage(ecosystem: EcosystemData) -> None:
    """Lightning-fast package usage analysis using hydrated data

    Replaces usage command with instant analysis
    """
    print(f"{Colors.PURPLE}{Colors.BOLD}📊 PACKAGE USAGE ANALYSIS{Colors.END}")
    print(f"{Colors.PURPLE}{'='*80}{Colors.END}\n")

    # Get hub packages from the new data model
    hub_deps = {}
    for pkg_name, latest_info in ecosystem.latest.items():
        # Check if package is in hub (status is 'current' or 'outdated')
        if latest_info.hub_status in ['current', 'outdated']:
            hub_deps[pkg_name] = {
                'version': latest_info.hub_version,
                'status': latest_info.hub_status,
                'latest': latest_info.latest_version
            }

    # Collect usage stats, filtering out path/workspace deps and hub repo
    hub_repo_id = get_hub_repo_id(ecosystem)
    package_consumers = {}
    for dep in ecosystem.deps.values():
        # Skip dependencies that should be excluded (local/workspace/hub)
        if should_exclude_from_stats(dep, hub_repo_id):
            continue

        pkg_name = dep.pkg_name
        if pkg_name not in package_consumers:
            package_consumers[pkg_name] = set()

        # Extract repo name from path - match legacy logic
        repo_name = f"repo_{dep.repo_id}"
        package_consumers[pkg_name].add(repo_name)

    # Categorize packages like legacy
    high_usage = []  # 5+ consumers
    medium_usage = []  # 3-4 consumers
    low_usage = []  # 1-2 consumers

    for pkg_name, repo_names in package_consumers.items():
        consumer_count = len(repo_names)
        in_hub = pkg_name in hub_deps

        if consumer_count >= 5:
            high_usage.append((pkg_name, consumer_count, list(repo_names)))
        elif consumer_count >= 3:
            medium_usage.append((pkg_name, consumer_count, list(repo_names)))
        else:
            low_usage.append((pkg_name, consumer_count, list(repo_names)))

    # Sort each category: hub packages first, then by usage count like legacy
    def sort_key(item):
        pkg_name, count, _ = item
        in_hub = pkg_name in hub_deps
        # Return tuple: (0 if in hub else 1, -count) for sorting
        # This puts hub packages first, then sorts by count descending
        return (0 if in_hub else 1, -count)

    high_usage.sort(key=sort_key)
    medium_usage.sort(key=sort_key)
    low_usage.sort(key=sort_key)

    # Print high usage packages with count in header
    if high_usage:
        print(f"\n{Colors.PURPLE}{Colors.BOLD}HIGH USAGE (5+ projects) - {len(high_usage)} packages:{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")
        col_width = 25
        cols = 3
        for i in range(0, len(high_usage), cols):
            row = "  "
            for j in range(cols):
                if i + j < len(high_usage):
                    pkg_name, count, _ = high_usage[i + j]
                    in_hub = pkg_name in hub_deps
                    if in_hub:
                        # Check hub status for proper coloring
                        hub_info = hub_deps[pkg_name]
                        if hub_info['status'] == 'current':
                            # Current - blue
                            text = f"{pkg_name}({count})"
                            colored = f"{Colors.BLUE}{text}{Colors.END}"
                        else:
                            # Outdated - yellow/orange
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.YELLOW}{text}{Colors.END}"
                    else:
                        # Not in hub - green if high usage (5+), grey if low usage (1-2), normal for medium (3-4)
                        if count >= 5:
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.GREEN}{text}{Colors.END}"  # Gap package (opportunity)
                        elif count <= 2:
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.GRAY}{text}{Colors.END}"   # Unique package (low priority)
                        else:
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.WHITE}{text}{Colors.END}"  # Medium usage, not categorized"
                    # Pad based on actual text length, not colored string
                    padding = " " * max(0, col_width - len(text))
                    row += colored + padding
            print(row.rstrip())

    # Print medium usage packages with count in header
    if medium_usage:
        print(f"\n{Colors.PURPLE}{Colors.BOLD}MEDIUM USAGE (3-4 projects) - {len(medium_usage)} packages:{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")
        col_width = 25
        cols = 3
        for i in range(0, len(medium_usage), cols):
            row = "  "
            for j in range(cols):
                if i + j < len(medium_usage):
                    pkg_name, count, _ = medium_usage[i + j]
                    in_hub = pkg_name in hub_deps
                    if in_hub:
                        # Check hub status for proper coloring
                        hub_info = hub_deps[pkg_name]
                        if hub_info['status'] == 'current':
                            # Current - blue
                            text = f"{pkg_name}({count})"
                            colored = f"{Colors.BLUE}{text}{Colors.END}"
                        else:
                            # Outdated - yellow/orange
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.YELLOW}{text}{Colors.END}"
                    else:
                        # Not in hub - green if high usage (5+), grey if low usage (1-2), normal for medium (3-4)
                        if count >= 5:
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.GREEN}{text}{Colors.END}"  # Gap package (opportunity)
                        elif count <= 2:
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.GRAY}{text}{Colors.END}"   # Unique package (low priority)
                        else:
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.WHITE}{text}{Colors.END}"  # Medium usage, not categorized"
                    # Pad based on actual text length, not colored string
                    padding = " " * max(0, col_width - len(text))
                    row += colored + padding
            print(row.rstrip())

    # Print low usage packages with count in header
    if low_usage:
        print(f"\n{Colors.PURPLE}{Colors.BOLD}LOW USAGE (1-2 projects) - {len(low_usage)} packages:{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")
        col_width = 25
        cols = 3
        for i in range(0, len(low_usage), cols):
            row = "  "
            for j in range(cols):
                if i + j < len(low_usage):
                    pkg_name, count, _ = low_usage[i + j]
                    in_hub = pkg_name in hub_deps
                    if in_hub:
                        # Check hub status for proper coloring
                        hub_info = hub_deps[pkg_name]
                        if hub_info['status'] == 'current':
                            # Current - blue
                            text = f"{pkg_name}({count})"
                            colored = f"{Colors.BLUE}{text}{Colors.END}"
                        else:
                            # Outdated - yellow/orange
                            text = f"{pkg_name}({count})*"
                            colored = f"{Colors.YELLOW}{text}{Colors.END}"
                    else:
                        # Gap package for low usage - grey (less important)
                        text = f"{pkg_name}({count})*"
                        colored = f"{Colors.GRAY}{text}{Colors.END}"
                    # Pad based on actual text length, not colored string
                    padding = " " * max(0, col_width - len(text))
                    row += colored + padding
            print(row.rstrip())

    # Hub status summary - calculate properly
    hub_current = 0
    hub_outdated = 0
    hub_gap = 0  # Packages with 5+ usage not in hub
    hub_unused = 0  # Hub packages with 0 usage in ecosystem
    hub_unique = 0  # Hub packages not used by any other repo

    # Count hub packages by status
    for pkg_name, hub_info in hub_deps.items():
        if pkg_name in package_consumers:
            # Package is used in ecosystem
            if hub_info['status'] == 'current':
                hub_current += 1
            else:
                hub_outdated += 1
        else:
            # Hub package not used in ecosystem at all
            hub_unique += 1

    # Count gap and unique packages
    gap_packages = 0
    unique_packages = 0

    for pkg_name, repo_set in package_consumers.items():
        if pkg_name not in hub_deps:
            usage_count = len(repo_set)
            if usage_count >= 5:
                gap_packages += 1  # High value opportunities (missing from hub)
            elif usage_count <= 2:
                unique_packages += 1  # Low usage packages (not hub-worthy)
            # Medium usage (3-4) packages not in hub are neither gap nor unique

    hub_gap = gap_packages
    # hub_unused is already calculated above (hub packages with zero ecosystem usage)
    hub_unique = unique_packages  # Low usage packages not in hub

    total_packages = len(package_consumers)
    print(f"\n{Colors.PURPLE}{Colors.BOLD}HUB STATUS - {total_packages} total packages:{Colors.END}")
    print(f"  {'Current':<12}{'Outdated':<12}{'Gap':<12}{'Unused':<12}{'Unique':<12}")
    print(f"  {Colors.BLUE}■{Colors.END} {Colors.BLUE}{hub_current:<9}{Colors.END} {Colors.ORANGE}■{Colors.END} {Colors.ORANGE}{hub_outdated:<9}{Colors.END} {Colors.GREEN}■{Colors.END} {Colors.GREEN}{hub_gap:<9}{Colors.END} {Colors.RED}■{Colors.END} {Colors.RED}{hub_unused:<9}{Colors.END} {Colors.GRAY}■{Colors.END} {Colors.GRAY}{hub_unique}{Colors.END}")

    # Print opportunity packages (high usage not in hub)
    opportunity_packages = [pkg for pkg, count, _ in high_usage if pkg not in hub_deps and count >= 5]
    if opportunity_packages:
        print(f"\n{Colors.PURPLE}{Colors.BOLD}OPPORTUNITY PACKAGES (5+ usage, not in hub):{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")
        for pkg in opportunity_packages:
            count = len(package_consumers[pkg])
            print(f"  {Colors.GREEN}{pkg}({count}){Colors.END}")

def view_stats(ecosystem: EcosystemData) -> None:
    """Display quick ecosystem statistics"""
    if BOXY_AVAILABLE:
        # Collect all output for boxy rendering
        output_lines = []

        # Aggregation stats
        if ecosystem.aggregation:
            output_lines.append(f"{Colors.YELLOW}📈 Overview:{Colors.END}")
            for key, value in ecosystem.aggregation.items():
                if key != "generated_at":
                    output_lines.append(f"  {Colors.BLUE}•{Colors.END} {key.replace('_', ' ').title()}: {Colors.GREEN}{value}{Colors.END}")

        # Package distribution (using consistent filtering)
        hub_repo_id = get_hub_repo_id(ecosystem)
        usage_counts = {}
        for dep in ecosystem.deps.values():
            if not should_exclude_from_stats(dep, hub_repo_id):
                usage_counts[dep.pkg_name] = usage_counts.get(dep.pkg_name, 0) + 1

        sorted_packages = sorted(usage_counts.items(), key=lambda x: x[1], reverse=True)

        output_lines.append("")
        output_lines.append(f"{Colors.YELLOW}📦 Top 10 Most Used Packages:{Colors.END}")
        for pkg, count in sorted_packages[:10]:
            bar_length = int((count / sorted_packages[0][1]) * 30) if sorted_packages else 0
            bar = "█" * bar_length
            output_lines.append(f"  {pkg:20} {Colors.GREEN}{bar}{Colors.END} ({count})")

        # Version statistics
        version_conflicts = get_version_conflicts(ecosystem)
        breaking_updates = get_breaking_updates(ecosystem)

        output_lines.append("")
        output_lines.append(f"{Colors.YELLOW}⚠️  Issues:{Colors.END}")
        output_lines.append(f"  {Colors.BLUE}•{Colors.END} Version Conflicts: {Colors.RED if version_conflicts else Colors.GREEN}{len(version_conflicts)}{Colors.END}")
        output_lines.append(f"  {Colors.BLUE}•{Colors.END} Breaking Updates Available: {Colors.YELLOW if breaking_updates else Colors.GREEN}{len(breaking_updates)}{Colors.END}")

        # Hub status
        hub_gaps = get_hub_gaps(ecosystem)
        hub_packages = [dep.pkg_name for dep in ecosystem.deps.values() if hasattr(dep, 'hub_status') and dep.hub_status == "HUB"]

        output_lines.append("")
        output_lines.append(f"{Colors.YELLOW}🏗️  Hub Integration:{Colors.END}")
        output_lines.append(f"  {Colors.BLUE}•{Colors.END} Hub Packages: {Colors.GREEN}{len(set(hub_packages))}{Colors.END}")
        output_lines.append(f"  {Colors.BLUE}•{Colors.END} Hub Gaps: {Colors.YELLOW if hub_gaps else Colors.GREEN}{len(hub_gaps)}{Colors.END}")

        # Render with boxy
        content = "\n".join(output_lines)
        theme = get_command_theme("stats")
        result = render_with_boxy(content, title="📊 Ecosystem Statistics", theme=theme, header="Hub Repository Analysis", width="80")
        print(result)

    else:
        # Original output without boxy
        print(f"\n{Colors.CYAN}{Colors.BOLD}📊 ECOSYSTEM STATISTICS{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")

        # Aggregation stats
        if ecosystem.aggregation:
            print(f"\n{Colors.YELLOW}📈 Overview:{Colors.END}")
            for key, value in ecosystem.aggregation.items():
                if key != "generated_at":
                    print(f"  {Colors.BLUE}•{Colors.END} {key.replace('_', ' ').title()}: {Colors.GREEN}{value}{Colors.END}")

        # Package distribution (using consistent filtering)
        hub_repo_id = get_hub_repo_id(ecosystem)
        usage_counts = {}
        for dep in ecosystem.deps.values():
            if not should_exclude_from_stats(dep, hub_repo_id):
                usage_counts[dep.pkg_name] = usage_counts.get(dep.pkg_name, 0) + 1

        sorted_packages = sorted(usage_counts.items(), key=lambda x: x[1], reverse=True)

        print(f"\n{Colors.YELLOW}📦 Top 10 Most Used Packages:{Colors.END}")
        for pkg, count in sorted_packages[:10]:
            bar_length = int((count / sorted_packages[0][1]) * 30) if sorted_packages else 0
            bar = "█" * bar_length
            print(f"  {pkg:20} {Colors.GREEN}{bar}{Colors.END} ({count})")

        # Version statistics
        version_conflicts = get_version_conflicts(ecosystem)
        breaking_updates = get_breaking_updates(ecosystem)

        print(f"\n{Colors.YELLOW}⚠️  Issues:{Colors.END}")
        print(f"  {Colors.BLUE}•{Colors.END} Version Conflicts: {Colors.RED if version_conflicts else Colors.GREEN}{len(version_conflicts)}{Colors.END}")
        print(f"  {Colors.BLUE}•{Colors.END} Breaking Updates Available: {Colors.YELLOW if breaking_updates else Colors.GREEN}{len(breaking_updates)}{Colors.END}")

        # Hub status
        hub_gaps = get_hub_gaps(ecosystem)
        hub_packages = [dep.pkg_name for dep in ecosystem.deps.values() if hasattr(dep, 'hub_status') and dep.hub_status == "HUB"]

        print(f"\n{Colors.YELLOW}🏗️  Hub Integration:{Colors.END}")
        print(f"  {Colors.BLUE}•{Colors.END} Hub Packages: {Colors.GREEN}{len(set(hub_packages))}{Colors.END}")
        print(f"  {Colors.BLUE}•{Colors.END} Hub Gaps: {Colors.YELLOW if hub_gaps else Colors.GREEN}{len(hub_gaps)}{Colors.END}")

def view_repo_deps(ecosystem: EcosystemData, repo_name: str) -> None:
    """Display dependencies of a specific repository"""
    # Find the repo
    matching_repos = []
    for repo in ecosystem.repos.values():
        if repo_name.lower() in repo.repo_name.lower():
            matching_repos.append(repo)

    if not matching_repos:
        print(f"{Colors.RED}❌ No repository found matching '{repo_name}'{Colors.END}")
        return

    if len(matching_repos) > 1:
        print(f"{Colors.YELLOW}⚠️  Multiple repositories match '{repo_name}':{Colors.END}")
        for i, repo in enumerate(matching_repos[:5], 1):
            print(f"  {i}. {repo.repo_name}")
        print(f"\nShowing first match: {Colors.BOLD}{matching_repos[0].repo_name}{Colors.END}")

    repo = matching_repos[0]

    # Get dependencies for this repo
    repo_deps = []
    for dep in ecosystem.deps.values():
        dep_repo = ecosystem.repos.get(dep.repo_id)
        if dep_repo and dep_repo.path == repo.path:
            repo_deps.append(dep)

    if BOXY_AVAILABLE:
        # Collect output for boxy rendering
        output_lines = []

        output_lines.append(f"Path: {repo.path}")
        output_lines.append(f"Hub Status: {Colors.GREEN if repo.hub_status == 'HUB' else Colors.YELLOW}{repo.hub_status}{Colors.END}")

        if not repo_deps:
            output_lines.append(f"\n{Colors.YELLOW}No dependencies found{Colors.END}")
        else:
            # Group by dependency type
            normal_deps = [d for d in repo_deps if d.dep_type == "dep"]
            dev_deps = [d for d in repo_deps if d.dep_type == "dev-dep"]
            # Note: build-dependencies don't appear in the TSV cache
            build_deps = []

            def add_dep_list(deps, title):
                if deps:
                    output_lines.append("")
                    output_lines.append(f"{Colors.YELLOW}{title} ({len(deps)}):{Colors.END}")
                    for dep in sorted(deps, key=lambda d: d.pkg_name):
                        latest = ecosystem.latest.get(dep.pkg_name)
                        version_color = Colors.GREEN
                        update_marker = ""

                        if latest and dep.pkg_version != latest.latest_version and latest.latest_version != "LOCAL":
                            if is_breaking_change(dep.pkg_version, latest.latest_version):
                                version_color = Colors.RED
                                update_marker = f" → {Colors.RED}{latest.latest_version}{Colors.END}"
                            else:
                                version_color = Colors.YELLOW
                                update_marker = f" → {Colors.YELLOW}{latest.latest_version}{Colors.END}"

                        features = f" [{dep.features}]" if dep.features and dep.features != "[]" and dep.features != "NONE" else ""
                        output_lines.append(f"  {Colors.BLUE}•{Colors.END} {dep.pkg_name}: {version_color}{dep.pkg_version}{Colors.END}{features}{update_marker}")

            add_dep_list(normal_deps, "Dependencies")
            add_dep_list(dev_deps, "Dev Dependencies")
            add_dep_list(build_deps, "Build Dependencies")

            output_lines.append("")
            output_lines.append(f"{Colors.GREEN}Total: {len(repo_deps)} dependencies{Colors.END}")

        # Render with boxy
        content = "\n".join(output_lines)
        theme = get_command_theme("deps")
        result = render_with_boxy(content, title=f"📦 Dependencies: {repo.repo_name}", theme=theme, header="Repository Analysis", width="80")
        print(result)

    else:
        # Original output without boxy
        print(f"\n{Colors.CYAN}{Colors.BOLD}📦 DEPENDENCIES: {repo.repo_name}{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")
        print(f"Path: {repo.path}")
        print(f"Hub Status: {Colors.GREEN if repo.hub_status == 'HUB' else Colors.YELLOW}{repo.hub_status}{Colors.END}")

        if not repo_deps:
            print(f"\n{Colors.YELLOW}No dependencies found{Colors.END}")
            return

        # Group by dependency type
        normal_deps = [d for d in repo_deps if d.dep_type == "dep"]
        dev_deps = [d for d in repo_deps if d.dep_type == "dev-dep"]
        # Note: build-dependencies don't appear in the TSV cache
        build_deps = []

        def print_dep_list(deps, title):
            if deps:
                print(f"\n{Colors.YELLOW}{title} ({len(deps)}):{Colors.END}")
                for dep in sorted(deps, key=lambda d: d.pkg_name):
                    latest = ecosystem.latest.get(dep.pkg_name)
                    version_color = Colors.GREEN
                    update_marker = ""

                    if latest and dep.pkg_version != latest.latest_version and latest.latest_version != "LOCAL":
                        if is_breaking_change(dep.pkg_version, latest.latest_version):
                            version_color = Colors.RED
                            update_marker = f" → {Colors.RED}{latest.latest_version}{Colors.END}"
                        else:
                            version_color = Colors.YELLOW
                            update_marker = f" → {Colors.YELLOW}{latest.latest_version}{Colors.END}"

                    features = f" [{dep.features}]" if dep.features and dep.features != "[]" else ""
                    print(f"  {Colors.BLUE}•{Colors.END} {dep.pkg_name}: {version_color}{dep.pkg_version}{Colors.END}{features}{update_marker}")

        print_dep_list(normal_deps, "Dependencies")
        print_dep_list(dev_deps, "Dev Dependencies")
        print_dep_list(build_deps, "Build Dependencies")

        print(f"\n{Colors.GREEN}Total: {len(repo_deps)} dependencies{Colors.END}")

def view_outdated(ecosystem: EcosystemData) -> None:
    """Display packages with available updates"""

    # Collect outdated packages
    outdated = {}
    for dep in ecosystem.deps.values():
        latest = ecosystem.latest.get(dep.pkg_name)
        if latest and dep.pkg_version != latest.latest_version and latest.latest_version != "LOCAL":
            if dep.pkg_name not in outdated:
                outdated[dep.pkg_name] = {
                    'current_versions': set(),
                    'latest': latest.latest_version,
                    'repos': []
                }
            outdated[dep.pkg_name]['current_versions'].add(dep.pkg_version)
            repo = ecosystem.repos.get(dep.repo_id)
            if repo and repo.repo_name not in outdated[dep.pkg_name]['repos']:
                outdated[dep.pkg_name]['repos'].append(repo.repo_name)

    if BOXY_AVAILABLE:
        # Collect output for boxy rendering
        output_lines = []

        if not outdated:
            output_lines.append(f"{Colors.GREEN}✅ All packages are up to date!{Colors.END}")
        else:
            # Separate breaking and non-breaking updates
            breaking_updates = []
            minor_updates = []

            for pkg, info in outdated.items():
                has_breaking = False
                for current in info['current_versions']:
                    if is_breaking_change(current, info['latest']):
                        has_breaking = True
                        break

                if has_breaking:
                    breaking_updates.append((pkg, info))
                else:
                    minor_updates.append((pkg, info))

            # Add breaking updates
            if breaking_updates:
                output_lines.append(f"{Colors.RED}{Colors.BOLD}⚠️  BREAKING UPDATES ({len(breaking_updates)}):{Colors.END}")
                for pkg, info in sorted(breaking_updates):
                    versions = ', '.join(sorted(info['current_versions']))
                    output_lines.append("")
                    output_lines.append(f"  {Colors.BOLD}{pkg}{Colors.END}")
                    output_lines.append(f"    Current: {Colors.YELLOW}{versions}{Colors.END}")
                    output_lines.append(f"    Latest:  {Colors.GREEN}{info['latest']}{Colors.END}")
                    output_lines.append(f"    Used in: {', '.join(info['repos'][:5])}")
                    if len(info['repos']) > 5:
                        output_lines.append(f"             ... and {len(info['repos']) - 5} more")

            # Add minor updates
            if minor_updates:
                if breaking_updates:
                    output_lines.append("")
                output_lines.append(f"{Colors.YELLOW}{Colors.BOLD}📦 MINOR UPDATES ({len(minor_updates)}):{Colors.END}")
                for pkg, info in sorted(minor_updates):
                    versions = ', '.join(sorted(info['current_versions']))
                    output_lines.append("")
                    output_lines.append(f"  {Colors.BOLD}{pkg}{Colors.END}")
                    output_lines.append(f"    Current: {Colors.BLUE}{versions}{Colors.END}")
                    output_lines.append(f"    Latest:  {Colors.GREEN}{info['latest']}{Colors.END}")
                    output_lines.append(f"    Used in: {', '.join(info['repos'][:3])}")
                    if len(info['repos']) > 3:
                        output_lines.append(f"             ... and {len(info['repos']) - 3} more")

            output_lines.append("")
            output_lines.append(f"{Colors.GRAY}Run 'cargo update' in affected repositories to update non-breaking changes{Colors.END}")

        # Render with boxy
        content = "\n".join(output_lines)
        theme = get_command_theme("outdated")
        result = render_with_boxy(content, title="🔄 Outdated Packages", theme=theme, header="Update Analysis", width="80")
        print(result)

    else:
        # Original output without boxy
        print(f"\n{Colors.CYAN}{Colors.BOLD}🔄 OUTDATED PACKAGES{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")

        if not outdated:
            print(f"{Colors.GREEN}✅ All packages are up to date!{Colors.END}")
            return

        # Separate breaking and non-breaking updates
        breaking_updates = []
        minor_updates = []

        for pkg, info in outdated.items():
            has_breaking = False
            for current in info['current_versions']:
                if is_breaking_change(current, info['latest']):
                    has_breaking = True
                    break

            if has_breaking:
                breaking_updates.append((pkg, info))
            else:
                minor_updates.append((pkg, info))

        # Display breaking updates
        if breaking_updates:
            print(f"\n{Colors.RED}{Colors.BOLD}⚠️  BREAKING UPDATES ({len(breaking_updates)}):{Colors.END}")
            for pkg, info in sorted(breaking_updates):
                versions = ', '.join(sorted(info['current_versions']))
                print(f"\n  {Colors.BOLD}{pkg}{Colors.END}")
                print(f"    Current: {Colors.YELLOW}{versions}{Colors.END}")
                print(f"    Latest:  {Colors.GREEN}{info['latest']}{Colors.END}")
                print(f"    Used in: {', '.join(info['repos'][:5])}")
                if len(info['repos']) > 5:
                    print(f"             ... and {len(info['repos']) - 5} more")

        # Display minor updates
        if minor_updates:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}📦 MINOR UPDATES ({len(minor_updates)}):{Colors.END}")
            for pkg, info in sorted(minor_updates):
                versions = ', '.join(sorted(info['current_versions']))
                print(f"\n  {Colors.BOLD}{pkg}{Colors.END}")
                print(f"    Current: {Colors.BLUE}{versions}{Colors.END}")
                print(f"    Latest:  {Colors.GREEN}{info['latest']}{Colors.END}")
                print(f"    Used in: {', '.join(info['repos'][:3])}")
                if len(info['repos']) > 3:
                    print(f"             ... and {len(info['repos']) - 3} more")

        print(f"\n{Colors.GRAY}Run 'cargo update' in affected repositories to update non-breaking changes{Colors.END}")

def view_search(ecosystem: EcosystemData, pattern: str) -> None:
    """Search for packages matching a pattern"""
    import re

    # Compile pattern for fuzzy matching
    try:
        # Support both regex and simple substring matching
        if any(c in pattern for c in ['^', '$', '*', '.', '[', ']', '(', ')']):
            regex = re.compile(pattern, re.IGNORECASE)
        else:
            # Convert to fuzzy pattern: "abc" -> ".*a.*b.*c.*"
            fuzzy = '.*'.join(pattern)
            regex = re.compile(f'.*{fuzzy}.*', re.IGNORECASE)
    except re.error:
        print(f"{Colors.RED}❌ Invalid search pattern{Colors.END}")
        return

    # Find matching packages
    matching_packages = {}
    for dep in ecosystem.deps.values():
        if regex.search(dep.pkg_name):
            if dep.pkg_name not in matching_packages:
                matching_packages[dep.pkg_name] = {
                    'versions': set(),
                    'repos': set(),
                    'hub_status': set()
                }
            matching_packages[dep.pkg_name]['versions'].add(dep.pkg_version)
            repo = ecosystem.repos.get(dep.repo_id)
            if repo:
                matching_packages[dep.pkg_name]['repos'].add(repo.repo_name)
                if hasattr(dep, 'hub_status'):
                    matching_packages[dep.pkg_name]['hub_status'].add(dep.hub_status)

    if BOXY_AVAILABLE:
        # Collect output for boxy rendering
        output_lines = []

        if not matching_packages:
            output_lines.append(f"{Colors.YELLOW}No packages found matching '{pattern}'{Colors.END}")
        else:
            # Sort by usage count
            sorted_packages = sorted(matching_packages.items(),
                                   key=lambda x: len(x[1]['repos']), reverse=True)

            output_lines.append(f"{Colors.GREEN}Found {len(matching_packages)} matching packages:{Colors.END}")
            output_lines.append("")

            for pkg, info in sorted_packages[:20]:  # Show top 20 matches
                # Highlight matched portion
                highlighted = regex.sub(lambda m: f"{Colors.YELLOW}{m.group()}{Colors.END}", pkg)

                # Determine status color
                if "HUB" in info['hub_status']:
                    status_color = Colors.GREEN
                    status = "HUB"
                elif "HUB_ONLY" in info['hub_status']:
                    status_color = Colors.BLUE
                    status = "HUB_ONLY"
                else:
                    status_color = Colors.GRAY
                    status = "EXTERNAL"

                versions = ', '.join(sorted(info['versions'])[:3])
                if len(info['versions']) > 3:
                    versions += f", +{len(info['versions']) - 3}"

                output_lines.append(f"  {Colors.BOLD}{highlighted}{Colors.END} {status_color}[{status}]{Colors.END}")
                output_lines.append(f"    Used in: {len(info['repos'])} repos | Versions: {versions}")

            if len(matching_packages) > 20:
                output_lines.append("")
                output_lines.append(f"{Colors.GRAY}... and {len(matching_packages) - 20} more matches{Colors.END}")

        # Render with boxy
        content = "\n".join(output_lines)
        theme = get_command_theme("search")
        result = render_with_boxy(content, title=f"🔍 Package Search: '{pattern}'", theme=theme, header="Search Results", width="80")
        print(result)

    else:
        # Original output without boxy
        print(f"\n{Colors.CYAN}{Colors.BOLD}🔍 PACKAGE SEARCH: '{pattern}'{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")

        if not matching_packages:
            print(f"{Colors.YELLOW}No packages found matching '{pattern}'{Colors.END}")
            return

        # Sort by usage count
        sorted_packages = sorted(matching_packages.items(),
                               key=lambda x: len(x[1]['repos']), reverse=True)

        print(f"\n{Colors.GREEN}Found {len(matching_packages)} matching packages:{Colors.END}\n")

        for pkg, info in sorted_packages[:20]:  # Show top 20 matches
            # Highlight matched portion
            highlighted = regex.sub(lambda m: f"{Colors.YELLOW}{m.group()}{Colors.END}", pkg)

            # Determine status color
            if "HUB" in info['hub_status']:
                status_color = Colors.GREEN
                status = "HUB"
            elif "HUB_ONLY" in info['hub_status']:
                status_color = Colors.BLUE
                status = "HUB_ONLY"
            else:
                status_color = Colors.GRAY
                status = "EXTERNAL"

            versions = ', '.join(sorted(info['versions'])[:3])
            if len(info['versions']) > 3:
                versions += f", +{len(info['versions']) - 3}"

            print(f"  {Colors.BOLD}{highlighted}{Colors.END} {status_color}[{status}]{Colors.END}")
            print(f"    Used in: {len(info['repos'])} repos | Versions: {versions}")

        if len(matching_packages) > 20:
            print(f"\n{Colors.GRAY}... and {len(matching_packages) - 20} more matches{Colors.END}")

def view_graph(ecosystem: EcosystemData, package: str) -> None:
    """Show dependency graph for a package"""
    # Find exact package match
    package_deps = [dep for dep in ecosystem.deps.values() if dep.pkg_name == package]

    if not package_deps:
        # Try fuzzy match
        fuzzy_matches = [dep.pkg_name for dep in ecosystem.deps.values()
                        if package.lower() in dep.pkg_name.lower()]
        if fuzzy_matches:
            unique_matches = list(set(fuzzy_matches))
            print(f"{Colors.YELLOW}Package '{package}' not found. Did you mean:{Colors.END}")
            for match in unique_matches[:5]:
                print(f"  • {match}")
        else:
            print(f"{Colors.RED}❌ Package '{package}' not found{Colors.END}")
        return

    if BOXY_AVAILABLE:
        # Collect output for boxy rendering
        output_lines = []

        # Build dependency relationships
        output_lines.append(f"{Colors.YELLOW}📦 Package: {Colors.BOLD}{package}{Colors.END}")

        # Get latest version info
        latest = ecosystem.latest.get(package)
        if latest:
            output_lines.append(f"Latest Version: {Colors.GREEN}{latest.latest_version}{Colors.END}")

        # Show which repos use this package
        using_repos = {}
        for dep in package_deps:
            repo = ecosystem.repos.get(dep.repo_id)
            if repo:
                if repo.repo_name not in using_repos:
                    using_repos[repo.repo_name] = []
                using_repos[repo.repo_name].append({
                    'version': dep.pkg_version,
                    'type': dep.dep_type,
                    'features': dep.features
                })

        output_lines.append("")
        output_lines.append(f"{Colors.YELLOW}Used by {len(using_repos)} repositories:{Colors.END}")
        for repo_name, deps in sorted(using_repos.items())[:10]:
            for dep_info in deps:
                dep_type_marker = ""
                if dep_info['type'] == "dev-dep":
                    dep_type_marker = " [dev]"
                elif dep_info['type'] == "build-dep":
                    dep_type_marker = " [build]"

                features = f" {{{dep_info['features']}}}" if dep_info['features'] and dep_info['features'] != "[]" and dep_info['features'] != "NONE" else ""

                # Check if update available
                update_marker = ""
                if latest and dep_info['version'] != latest.latest_version and latest.latest_version != "LOCAL":
                    if is_breaking_change(dep_info['version'], latest.latest_version):
                        update_marker = f" {Colors.RED}(breaking update available){Colors.END}"
                    else:
                        update_marker = f" {Colors.YELLOW}(update available){Colors.END}"

                output_lines.append(f"  {Colors.BLUE}├─{Colors.END} {repo_name}: {Colors.GREEN}{dep_info['version']}{Colors.END}{dep_type_marker}{features}{update_marker}")

        if len(using_repos) > 10:
            output_lines.append(f"  {Colors.GRAY}... and {len(using_repos) - 10} more{Colors.END}")

        # Show version distribution
        version_counts = {}
        for dep in package_deps:
            version_counts[dep.pkg_version] = version_counts.get(dep.pkg_version, 0) + 1

        if len(version_counts) > 1:
            output_lines.append("")
            output_lines.append(f"{Colors.YELLOW}Version Distribution:{Colors.END}")
            for version, count in sorted(version_counts.items(), key=lambda x: x[1], reverse=True):
                bar_length = int((count / max(version_counts.values())) * 20)
                bar = "█" * bar_length
                status = ""
                if latest and version != latest.latest_version and latest.latest_version != "LOCAL":
                    if is_breaking_change(version, latest.latest_version):
                        status = f" {Colors.RED}(outdated - breaking){Colors.END}"
                    else:
                        status = f" {Colors.YELLOW}(outdated){Colors.END}"
                output_lines.append(f"  {version:10} {Colors.GREEN}{bar}{Colors.END} ({count} repos){status}")

        # Render with boxy
        content = "\n".join(output_lines)
        theme = get_command_theme("graph")
        result = render_with_boxy(content, title=f"🌳 Dependency Graph: {package}", theme=theme, header="Package Analysis", width="80")
        print(result)

    else:
        # Original output without boxy
        print(f"\n{Colors.CYAN}{Colors.BOLD}🌳 DEPENDENCY GRAPH: {package}{Colors.END}")
        print(f"{Colors.GRAY}{'-'*80}{Colors.END}")

        # Build dependency relationships
        print(f"\n{Colors.YELLOW}📦 Package: {Colors.BOLD}{package}{Colors.END}")

        # Get latest version info
        latest = ecosystem.latest.get(package)
        if latest:
            print(f"Latest Version: {Colors.GREEN}{latest.latest_version}{Colors.END}")

        # Show which repos use this package
        using_repos = {}
        for dep in package_deps:
            repo = ecosystem.repos.get(dep.repo_id)
            if repo:
                if repo.repo_name not in using_repos:
                    using_repos[repo.repo_name] = []
                using_repos[repo.repo_name].append({
                    'version': dep.pkg_version,
                    'type': dep.dep_type,
                    'features': dep.features
                })

        print(f"\n{Colors.YELLOW}Used by {len(using_repos)} repositories:{Colors.END}")
        for repo_name, deps in sorted(using_repos.items())[:10]:
            for dep_info in deps:
                dep_type_marker = ""
                if dep_info['type'] == "dev-dep":
                    dep_type_marker = " [dev]"
                elif dep_info['type'] == "build-dep":
                    dep_type_marker = " [build]"

                features = f" {{{dep_info['features']}}}" if dep_info['features'] and dep_info['features'] != "[]" and dep_info['features'] != "NONE" else ""

                # Check if update available
                update_marker = ""
                if latest and dep_info['version'] != latest.latest_version and latest.latest_version != "LOCAL":
                    if is_breaking_change(dep_info['version'], latest.latest_version):
                        update_marker = f" {Colors.RED}(breaking update available){Colors.END}"
                    else:
                        update_marker = f" {Colors.YELLOW}(update available){Colors.END}"

                print(f"  {Colors.BLUE}├─{Colors.END} {repo_name}: {Colors.GREEN}{dep_info['version']}{Colors.END}{dep_type_marker}{features}{update_marker}")

        if len(using_repos) > 10:
            print(f"  {Colors.GRAY}... and {len(using_repos) - 10} more{Colors.END}")

        # Show version distribution
        version_counts = {}
        for dep in package_deps:
            version_counts[dep.pkg_version] = version_counts.get(dep.pkg_version, 0) + 1

        if len(version_counts) > 1:
            print(f"\n{Colors.YELLOW}Version Distribution:{Colors.END}")
            for version, count in sorted(version_counts.items(), key=lambda x: x[1], reverse=True):
                bar_length = int((count / max(version_counts.values())) * 20)
                bar = "█" * bar_length
                status = ""
                if latest and version != latest.latest_version and latest.latest_version != "LOCAL":
                    if is_breaking_change(version, latest.latest_version):
                        status = f" {Colors.RED}(outdated - breaking){Colors.END}"
                    else:
                        status = f" {Colors.YELLOW}(outdated){Colors.END}"
                print(f"  {version:10} {Colors.GREEN}{bar}{Colors.END} ({count} repos){status}")

def discover_repositories(force_live=False):
    """Discover repository paths using cache or live discovery

    Args:
        force_live: If True, force live discovery even if cache exists

    Returns:
        List[Path]: List of repository paths
    """
    if not force_live:
        try:
            ecosystem = hydrate_tsv_cache()
            # repo.path includes Cargo.toml, so get parent directory
            repo_paths = [(Path(RUST_REPO_ROOT) / repo.path).parent for repo in ecosystem.repos.values()]
            print(f"{Colors.GREEN}📋 Found {len(repo_paths)} repositories from cache{Colors.END}")
            return repo_paths
        except FileNotFoundError:
            print(f"{Colors.YELLOW}⚠️  Cache not found, discovering repositories...{Colors.END}")

    # Live discovery
    print(f"{Colors.CYAN}🔍 Live discovery: scanning filesystem...{Colors.END}")
    cargo_files = find_all_cargo_files_fast()
    repo_paths = [path.parent for path in cargo_files]
    print(f"{Colors.GREEN}📋 Found {len(repo_paths)} repositories via live discovery{Colors.END}")
    return repo_paths

def list_repositories(force_live=False):
    """List all repository names"""
    print(f"{Colors.CYAN}{Colors.BOLD}📂 Repository List{Colors.END}")

    repo_paths = discover_repositories(force_live)

    if not repo_paths:
        print(f"{Colors.RED}❌ No repositories found{Colors.END}")
        return

    print(f"\n{Colors.WHITE}Found {len(repo_paths)} repositories:{Colors.END}")
    for i, repo_path in enumerate(sorted(repo_paths, key=lambda p: p.name), 1):
        print(f"{Colors.BLUE}{i:2d}.{Colors.END} {Colors.BOLD}{repo_path.name}{Colors.END}")

def superclean_targets():
    """Clean target directories across all ecosystem repositories"""
    print(f"{Colors.CYAN}{Colors.BOLD}🧹 SuperClean: Cleaning all target directories in ecosystem{Colors.END}")

    repo_paths = discover_repositories()

    cleaned_count = 0
    total_size_freed = 0

    # Initialize progress spinner
    progress = ProgressSpinner("Initializing cleanup...", len(repo_paths))
    progress.start()

    try:
        for i, repo_path in enumerate(repo_paths):
            progress.update(i, f"Processing {repo_path.name}...")

            target_path = repo_path / "target"
            cargo_toml_path = repo_path / "Cargo.toml"

            # Only process if there's a Cargo.toml file
            if not cargo_toml_path.exists():
                continue

            if target_path.exists() and target_path.is_dir():
                try:
                    progress.update(i, f"Cleaning {repo_path.name}...")

                    # Get size before cleaning
                    result = subprocess.run(['du', '-sh', str(target_path)],
                                          capture_output=True, text=True, timeout=10)
                    size_str = result.stdout.split('\t')[0] if result.returncode == 0 else "unknown"

                    # Use cargo clean in the repo directory
                    result = subprocess.run(['cargo', 'clean'],
                                          cwd=str(repo_path),
                                          capture_output=True, text=True, timeout=60)

                    if result.returncode == 0:
                        cleaned_count += 1
                        # Try to extract numeric size for total
                        if size_str.endswith('M'):
                            total_size_freed += float(size_str[:-1])
                        elif size_str.endswith('G'):
                            total_size_freed += float(size_str[:-1]) * 1024
                        elif size_str.endswith('K'):
                            total_size_freed += float(size_str[:-1]) / 1024

                except subprocess.TimeoutExpired:
                    pass  # Continue with other repos
                except subprocess.CalledProcessError:
                    pass  # Continue with other repos
                except Exception:
                    pass  # Continue with other repos

        # Final update
        progress.update(len(repo_paths), "Cleanup complete!")

    finally:
        progress.stop()

    # Summary
    print(f"\n{Colors.GREEN}{Colors.BOLD}✅ SuperClean Complete!{Colors.END}")
    print(f"   🗑️  Cleaned {cleaned_count} target directories")
    if total_size_freed > 0:
        if total_size_freed > 1024:
            print(f"   💾 Freed approximately {total_size_freed/1024:.1f}GB of disk space")
        else:
            print(f"   💾 Freed approximately {total_size_freed:.0f}MB of disk space")

def test_ssh_connection(ssh_profile=None):
    """Test SSH connection with configurable profile

    Args:
        ssh_profile: SSH profile/host. Defaults to RUST_SSH_PROFILE env var or 'github.com'
                    Use 'qodeninja' for your custom profile

    Returns:
        bool: True if SSH connection successful, False otherwise
    """
    # Configure SSH test command with environment variable fallback
    if ssh_profile is None:
        ssh_profile = os.environ.get('RUST_SSH_PROFILE', 'github.com')

    ssh_test_cmd = ['ssh', '-T', f'git@{ssh_profile}']
    expected_success_text = "successfully authenticated"

    # Test SSH connection
    print(f"{Colors.YELLOW}🔐 Testing SSH connection: {' '.join(ssh_test_cmd)}...{Colors.END}")
    try:
        result = subprocess.run(ssh_test_cmd,
                              capture_output=True, text=True, timeout=10)

        # Check for success in both stdout and stderr
        output_text = (result.stdout + result.stderr).lower()
        if expected_success_text in output_text or result.returncode == 0:
            print(f"{Colors.GREEN}✅ SSH connection verified{Colors.END}")
            return True
        else:
            print(f"{Colors.RED}❌ SSH connection failed. Please check your SSH key setup.{Colors.END}")
            print(f"   Test command: {' '.join(ssh_test_cmd)}")
            print(f"   Output: {result.stderr or result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}❌ SSH connection timeout{Colors.END}")
        return False
    except Exception as e:
        print(f"{Colors.RED}❌ SSH test failed: {e}{Colors.END}")
        return False

def tap_repositories(ssh_profile=None):
    """Tap repositories - commit changes always, push only if SSH test passes

    Args:
        ssh_profile: SSH profile/host. Defaults to 'github.com'
                    Use 'qodeninja' for your custom profile
    """
    from datetime import datetime

    print(f"{Colors.CYAN}{Colors.BOLD}🚰 Tap: Auto-committing across ecosystem repositories{Colors.END}")

    # Test SSH connection to determine if we can push
    ssh_ok = test_ssh_connection(ssh_profile)
    if ssh_ok:
        print(f"{Colors.GREEN}🔗 SSH verified - will commit and push changes{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  SSH failed - will only commit changes (no push){Colors.END}")

    # Get repository list
    repo_paths = discover_repositories()

    committed_count = 0
    pushed_count = 0
    skipped_count = 0
    error_count = 0
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Initialize progress spinner
    progress = ProgressSpinner("Initializing tap...", len(repo_paths))
    progress.start()

    try:
        for i, repo_path in enumerate(repo_paths):
            progress.update(i, f"Tapping {repo_path.name}...")

            # Skip if not a git repository
            if not (repo_path / ".git").exists():
                skipped_count += 1
                continue

            try:
                # Check git status
                result = subprocess.run(['git', 'status', '--porcelain'],
                                      cwd=str(repo_path),
                                      capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    error_count += 1
                    continue

                # If there are changes, add and commit them
                if result.stdout.strip():
                    progress.update(i, f"Committing changes in {repo_path.name}...")

                    # Add all changes
                    add_result = subprocess.run(['git', 'add', '.'],
                                              cwd=str(repo_path),
                                              capture_output=True, text=True, timeout=30)

                    if add_result.returncode != 0:
                        error_count += 1
                        continue

                    # Commit with standardized message
                    commit_message = f"fix: hub batch auto tap {current_date}"
                    commit_result = subprocess.run(['git', 'commit', '-m', commit_message],
                                                 cwd=str(repo_path),
                                                 capture_output=True, text=True, timeout=30)

                    if commit_result.returncode == 0:
                        committed_count += 1

                        # If SSH is OK, also push the changes
                        if ssh_ok:
                            progress.update(i, f"Pushing changes in {repo_path.name}...")
                            push_result = subprocess.run(['git', 'push'],
                                                       cwd=str(repo_path),
                                                       capture_output=True, text=True, timeout=60)

                            if push_result.returncode == 0:
                                pushed_count += 1
                            # Don't count push failure as error - commit succeeded
                    else:
                        error_count += 1
                else:
                    # No changes to commit
                    skipped_count += 1

            except subprocess.TimeoutExpired:
                error_count += 1
            except Exception:
                error_count += 1

        # Final update
        progress.update(len(repo_paths), "Tap complete!")

    finally:
        progress.stop()

    # Summary
    print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Tap Complete!{Colors.END}")
    print(f"   📝 Committed changes in {committed_count} repositories")
    if ssh_ok and pushed_count > 0:
        print(f"   🚀 Pushed changes in {pushed_count} repositories")
    elif ssh_ok and committed_count > 0:
        print(f"   📤 SSH OK but no pushes needed")
    elif not ssh_ok and committed_count > 0:
        print(f"   🔒 Changes committed locally only (SSH failed)")
    print(f"   ⏭️  Skipped {skipped_count} repositories (no changes or not git repos)")
    if error_count > 0:
        print(f"   ❌ Errors in {error_count} repositories")

def write_cargo_toml_manually(cargo_path: Path, package_name: str, version: str, domain: str) -> bool:
    """Manually append a new dependency to Cargo.toml by editing the file directly"""
    try:
        with open(cargo_path, 'r') as f:
            lines = f.readlines()

        # Find the dependencies section
        dep_section_start = -1
        dep_section_end = -1
        in_dependencies = False

        for i, line in enumerate(lines):
            if line.strip() == '[dependencies]':
                dep_section_start = i
                in_dependencies = True
            elif in_dependencies and line.strip().startswith('['):
                dep_section_end = i
                break

        if dep_section_start == -1:
            print(f"{Colors.RED}❌ Could not find [dependencies] section in Cargo.toml{Colors.END}")
            return False

        # If no end found, it means dependencies is the last section
        if dep_section_end == -1:
            dep_section_end = len(lines)

        # Insert the new dependency before the end of the dependencies section
        # Find the last non-empty line in dependencies section
        insert_pos = dep_section_end
        for i in range(dep_section_end - 1, dep_section_start, -1):
            if lines[i].strip():
                insert_pos = i + 1
                break

        # Create the new dependency line
        dep_line = f'{package_name} = {{ version = "{version}", optional = true }}\n'

        # Insert the new dependency
        lines.insert(insert_pos, dep_line)

        # Now update the features section
        # Find the features section
        features_start = -1
        for i, line in enumerate(lines):
            if line.strip() == '[features]':
                features_start = i
                break

        if features_start == -1:
            print(f"{Colors.RED}❌ Could not find [features] section in Cargo.toml{Colors.END}")
            return False

        # Find the domain feature line
        domain_found = False
        for i in range(features_start + 1, len(lines)):
            if lines[i].startswith(f'{domain} = '):
                # Parse the existing array and add our package
                line = lines[i]
                # Extract the array content
                start_idx = line.index('[')
                end_idx = line.rindex(']')
                array_content = line[start_idx+1:end_idx]

                # Parse existing items
                items = []
                if array_content.strip():
                    items = [item.strip().strip('"') for item in array_content.split(',')]

                # Add our package if not already there
                if package_name not in items:
                    items.append(package_name)

                # Reconstruct the line
                formatted_items = ', '.join(f'"{item}"' for item in items)
                lines[i] = f'{domain} = [{formatted_items}]\n'
                domain_found = True
                break
            elif lines[i].strip().startswith('['):
                # We've reached another section
                break

        if not domain_found:
            # Need to add the domain feature
            # Find where to insert it (after the features line)
            for i in range(features_start + 1, len(lines)):
                if lines[i].strip() == '' or lines[i].strip().startswith('['):
                    lines.insert(i, f'{domain} = ["{package_name}"]\n')
                    break

        # Add package's own feature if not exists
        package_feature_line = f'{package_name} = ["dep:{package_name}"]\n'
        package_feature_found = False

        for i in range(features_start + 1, len(lines)):
            if lines[i].startswith(f'{package_name} = '):
                package_feature_found = True
                break
            elif lines[i].strip().startswith('['):
                # Insert before the next section
                lines.insert(i, package_feature_line)
                break

        if not package_feature_found and not any(package_feature_line in line for line in lines):
            # Find the end of features section and add it there
            for i in range(features_start + 1, len(lines)):
                if lines[i].strip().startswith('[') or i == len(lines) - 1:
                    insert_pos = i if lines[i].strip().startswith('[') else i + 1
                    lines.insert(insert_pos, package_feature_line)
                    break

        # Write the file back
        with open(cargo_path, 'w') as f:
            f.writelines(lines)

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ Error manually editing Cargo.toml: {e}{Colors.END}")
        return False

def learn_package(ecosystem: EcosystemData, package_name: str) -> bool:
    """Learn a package by adding it to hub's Cargo.toml with its latest version"""

    # Skip RSB package
    if package_name.lower() == 'rsb':
        print(f"{Colors.YELLOW}⚠️  Cannot learn 'rsb' package (circular dependency){Colors.END}")
        return False

    # Check if package exists in ecosystem
    if package_name not in ecosystem.latest:
        print(f"{Colors.RED}❌ Package '{package_name}' not found in ecosystem{Colors.END}")
        return False

    pkg_info = ecosystem.latest[package_name]

    # Check if already in hub
    if pkg_info.hub_status in ['current', 'outdated']:
        print(f"{Colors.YELLOW}⚠️  Package '{package_name}' already in hub (status: {pkg_info.hub_status}){Colors.END}")
        return False

    # Get the latest stable version
    latest_version = pkg_info.latest_stable_version or pkg_info.latest_version

    # Load hub's Cargo.toml path (using configurable HUB_PATH)
    if not HUB_PATH:
        print(f"{Colors.RED}❌ HUB_PATH not configured. Set HUB_HOME or HUB_PATH environment variable.{Colors.END}")
        return False
    hub_cargo_path = Path(HUB_PATH) / "Cargo.toml"

    # Determine which domain feature group this package belongs to
    domain = categorize_package(package_name)

    # Try to use toml library first, fallback to manual editing
    try:
        import toml
        cargo_data = load_toml(hub_cargo_path)

        # Ensure dependencies section exists
        if 'dependencies' not in cargo_data:
            cargo_data['dependencies'] = {}

        # Add the package with optional = true (for feature gating)
        cargo_data['dependencies'][package_name] = {
            'version': latest_version,
            'optional': True
        }

        # Update features section to include this package
        if 'features' not in cargo_data:
            cargo_data['features'] = {}

        # Add to domain feature group
        if domain not in cargo_data['features']:
            cargo_data['features'][domain] = []

        if package_name not in cargo_data['features'][domain]:
            cargo_data['features'][domain].append(package_name)

        # Also ensure package has its own feature
        if package_name not in cargo_data['features']:
            cargo_data['features'][package_name] = [f"dep:{package_name}"]

        # Write back the updated Cargo.toml
        with open(hub_cargo_path, 'w') as f:
            toml.dump(cargo_data, f)

        print(f"{Colors.GREEN}✅ Learned '{package_name}' v{latest_version} → {domain} domain{Colors.END}")
        return True

    except ImportError:
        # Fallback to manual editing
        print(f"{Colors.YELLOW}⚠️  toml library not available, using manual editing{Colors.END}")
        if write_cargo_toml_manually(hub_cargo_path, package_name, latest_version, domain):
            print(f"{Colors.GREEN}✅ Learned '{package_name}' v{latest_version} → {domain} domain{Colors.END}")
            return True
        else:
            return False

    except Exception as e:
        print(f"{Colors.RED}❌ Failed to update hub's Cargo.toml: {e}{Colors.END}")
        return False

def categorize_package(package_name: str) -> str:
    """Categorize package into a domain based on its name/purpose"""
    # Common categorization patterns
    text_packages = ['regex', 'unicode', 'string', 'text', 'markdown', 'html']
    data_packages = ['serde', 'json', 'toml', 'yaml', 'csv', 'xml', 'bincode']
    time_packages = ['chrono', 'time', 'date', 'duration', 'timer']
    web_packages = ['http', 'url', 'reqwest', 'hyper', 'actix', 'warp', 'rocket', 'tower']
    system_packages = ['libc', 'nix', 'winapi', 'os', 'env', 'process', 'fs']
    dev_packages = ['log', 'tracing', 'env_logger', 'pretty', 'debug', 'test']
    random_packages = ['rand', 'uuid', 'nanoid', 'random']

    name_lower = package_name.lower()

    # Check each category
    for keyword in text_packages:
        if keyword in name_lower:
            return 'text'

    for keyword in data_packages:
        if keyword in name_lower:
            return 'data'

    for keyword in time_packages:
        if keyword in name_lower:
            return 'time'

    for keyword in web_packages:
        if keyword in name_lower:
            return 'web'

    for keyword in system_packages:
        if keyword in name_lower:
            return 'system'

    for keyword in dev_packages:
        if keyword in name_lower:
            return 'dev'

    for keyword in random_packages:
        if keyword in name_lower:
            return 'random'

    # Default to 'common' for uncategorized packages
    return 'common'

def add_hub_metadata_section(cargo_path: Path, repo_name: str) -> bool:
    """Add [package.metadata.hub] section to a Cargo.toml file"""
    try:
        with open(cargo_path, 'r') as f:
            lines = f.readlines()

        # Check if the section already exists
        for line in lines:
            if '[package.metadata.hub]' in line:
                print(f"{Colors.YELLOW}⚠️  [package.metadata.hub] section already exists{Colors.END}")
                return False

        # Find where to insert the metadata section
        # Look for [package.metadata] first, or [package] section
        package_metadata_idx = -1
        package_idx = -1

        for i, line in enumerate(lines):
            if line.strip() == '[package.metadata]':
                package_metadata_idx = i
            elif line.strip() == '[package]':
                package_idx = i

        # Prepare the hub metadata section
        hub_section = [
            '\n',
            '[package.metadata.hub]\n',
            f'notes = "Hub metadata for {repo_name} repository"\n',
            'hub_sync = "true"  # Set to "false" to skip this repo in hub updates\n',
            '# priority = "medium"  # Options: high, medium, low\n',
            '# Add any custom fields below\n'
        ]

        # Insert the section at the appropriate location
        insert_idx = -1

        if package_idx != -1:
            # Find the end of the [package] section
            insert_idx = package_idx + 1
            while insert_idx < len(lines) and not lines[insert_idx].strip().startswith('['):
                insert_idx += 1

            # Insert before the next section
            for section_line in hub_section:
                lines.insert(insert_idx, section_line)
                insert_idx += 1
        else:
            # If no [package] section found, append at the end
            lines.extend(hub_section)

        # Write the file back
        with open(cargo_path, 'w') as f:
            f.writelines(lines)

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ Error adding hub metadata section: {e}{Colors.END}")
        return False

def view_repo_notes(ecosystem: EcosystemData, repo_name: str, create_if_missing: bool = False) -> None:
    """Display hub annotations/notes for a specific repository, optionally creating the section if missing"""

    # Find the repository
    repo_found = None
    for repo in ecosystem.repos.values():
        if repo.repo_name.lower() == repo_name.lower():
            repo_found = repo
            break

    if not repo_found:
        print(f"{Colors.RED}❌ Repository '{repo_name}' not found{Colors.END}")
        print(f"\nAvailable repositories:")
        for repo in sorted(ecosystem.repos.values(), key=lambda r: r.repo_name):
            print(f"  • {repo.repo_name}")
        return

    # Load the Cargo.toml to get fresh metadata
    # Note: repo_found.path already includes "Cargo.toml"
    cargo_path = Path(RUST_REPO_ROOT) / repo_found.path

    try:
        cargo_data = load_toml(cargo_path)
        hub_meta = cargo_data.get('package', {}).get('metadata', {}).get('hub', {})

        print(f"{Colors.PURPLE}{Colors.BOLD}📝 HUB NOTES: {repo_found.repo_name}{Colors.END}")
        print(f"{Colors.PURPLE}{'='*80}{Colors.END}\n")

        if not hub_meta:
            if create_if_missing:
                # Create the metadata section
                print(f"{Colors.CYAN}📝 Creating hub metadata section for {repo_found.repo_name}...{Colors.END}")

                # Add the section to the Cargo.toml file
                if add_hub_metadata_section(cargo_path, repo_found.repo_name):
                    print(f"{Colors.GREEN}✅ Added [package.metadata.hub] section to {repo_found.repo_name}'s Cargo.toml{Colors.END}")
                    print(f"\n{Colors.CYAN}You can now edit the following fields:{Colors.END}")
                    print(f"  • notes - Description and notes about the repository")
                    print(f"  • hub_sync - Set to 'false' to skip in hub updates")
                    print(f"  • priority - Set to 'high', 'medium', or 'low'")
                    print(f"  • Add any custom fields as needed")
                else:
                    print(f"{Colors.RED}❌ Failed to add metadata section{Colors.END}")
            else:
                print(f"{Colors.GRAY}No hub metadata found for {repo_found.repo_name}{Colors.END}")
                print(f"\n{Colors.CYAN}💡 To add notes automatically, run:{Colors.END}")
                print(f"{Colors.WHITE}  repos.py notes {repo_found.repo_name} --create{Colors.END}")
                print(f"\n{Colors.CYAN}Or manually add this to {repo_found.repo_name}'s Cargo.toml:{Colors.END}")
                print(f"{Colors.GRAY}[package.metadata.hub]{Colors.END}")
                print(f'{Colors.GRAY}notes = "Your notes about this repo"{Colors.END}')
                print(f'{Colors.GRAY}hub_sync = "true"  # or "false" to skip in updates{Colors.END}')
                print(f'{Colors.GRAY}priority = "high"   # or "medium", "low"{Colors.END}')
            return

        # Display all hub metadata
        print(f"{Colors.WHITE}Repository: {Colors.CYAN}{repo_found.repo_name}{Colors.END}")
        print(f"{Colors.WHITE}Path: {Colors.GRAY}{repo_found.path}{Colors.END}")
        print(f"{Colors.WHITE}Version: {Colors.GRAY}{repo_found.cargo_version}{Colors.END}")
        print()

        # Display each metadata field
        for key, value in hub_meta.items():
            if key == 'notes':
                print(f"{Colors.WHITE}{Colors.BOLD}Notes:{Colors.END}")
                # Handle multiline notes
                if isinstance(value, str):
                    for line in value.split('\n'):
                        print(f"  {Colors.WHITE}{line}{Colors.END}")
                else:
                    print(f"  {Colors.WHITE}{value}{Colors.END}")
            elif key == 'hub_sync':
                status_color = Colors.GREEN if value != "false" else Colors.YELLOW
                print(f"{Colors.WHITE}Hub Sync: {status_color}{value}{Colors.END}")
            elif key == 'priority':
                priority_colors = {
                    'high': Colors.RED,
                    'medium': Colors.YELLOW,
                    'low': Colors.GRAY
                }
                color = priority_colors.get(value.lower(), Colors.WHITE)
                print(f"{Colors.WHITE}Priority: {color}{value}{Colors.END}")
            else:
                # Display any other custom fields
                print(f"{Colors.WHITE}{key.title()}: {Colors.CYAN}{value}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}❌ Error reading metadata from {cargo_path}: {e}{Colors.END}")

def learn_all_opportunities(ecosystem: EcosystemData) -> int:
    """Learn all package opportunities from hub analysis"""

    print(f"{Colors.PURPLE}{Colors.BOLD}🎓 LEARNING HUB OPPORTUNITIES{Colors.END}")
    print(f"{Colors.PURPLE}{'='*80}{Colors.END}\n")

    # Get packages that are actually IN the hub (current or outdated, not gap)
    actual_hub_packages = {name for name, info in ecosystem.latest.items()
                          if info.hub_status in ['current', 'outdated']}

    # Count usage excluding hub repository and local/workspace
    hub_repo_id = get_hub_repo_id(ecosystem)
    all_packages = {}
    for dep in ecosystem.deps.values():
        # Skip dependencies that should be excluded
        if should_exclude_from_stats(dep, hub_repo_id):
            continue

        pkg_name = dep.pkg_name
        if pkg_name not in all_packages:
            all_packages[pkg_name] = set()
        all_packages[pkg_name].add(dep.repo_id)

    # Convert to usage counts
    package_usage = {pkg: len(repos) for pkg, repos in all_packages.items()}

    # Find opportunities (5+ usage, not in hub, not rsb)
    opportunities = []
    for pkg_name, usage_count in package_usage.items():
        if usage_count >= 5 and pkg_name not in actual_hub_packages and pkg_name.lower() != 'rsb':
            opportunities.append((pkg_name, usage_count))

    if not opportunities:
        print(f"{Colors.YELLOW}⚠️  No package opportunities found (5+ usage, not in hub){Colors.END}")
        return 0

    # Sort by usage count
    opportunities.sort(key=lambda x: -x[1])

    print(f"Found {len(opportunities)} packages to learn:\n")
    for pkg_name, count in opportunities:
        print(f"  • {pkg_name} (used by {count} repos)")

    print(f"\n{Colors.CYAN}Learning packages...{Colors.END}\n")

    learned_count = 0
    for pkg_name, _ in opportunities:
        if learn_package(ecosystem, pkg_name):
            learned_count += 1

    print(f"\n{Colors.GREEN}✅ Successfully learned {learned_count}/{len(opportunities)} packages{Colors.END}")

    if learned_count > 0:
        print(f"\n{Colors.CYAN}ℹ️  Remember to run 'cargo check' to verify the additions{Colors.END}")

    return learned_count

def scan_git_dependencies(args=None):
    """Scan all Cargo.toml files for git dependencies and test accessibility"""
    import subprocess
    from pathlib import Path

    fix_urls = args and args.package == 'fix-urls'
    dry_run = args and args.dry_run

    print(f"{Colors.CYAN}{Colors.BOLD}🔍 Git Dependency Scanner{Colors.END}")
    print(f"{Colors.GRAY}Scanning for git dependencies and testing accessibility...{Colors.END}")
    if fix_urls:
        mode = "DRY RUN - no changes" if dry_run else "WILL FIX URLS"
        print(f"{Colors.YELLOW}Mode: {mode}{Colors.END}")
    print()

    if not RUST_REPO_ROOT:
        print(f"{Colors.RED}❌ RUST_REPO_ROOT not set{Colors.END}")
        return

    # Find all Cargo.toml files (using find_all_cargo_files_fast to respect exclusions)
    cargo_files = find_all_cargo_files_fast()
    print(f"Found {len(cargo_files)} Cargo.toml files (excluding bak/dev/archive/howto/ref)")
    print()

    git_deps = {}  # {git_url: [(cargo_file, dep_name, ref)]}
    broken_deps = []
    https_deps = []
    ssh_deps = []

    # Scan all Cargo.toml files for git dependencies
    for cargo_path in cargo_files:
        try:
            cargo_data = load_toml(cargo_path)

            for section in ['dependencies', 'dev-dependencies']:
                if section in cargo_data:
                    for dep_name, dep_info in cargo_data[section].items():
                        if isinstance(dep_info, dict) and 'git' in dep_info:
                            git_url = dep_info['git']
                            git_ref = dep_info.get('rev', dep_info.get('branch', dep_info.get('tag', 'main')))

                            if git_url not in git_deps:
                                git_deps[git_url] = []
                            git_deps[git_url].append((cargo_path, dep_name, git_ref))

                            # Categorize by URL type
                            if git_url.startswith('https://'):
                                if git_url not in [d[0] for d in https_deps]:
                                    https_deps.append((git_url, git_ref))
                            elif git_url.startswith('ssh://') or git_url.startswith('git@'):
                                if git_url not in [d[0] for d in ssh_deps]:
                                    ssh_deps.append((git_url, git_ref))
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Could not parse {cargo_path}: {e}{Colors.END}")

    print(f"{Colors.CYAN}📊 Git Dependency Summary:{Colors.END}")
    print(f"  Total unique git repos: {len(git_deps)}")
    print(f"  HTTPS URLs: {len(https_deps)}")
    print(f"  SSH URLs: {len(ssh_deps)}")
    print()

    # Test each unique git URL
    print(f"{Colors.CYAN}🧪 Testing accessibility:{Colors.END}")
    print()

    accessible = []
    needs_auth = []
    not_found = []
    timeouts = []

    for git_url in git_deps.keys():
        print(f"Testing: {git_url}... ", end='', flush=True)

        try:
            # Set environment to block prompts
            git_env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}

            result = subprocess.run(
                ['git', 'ls-remote', '--heads', git_url],
                capture_output=True,
                text=True,
                timeout=3,
                env=git_env,
                stdin=subprocess.DEVNULL
            )

            if result.returncode == 0:
                print(f"{Colors.GREEN}✓ accessible{Colors.END}")
                accessible.append(git_url)
            else:
                error_msg = result.stderr.lower()
                if 'permission denied' in error_msg or 'authentication failed' in error_msg or 'could not read username' in error_msg:
                    print(f"{Colors.YELLOW}⚠ AUTH_REQUIRED{Colors.END}")
                    needs_auth.append((git_url, result.stderr.strip()[:100]))
                elif 'not found' in error_msg or 'could not read' in error_msg or 'does not appear' in error_msg:
                    print(f"{Colors.RED}✗ NOT_FOUND{Colors.END}")
                    not_found.append((git_url, result.stderr.strip()[:100]))
                else:
                    print(f"{Colors.RED}✗ ERROR{Colors.END}")
                    not_found.append((git_url, result.stderr.strip()[:100]))
        except subprocess.TimeoutExpired:
            print(f"{Colors.ORANGE}⏱ TIMEOUT{Colors.END}")
            timeouts.append(git_url)
        except Exception as e:
            print(f"{Colors.RED}✗ {str(e)[:50]}{Colors.END}")

    print()
    print(f"{Colors.CYAN}{Colors.BOLD}📋 Results Summary:{Colors.END}")
    print()

    if accessible:
        print(f"{Colors.GREEN}✓ Accessible ({len(accessible)}):{Colors.END}")
        for url in accessible:
            print(f"  {url}")
        print()

    if needs_auth:
        print(f"{Colors.YELLOW}⚠ Requires Authentication ({len(needs_auth)}):{Colors.END}")
        for url, _ in needs_auth:
            uses = git_deps[url]
            print(f"  {url}")
            print(f"    Used in {len(uses)} files:")
            for cargo_path, dep_name, ref in uses[:3]:  # Show first 3
                rel_path = str(cargo_path).replace(str(RUST_REPO_ROOT) + '/', '')
                print(f"      - {rel_path} ({dep_name})")
            if len(uses) > 3:
                print(f"      ... and {len(uses) - 3} more")
        print()
        print(f"{Colors.CYAN}💡 Fix: Run 'blade fix-git' to configure cargo for SSH authentication{Colors.END}")
        print()

    if not_found:
        print(f"{Colors.RED}✗ Not Found / Moved ({len(not_found)}):{Colors.END}")
        for url, error in not_found:
            uses = git_deps[url]
            print(f"  {url}")
            if 'repository not found' in error.lower() or 'does not appear' in error.lower():
                print(f"    {Colors.GRAY}└─ Repo may have been moved or deleted{Colors.END}")
            print(f"    Used in {len(uses)} files:")
            for cargo_path, dep_name, ref in uses[:3]:
                rel_path = str(cargo_path).replace(str(RUST_REPO_ROOT) + '/', '')
                print(f"      - {rel_path} ({dep_name})")
            if len(uses) > 3:
                print(f"      ... and {len(uses) - 3} more")
        print()
        print(f"{Colors.CYAN}💡 Fix: Update Cargo.toml files with correct git URLs (e.g., migrated to GitLab){Colors.END}")
        print()

    if timeouts:
        print(f"{Colors.ORANGE}⏱ Timed Out ({len(timeouts)}):{Colors.END}")
        for url in timeouts:
            uses = git_deps[url]
            print(f"  {url}")
            print(f"    Used in {len(uses)} file(s)")
        print()

    # Auto-fix HTTPS URLs to SSH if requested
    if fix_urls and (needs_auth or https_deps):
        print()
        print(f"{Colors.CYAN}{Colors.BOLD}🔧 Auto-fixing HTTPS URLs to SSH:{Colors.END}")
        print()

        fixed_count = 0
        for cargo_path in cargo_files:
            try:
                with open(cargo_path, 'r') as f:
                    content = f.read()

                modified = False
                new_content = content

                # Convert common HTTPS patterns to SSH
                replacements = [
                    ('https://github.com/', 'ssh://git@github.com/'),
                    ('https://gitlab.com/', 'ssh://git@gitlab.com/'),
                ]

                for old, new in replacements:
                    if old in new_content:
                        new_content = new_content.replace(old, new)
                        modified = True

                if modified:
                    rel_path = str(cargo_path).replace(str(RUST_REPO_ROOT) + '/', '')
                    if dry_run:
                        print(f"{Colors.YELLOW}Would update: {rel_path}{Colors.END}")
                    else:
                        with open(cargo_path, 'w') as f:
                            f.write(new_content)
                        print(f"{Colors.GREEN}✓ Updated: {rel_path}{Colors.END}")
                    fixed_count += 1

            except Exception as e:
                print(f"{Colors.RED}✗ Error processing {cargo_path}: {e}{Colors.END}")

        print()
        if dry_run:
            print(f"{Colors.YELLOW}Dry run: Would fix {fixed_count} files{Colors.END}")
        else:
            print(f"{Colors.GREEN}✅ Fixed {fixed_count} Cargo.toml files{Colors.END}")
            print(f"{Colors.CYAN}Run 'cargo check' to verify changes{Colors.END}")
        print()

    # Provide actionable summary
    print(f"{Colors.CYAN}{Colors.BOLD}🔧 Action Items:{Colors.END}")
    if not_found:
        print(f"1. Update {len(not_found)} broken git URL(s) in Cargo.toml files")
        print(f"   (Repos may have moved from GitHub to GitLab)")
    if needs_auth:
        print(f"2. Run 'blade scan-git fix-urls' to auto-convert HTTPS to SSH")
        print(f"3. Run 'blade fix-git' to enable SSH authentication for private repos")
    if not not_found and not needs_auth:
        print(f"{Colors.GREEN}✓ All git dependencies are accessible!{Colors.END}")

def fix_git_config(args):
    """Fix cargo config for private git dependencies"""
    import subprocess
    from pathlib import Path

    print(f"{Colors.CYAN}{Colors.BOLD}🔧 Git Dependency Configuration Fixer{Colors.END}")
    print()

    cargo_config_path = Path.home() / ".cargo" / "config.toml"
    cargo_config_dir = Path.home() / ".cargo"

    # Check current status
    has_git_fetch_cli = False
    if cargo_config_path.exists():
        try:
            config = load_toml(cargo_config_path)
            net_section = config.get('net', {})
            has_git_fetch_cli = net_section.get('git-fetch-with-cli') == True
        except:
            pass

    if has_git_fetch_cli:
        print(f"{Colors.GREEN}✓ Cargo is already configured for private git dependencies{Colors.END}")
        print(f"  git-fetch-with-cli = true is set in {cargo_config_path}")
    else:
        print(f"{Colors.YELLOW}⚠️  Cargo is not configured for private git dependencies{Colors.END}")
        print(f"  Missing: git-fetch-with-cli = true in [net] section")
        print()

        if args.dry_run:
            print(f"{Colors.CYAN}Would add to {cargo_config_path}:{Colors.END}")
            print(f"{Colors.WHITE}[net]{Colors.END}")
            print(f"{Colors.WHITE}git-fetch-with-cli = true{Colors.END}")
            print()
            print(f"{Colors.YELLOW}⚠️  Dry run mode - no changes made{Colors.END}")
            return

        # Fix it
        try:
            cargo_config_dir.mkdir(parents=True, exist_ok=True)

            # Read existing config
            existing_config = ""
            if cargo_config_path.exists():
                with open(cargo_config_path, 'r') as f:
                    existing_config = f.read()

            # Check if [net] section exists
            has_net_section = '[net]' in existing_config

            if not has_net_section:
                # Add entire [net] section
                with open(cargo_config_path, 'a') as f:
                    f.write("\n[net]\ngit-fetch-with-cli = true\n")
                print(f"{Colors.GREEN}✓ Added [net] section with git-fetch-with-cli = true{Colors.END}")
            else:
                # Add just the setting to existing [net] section
                lines = existing_config.split('\n')
                new_lines = []
                in_net_section = False
                added = False

                for line in lines:
                    new_lines.append(line)
                    if line.strip() == '[net]':
                        in_net_section = True
                    elif in_net_section and line.strip().startswith('['):
                        if not added:
                            new_lines.insert(-1, 'git-fetch-with-cli = true')
                            added = True
                        in_net_section = False

                if in_net_section and not added:
                    new_lines.append('git-fetch-with-cli = true')

                with open(cargo_config_path, 'w') as f:
                    f.write('\n'.join(new_lines))

                print(f"{Colors.GREEN}✓ Added git-fetch-with-cli = true to [net] section{Colors.END}")

            print(f"\n{Colors.GREEN}✅ Cargo config updated: {cargo_config_path}{Colors.END}")
            print(f"   Git dependencies will now use system git with SSH auth")

        except Exception as e:
            print(f"{Colors.RED}❌ Error fixing cargo config: {e}{Colors.END}")
            return

    # Check for SSH config
    print()
    print(f"{Colors.CYAN}📋 SSH Configuration:{Colors.END}")
    ssh_config_path = Path.home() / ".ssh" / "config"

    if ssh_config_path.exists():
        try:
            with open(ssh_config_path, 'r') as f:
                ssh_content = f.read()

            # Look for GitLab and GitHub entries
            has_gitlab = 'gitlab.com' in ssh_content.lower()
            has_github = 'github.com' in ssh_content.lower()

            if has_gitlab:
                print(f"{Colors.GREEN}✓ GitLab SSH profile found{Colors.END}")
            else:
                print(f"{Colors.YELLOW}⚠ No GitLab SSH profile in ~/.ssh/config{Colors.END}")

            if has_github:
                print(f"{Colors.GREEN}✓ GitHub SSH profile found{Colors.END}")
            else:
                print(f"{Colors.YELLOW}⚠ No GitHub SSH profile in ~/.ssh/config{Colors.END}")

        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Could not read SSH config: {e}{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  No SSH config found at ~/.ssh/config{Colors.END}")

    # Next steps
    print()
    print(f"{Colors.CYAN}{Colors.BOLD}📚 Next Steps:{Colors.END}")
    print(f"1. Ensure your SSH keys are added to ssh-agent:")
    print(f"   {Colors.WHITE}ssh-add ~/.ssh/your_private_key{Colors.END}")
    print(f"2. Test git access to private repos:")
    print(f"   {Colors.WHITE}git ls-remote ssh://git@gitlab.com/your-org/your-repo.git{Colors.END}")
    print(f"3. Update Cargo.toml dependencies to use SSH URLs:")
    print(f"   {Colors.WHITE}rsb = {{ git = \"ssh://git@gitlab.com/oodx/rsb.git\", branch = \"main\" }}{Colors.END}")
    print(f"4. Restart any running cargo processes")

def main():
    def signal_handler(signum, frame):
        """Global signal handler for graceful exit"""
        # Restore cursor visibility before exit
        sys.stdout.write('\033[?25h')
        # Try to restore terminal settings
        try:
            if sys.stdin.isatty():
                # Reset terminal to normal mode
                os.system('stty sane')
        except:
            pass
        sys.stdout.flush()
        print(f"\n{Colors.YELLOW}⚠️  Operation interrupted by user{Colors.END}")
        sys.exit(0)

    # Setup global signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination
    signal.signal(signal.SIGTSTP, signal_handler)  # Ctrl+Z

    parser = argparse.ArgumentParser(
        prog='blade',
        description='🗡️  BLADE - Advanced Dependency Management for Rust Ecosystems',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
COMMAND CATEGORIES:

  📊 Analysis Commands:
    conflicts         Show version conflicts across ecosystem (default)
    review            Detailed dependency review with latest versions
    hub               Hub-centric package status dashboard
    usage, u, q       Package usage analysis across ecosystem
    stats             Ecosystem statistics and metrics
    outdated          Show all outdated packages

  🔍 Query Commands:
    repos             List all repositories
    deps <repo>       Show dependencies for a specific repository
    pkg <package>     Package-specific analysis
    search <pattern>  Search for packages by pattern
    graph <package>   Show dependency graph for package

  🔧 Update Commands:
    update <repo>     Update specific repository dependencies
    eco               Update entire ecosystem
    learn <package>   Learn package (add to hub with latest version)

  🛠️  Maintenance Commands:
    data              Generate/refresh dependency cache
    export            Export raw analysis data to TSV
    superclean        Clean all target directories
    ls                List discovered repositories
    notes <repo>      View/manage repository notes

  🔐 Git Dependency Commands:
    scan-git          Scan and test git dependency accessibility
    fix-git           Configure cargo for SSH authentication

  ℹ️  Info Commands:
    --version         Show version information
    --help            Show this help message

FLAGS:
  --fast-mode         Disable progress bars for scripts
  --dry-run           Preview changes without applying
  --force-commit      Auto-commit with 'auto:hub bump' message
  --force             Bypass safety checks (use with caution)
  --live              Force live discovery (ignore cache)
  --create            Create hub metadata section (for notes)
  --ssh-profile       SSH profile for git operations

EXAMPLES:
  blade                          # Show conflicts (default)
  blade review --fast-mode       # Quick dependency review
  blade update myapp --dry-run   # Preview updates
  blade learn tokio              # Add tokio to hub
  blade scan-git fix-urls        # Fix HTTPS→SSH git URLs
        ''')

    parser.add_argument('--version', action=VersionAction, nargs=0)
    parser.add_argument('command', nargs='?', default='conflicts',
                       choices=['repos', 'conflicts', 'usage', 'u', 'q', 'review', 'hub', 'update', 'eco', 'pkg', 'export', 'data', 'superclean', 'ls', 'legacy',
                               'stats', 'deps', 'outdated', 'search', 'graph', 'learn', 'notes', 'fix-git', 'scan-git', 'latest'],
                       help='Command to run (see categories below)')
    parser.add_argument('package', nargs='?', help='Package/repo name for specific commands')
    parser.add_argument('--ssh-profile', default=None, help='SSH profile/host for git operations')
    parser.add_argument('--live', action='store_true', help='Force live discovery instead of cache')
    parser.add_argument('--fast-mode', action='store_true', help='Disable progress bars and interactive elements')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    parser.add_argument('--force-commit', action='store_true', help='Automatically commit changes')
    parser.add_argument('--force', action='store_true', help='Force operation (bypass safety checks)')
    parser.add_argument('--create', action='store_true', help='Create hub metadata section if missing')

    args = parser.parse_args()

    try:
        if args.command == 'latest':
            if not args.package:
                print(f"{Colors.RED}❌ Package name required for 'latest' command{Colors.END}")
                print(f"Usage: python deps.py latest <package_name>")
                sys.exit(1)
            check_latest(args.package)
            return

        # For other commands, we need to analyze dependencies first
        dependencies = analyze_dependencies()

        # Fast view commands (primary interface)
        if args.command in ['conflicts', 'usage', 'u', 'q', 'review', 'hub', 'update', 'eco', 'pkg', 'stats', 'deps', 'outdated', 'search', 'graph', 'learn', 'notes']:
            try:
                ecosystem = hydrate_tsv_cache()
                print(f"✅ Hydration successful: {len(ecosystem.deps)} deps, {len(ecosystem.repos)} repos")

                if args.command == 'repos':
                    view_repos(ecosystem)
                elif args.command == 'conflicts':
                    view_conflicts(ecosystem)
                elif args.command in ['usage', 'u', 'q']:
                    view_usage(ecosystem)
                elif args.command == 'review':
                    view_review(ecosystem)
                elif args.command == 'hub':
                    view_hub_dashboard(ecosystem)
                elif args.command == 'update':
                    if args.package:
                        update_repo_dependencies(ecosystem, args.package, dry_run=args.dry_run, force_commit=args.force_commit, force=args.force)
                    else:
                        print(f"{Colors.RED}❌ Repository name required for update command{Colors.END}")
                        print(f"Usage: repos.py update <repo-name> [--dry-run] [--force-commit] [--force]")
                        return
                elif args.command == 'eco':
                    update_ecosystem(ecosystem, dry_run=args.dry_run, force_commit=args.force_commit, force=args.force)
                elif args.command == 'pkg':
                    if args.package:
                        view_package_detail(ecosystem, args.package)
                    else:
                        print(f"{Colors.RED}❌ Package name required for pkg command{Colors.END}")
                        print(f"Usage: repos.py pkg <package-name>")
                        return
                elif args.command == 'stats':
                    view_stats(ecosystem)
                elif args.command == 'deps':
                    if args.package:
                        view_repo_deps(ecosystem, args.package)
                    else:
                        print(f"{Colors.RED}❌ Repository name required for deps command{Colors.END}")
                        print(f"Usage: repos.py deps <repo-name>")
                        return
                elif args.command == 'outdated':
                    view_outdated(ecosystem)
                elif args.command == 'search':
                    if args.package:
                        view_search(ecosystem, args.package)
                    else:
                        print(f"{Colors.RED}❌ Search pattern required for search command{Colors.END}")
                        print(f"Usage: repos.py search <pattern>")
                        return
                elif args.command == 'graph':
                    if args.package:
                        view_graph(ecosystem, args.package)
                    else:
                        print(f"{Colors.RED}❌ Package name required for graph command{Colors.END}")
                        print(f"Usage: repos.py graph <package-name>")
                        return
                elif args.command == 'learn':
                    if args.package:
                        if args.package.lower() == 'all':
                            learn_all_opportunities(ecosystem)
                        else:
                            learn_package(ecosystem, args.package)
                    else:
                        print(f"{Colors.RED}❌ Package name or 'all' required for learn command{Colors.END}")
                        print(f"Usage: repos.py learn <package-name>  # Learn a specific package")
                        print(f"       repos.py learn all              # Learn all opportunities")
                        return
                elif args.command == 'notes':
                    if args.package:
                        view_repo_notes(ecosystem, args.package, create_if_missing=args.create)
                    else:
                        print(f"{Colors.RED}❌ Repository name required for notes command{Colors.END}")
                        print(f"Usage: repos.py notes <repo-name>           # View hub metadata/notes")
                        print(f"       repos.py notes <repo-name> --create  # Create metadata section if missing")
                        return
            except Exception as e:
                print(f"❌ Error in {args.command} command: {e}")
                import traceback
                traceback.print_exc()
                return

        # Utility commands
        elif args.command == 'data':
            generate_data_cache(dependencies, args.fast_mode)
        elif args.command == 'export':
            export_raw_data(dependencies)
        elif args.command == 'superclean':
            superclean_targets()
        elif args.command == 'ls':
            list_repositories(force_live=args.live)
        elif args.command == 'legacy':
            # Legacy analyze command for backwards compatibility
            analyze_package_usage(dependencies)
        elif args.command == 'fix-git':
            fix_git_config(args)
        elif args.command == 'scan-git':
            scan_git_dependencies(args)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Operation interrupted by user{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
        sys.exit(1)

if __name__ == "__main__":
    main()
