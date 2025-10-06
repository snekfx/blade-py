# Blade Deployment Guide

## Quick Deployment

### Step 1: Configure Environment
```bash
cd /path/to/blade-py
source ./bin/blade-config.sh
```

This will auto-detect your RUST_REPO_ROOT and HUB_PATH.

### Step 2: Deploy Blade
```bash
./bin/deploy.sh
```

This installs blade to `~/.local/bin/snek/blade`.

### Step 3: Make Configuration Permanent
Add the exports shown by blade-config.sh to your `~/.bashrc` or `~/.zshrc`:

```bash
export RUST_REPO_ROOT="/home/user/repos/code/rust"
export HUB_PATH="/home/user/repos/code/rust/prods/oodx/hub"
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

## Verification

### Test Configuration
```bash
# Check variables are set
echo $RUST_REPO_ROOT
echo $HUB_PATH

# Test blade-config.sh
source ./bin/blade-config.sh
```

### Test Blade Installation
```bash
# Check blade is in PATH
which blade

# Test blade commands
blade --help
blade repos
blade hub
```

## What Gets Deployed

### Files Deployed
- `~/.local/bin/snek/blade` - Main blade executable

### Configuration Scripts
- `bin/blade-config.sh` - Auto-configuration helper
- Can be sourced from anywhere

### Environment Variables Required
- `RUST_REPO_ROOT` - Path to your Rust repositories root
- `HUB_PATH` - Path to your hub repository

## Common Issues

### "blade: command not found"
**Solution**: Ensure `~/.local/bin/snek` is in your PATH:
```bash
echo 'export PATH="$HOME/.local/bin/snek:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "Hub not found"
**Solution**: Run blade-config.sh or manually set HUB_PATH:
```bash
source ./bin/blade-config.sh
# OR
export HUB_PATH="/path/to/your/hub"
```

### Auto-detection fails
**Solution**: Manually set environment variables:
```bash
export RUST_REPO_ROOT="/full/path/to/rust"
export HUB_PATH="/full/path/to/hub"
```

## Deployment Details

### What deploy.sh Does
1. Creates `~/.local/bin/snek/` directory
2. Copies `blade.py` to `~/.local/bin/snek/blade`
3. Makes it executable
4. Tests that blade is in PATH
5. Shows deployment ceremony with version info

### Version Detection
The deploy script extracts version from `blade.py`:
- Looks for `__version__ = "X.Y.Z"` in blade.py
- Falls back to "2.0.0-dev" if not found

### Current Version
- **Blade v2.0.0** - With configurable hub path support

## Upgrading

To upgrade blade after pulling new changes:

```bash
cd /path/to/blade-py
git pull
source ./bin/blade-config.sh  # If needed
./bin/deploy.sh
```

## Uninstalling

To remove blade:

```bash
rm ~/.local/bin/snek/blade
```

To also remove configuration:
```bash
# Remove from ~/.bashrc or ~/.zshrc
# Delete lines containing RUST_REPO_ROOT and HUB_PATH exports
```

## Development Mode

To use blade directly without deploying:

```bash
cd /path/to/blade-py
source ./bin/blade-config.sh
python blade.py --help
```

Or create an alias:
```bash
alias blade-dev='cd /path/to/blade-py && python blade.py'
```
