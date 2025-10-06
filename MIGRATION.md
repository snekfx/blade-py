# Blade Hub Path Migration Guide

## What Changed

The hub repository has been relocated from:
- **Old location**: `rust/oodx/projects/hub`
- **New location**: `rust/prods/oodx/hub`

Blade tools (blade.py and blade-repo.py) have been updated to handle this change through configurable paths.

## Quick Start

### Option 1: Auto-Configuration (Recommended)

```bash
# Navigate to blade-py directory
cd /path/to/blade-py

# Source the configuration script
source ./blade-config.sh
```

The script will:
- Auto-detect your RUST_REPO_ROOT
- Auto-detect HUB_PATH from common locations (prioritizing the new location)
- Export environment variables for your current session
- Show you commands to make the configuration permanent

### Option 2: Manual Configuration

```bash
# Set environment variables
export RUST_REPO_ROOT="/home/user/repos/code/rust"
export HUB_PATH="/home/user/repos/code/rust/prods/oodx/hub"
```

## Making Configuration Permanent

Add the following to your `~/.bashrc` or `~/.zshrc`:

```bash
export RUST_REPO_ROOT="/home/user/repos/code/rust"
export HUB_PATH="/home/user/repos/code/rust/prods/oodx/hub"
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

## How Auto-Detection Works

### RUST_REPO_ROOT Detection
1. Checks `RUST_REPO_ROOT` environment variable
2. Walks up directory tree looking for a `rust` directory
3. Falls back to common locations:
   - `~/repos/code/rust`
   - `/home/xnull/repos/code/rust`

### HUB_PATH Detection
1. Checks `HUB_PATH` environment variable
2. Searches for hub in priority order:
   - `{RUST_REPO_ROOT}/prods/oodx/hub` (new standard)
   - `{RUST_REPO_ROOT}/oodx/projects/hub` (legacy)
   - `{RUST_REPO_ROOT}/oodx/hub`
   - `{RUST_REPO_ROOT}/hub`
3. Validates by checking for `Cargo.toml`

## Verifying Configuration

### Check Current Configuration
```bash
echo "RUST_REPO_ROOT: $RUST_REPO_ROOT"
echo "HUB_PATH: $HUB_PATH"
```

### Test Blade Tools
```bash
# Test blade.py can find hub
python blade.py --help

# Verify hub detection (should show version and dependency count)
python -c "
import blade
hub_info = blade.get_hub_info()
if hub_info:
    print(f'Hub found: v{hub_info.version} with {len(hub_info.dependencies)} deps')
else:
    print('Hub not found!')
"
```

### Test blade-repo.py
```bash
# Should work without hub-specific configuration
python blade-repo.py --help
python blade-repo.py --stats
```

## Troubleshooting

### Hub Not Found

If blade.py can't find the hub:

1. **Check HUB_PATH is set:**
   ```bash
   echo $HUB_PATH
   ```

2. **Verify hub location:**
   ```bash
   ls -la $HUB_PATH/Cargo.toml
   ```

3. **Manually set the path:**
   ```bash
   export HUB_PATH="/full/path/to/hub"
   ```

### RUST_REPO_ROOT Not Detected

If RUST_REPO_ROOT isn't auto-detected:

1. **Find your rust directory:**
   ```bash
   find ~ -type d -name rust 2>/dev/null | grep repos
   ```

2. **Set it manually:**
   ```bash
   export RUST_REPO_ROOT="/path/to/rust"
   ```

### Path Still Using Old Location

If blade is still trying to use the old location:

1. **Check for cached environment variables:**
   ```bash
   env | grep -E "(RUST_REPO_ROOT|HUB_PATH)"
   ```

2. **Unset and re-source:**
   ```bash
   unset RUST_REPO_ROOT HUB_PATH
   source ./blade-config.sh
   ```

3. **Check for conflicts in shell config files:**
   ```bash
   grep -r "HUB_PATH" ~/.bashrc ~/.zshrc ~/.profile 2>/dev/null
   ```

## For Future Relocations

If the hub needs to be moved again in the future:

1. **Update environment variable:**
   ```bash
   export HUB_PATH="/new/path/to/hub"
   ```

2. **Or update blade-config.sh** to add new search location:
   - Edit `blade-config.sh`
   - Add new path to `hub_search_paths` array (at the top for priority)

3. **Update blade.py** search paths (optional):
   - Edit the `HUB_PATH` auto-detection section (around line 220)
   - Add new path to `hub_search_paths` list

## Architecture Notes

The blade tools now use a flexible configuration system:

- **Environment Variables** (highest priority):
  - `RUST_REPO_ROOT` - Root directory containing Rust projects
  - `HUB_PATH` - Direct path to hub repository

- **Auto-Detection** (fallback):
  - Searches common locations in priority order
  - Validates paths by checking for expected files

- **Backwards Compatibility**:
  - Old hub location is still in search path
  - Will work with either new or old structure
  - No breaking changes to existing workflows

This ensures blade tools will continue to work even if the hub location changes in the future, as long as the environment variables are updated or the new location is added to the search paths.
