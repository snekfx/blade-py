# blade data vs blade scan-git

## Quick Answer

**No, `blade scan-git` does NOT use data from `blade data`**

They are independent commands that work differently:

| Command | What It Does | Data Source | Speed | Purpose |
|---------|--------------|-------------|-------|---------|
| `blade data` | Analyzes ALL dependencies | Resolves git versions during scan | Slow (hangs on broken HTTPS) | Cache dependency data for other commands |
| `blade scan-git` | Tests git URLs only | Direct git ls-remote tests | Fast (3s timeout per URL) | Find broken git dependencies |

## Detailed Comparison

### blade data

**What it does:**
1. Scans all Cargo.toml files
2. Extracts ALL dependencies (crates.io + git + local + workspace)
3. **Calls `resolve_git_version()` for each git dependency**
4. Fetches latest versions from crates.io
5. Saves to `deps_cache.tsv`

**Git dependency handling:**
- Tries GitHub API (for public GitHub repos)
- Tries `git archive --remote` (SSH/HTTPS)
- **Will hang on HTTPS URLs that need credentials**
- Returns: version string, "AUTH_REQUIRED", "NOT_FOUND", "0.0.0"

**Used by:**
- `blade review`
- `blade conflicts`
- `blade hub`
- Other analysis commands

**Problem with broken HTTPS URLs:**
```
blade data  # Hangs trying to access https://github.com/oodx/rsb.git
            # Waits for username/password that never comes
```

---

### blade scan-git

**What it does:**
1. Scans all Cargo.toml files
2. Extracts ONLY git dependencies
3. **Tests each unique git URL with `git ls-remote --heads`**
4. Reports accessibility status
5. Optionally fixes HTTPS → SSH

**Git dependency testing:**
- Uses `git ls-remote` (fast, 3s timeout)
- Sets `GIT_TERMINAL_PROMPT=0` (no prompts)
- Uses `stdin=DEVNULL` (blocks input)
- **Never hangs** - fails fast

**Used for:**
- Diagnosing git dependency issues
- Finding repos that need SSH setup
- Auto-converting HTTPS → SSH URLs

**Handles broken HTTPS URLs:**
```
blade scan-git  # Tests https://github.com/oodx/rsb.git
                # Detects AUTH_REQUIRED in ~3 seconds
                # Moves to next URL
                # Reports which files need fixing
```

## Why They're Different

### Data Flow

**blade data:**
```
Cargo.toml → parse deps → resolve git version → try GitHub API
                                               → try git archive
                                               → HANGS on HTTPS prompt
                                               → eventually times out (10s)
                                               → cache to TSV
```

**blade scan-git:**
```
Cargo.toml → parse git deps only → test git ls-remote (3s timeout)
                                  → report status
                                  → never caches
                                  → optionally fix URLs
```

### Performance

**blade data:**
- Processes ALL dependency types
- Fetches from crates.io API
- Resolves git versions (slow)
- **Time:** ~30-60 seconds for 20 repos

**blade scan-git:**
- Only tests git URLs
- Direct git command
- Fast timeout (3s per URL)
- **Time:** ~5-10 seconds for 8 unique git URLs

## When to Use Which

### Use `blade scan-git` when:
- ✅ You want to find broken git dependencies
- ✅ You need to convert HTTPS → SSH
- ✅ You want fast diagnostics
- ✅ `blade data` is hanging

### Use `blade data` when:
- ✅ You need to cache dependency info for analysis
- ✅ You want to analyze crates.io dependencies
- ✅ You're running `blade review`, `blade hub`, etc.
- ✅ All git dependencies are already working (SSH)

## Solving the Hanging Issue

**Before (blade data hangs):**
```bash
blade data
# Hangs... waiting for credentials...
# Ctrl+C to cancel
```

**Solution:**
```bash
# 1. Find broken git deps (fast, doesn't hang)
blade scan-git

# 2. Fix them
blade scan-git fix-urls

# 3. Configure cargo
blade fix-git

# 4. Now blade data won't hang
blade data
```

## Can They Work Together?

**Not directly**, but they complement each other:

1. **blade scan-git** → Fixes git dependency URLs
2. **blade data** → Now works without hanging
3. **blade review** → Uses cached data from `blade data`

## Summary

- **`blade scan-git`** = Standalone git URL tester (fast, independent)
- **`blade data`** = Full dependency cache builder (slow, comprehensive)
- **Fix git issues with scan-git BEFORE running blade data**
- **They don't share data** - scan-git always scans fresh
