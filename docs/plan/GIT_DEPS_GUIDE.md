# Private Git Dependencies Guide

## Problem

When blade.py encounters git dependencies that require authentication (private GitLab/GitHub repos), it shows version as `0.0.0` or `AUTH_REQUIRED` because:
1. Cargo's built-in git doesn't use SSH authentication
2. Missing `git-fetch-with-cli = true` in cargo config
3. SSH config may not be properly set up

## Solution

### Quick Fix

```bash
# Check and fix cargo config
blade fix-git

# Or dry-run to see what would change
blade fix-git --dry-run
```

### What `blade fix-git` Does

1. **Checks cargo config** (`~/.cargo/config.toml`)
   - Verifies `git-fetch-with-cli = true` is set in `[net]` section
   - If missing, adds it **without clobbering** existing config

2. **Validates SSH config** (`~/.ssh/config`)
   - Checks for GitLab and GitHub host entries
   - Reports if SSH profiles are configured

3. **Provides next steps**
   - SSH key setup instructions
   - How to test git access
   - Cargo.toml format for SSH URLs

### Enhanced Version Resolution

blade.py now detects different git access states:

| Version Shown | Meaning | Action Needed |
|---------------|---------|---------------|
| `1.2.3` | Successfully retrieved version | None |
| `GIT#abc1234` | Accessible but no Cargo.toml found | Check repo structure |
| `AUTH_REQUIRED` | Authentication failure | Run `blade fix-git`, add SSH keys |
| `NOT_FOUND` | Repository doesn't exist | Check URL |
| `TIMEOUT` | Git operation timed out | Check network |
| `0.0.0` | Unknown/fallback | Check configuration |

## Complete Setup for Private GitLab Repos

### 1. Cargo Configuration

Add to `~/.cargo/config.toml`:
```toml
[net]
git-fetch-with-cli = true
```

**Or run:** `blade fix-git`

### 2. SSH Configuration

Add to `~/.ssh/config`:
```
Host qode2 gitlab gitlab.com
  HostName gitlab.com
  IdentityFile ~/.ssh/id_gh08_ed255
  User git
```

### 3. SSH Key Setup

```bash
# Add your SSH key to ssh-agent
ssh-add ~/.ssh/id_gh08_ed255

# Test access
ssh -T git@gitlab.com
```

### 4. Cargo.toml Format

Use SSH URLs for private dependencies:
```toml
[dependencies]
rsb = { git = "ssh://git@gitlab.com/oodx/rsb.git", branch = "main" }
hub = { git = "ssh://git@gitlab.com/oodx/hub.git", branch = "main" }
```

**Important:** Use `ssh://git@...` format, not `git@...` format

### 5. Verify Setup

```bash
# Test git access directly
git ls-remote ssh://git@gitlab.com/oodx/rsb.git

# Run blade to check version resolution
blade review  # Should now show real versions instead of 0.0.0
```

## Troubleshooting

### Still seeing AUTH_REQUIRED?

1. **Check cargo config:**
   ```bash
   cat ~/.cargo/config.toml | grep git-fetch-with-cli
   ```
   Should show: `git-fetch-with-cli = true`

2. **Test SSH access:**
   ```bash
   ssh -T git@gitlab.com
   ```
   Should show welcome message

3. **Verify SSH key is loaded:**
   ```bash
   ssh-add -l
   ```
   Should list your key

4. **Check Cargo.toml URL format:**
   - ✅ Good: `ssh://git@gitlab.com/org/repo.git`
   - ❌ Bad: `git@gitlab.com:org/repo.git` (won't work with cargo)
   - ❌ Bad: `https://gitlab.com/org/repo.git` (requires token)

### Cargo Not Using System Git?

Restart any running cargo processes:
```bash
# Kill all cargo processes
pkill -9 cargo

# Run cargo again
cargo check
```

### SSH Agent Not Running?

```bash
# Start ssh-agent
eval "$(ssh-agent -s)"

# Add your key
ssh-add ~/.ssh/your_key
```

## Files Involved

1. **`~/.cargo/config.toml`** - Tells cargo to use system git
2. **`~/.ssh/config`** - SSH host profiles and keys
3. **`~/.ssh/id_*`** - Your SSH private keys
4. **`Cargo.toml`** - Dependency definitions with git URLs

## Advanced: Multiple SSH Keys

If you have different keys for different services:

```
Host github github.com
  HostName github.com
  IdentityFile ~/.ssh/id_github
  User git

Host gitlab gitlab.com
  HostName gitlab.com
  IdentityFile ~/.ssh/id_gitlab
  User git

Host qode2
  HostName gitlab.com
  IdentityFile ~/.ssh/id_qode2
  User git
```

Then use appropriate host in git URLs:
```toml
# Uses id_qode2 key
dep1 = { git = "ssh://git@qode2/org/repo.git", branch = "main" }

# Uses id_gitlab key
dep2 = { git = "ssh://git@gitlab/org/repo.git", branch = "main" }
```
