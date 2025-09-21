# Fast View Commands - User Acceptance Testing (UAT)

## 🎯 UAT Test Suite for Fast View Implementation

### Prerequisites
```bash
cd /home/xnull/repos/code/rust/oodx/projects/hub
python3 --version  # Ensure Python 3.11+ or external toml package available
```

### 1. Environment Setup & Cache Generation
```bash
# Generate fresh TSV cache
python3 ./bin/repos.py data

# Verify cache file exists and has correct structure
ls -la deps_cache.tsv
head -20 deps_cache.tsv
```

### 2. Fast Conflicts Analysis
```bash
# Test fast conflicts command
echo "=== UAT: Fast Conflicts Analysis ==="
time python3 ./bin/repos.py fast --conflicts

# Expected:
# - Sub-second execution time
# - List of packages with version conflicts
# - Color-coded output with repository names
# - Latest version information displayed
```

### 3. Fast Package Detail Analysis
```bash
# Test package detail for high-usage package
echo "=== UAT: Fast Package Detail (serde) ==="
time python3 ./bin/repos.py fast --pkg-detail serde

# Test package detail for conflicted package
echo "=== UAT: Fast Package Detail (regex) ==="
time python3 ./bin/repos.py fast --pkg-detail regex

# Test package detail for non-existent package
echo "=== UAT: Fast Package Detail (nonexistent) ==="
python3 ./bin/repos.py fast --pkg-detail nonexistent_package

# Expected:
# - Sub-second execution for existing packages
# - Package overview with latest version, hub status, usage count
# - Repository usage breakdown by version and type
# - Proper error message for non-existent packages
```

### 4. Fast Hub Dashboard
```bash
# Test comprehensive hub dashboard
echo "=== UAT: Fast Hub Dashboard ==="
time python3 ./bin/repos.py fast --hub-dashboard

# Expected:
# - Sub-second execution time
# - Hub overview with total packages and coverage statistics
# - Status breakdown (current/outdated/gap packages)
# - Complete package listing with hub status and usage metrics
```

### 5. Performance Comparison Tests
```bash
# Compare legacy vs fast commands
echo "=== UAT: Performance Comparison ==="

echo "Legacy package analysis (serde):"
time python3 ./bin/repos.py pkg serde

echo "Fast package analysis (serde):"
time python3 ./bin/repos.py fast --pkg-detail serde

echo "Legacy hub status:"
time python3 ./bin/repos.py hub

echo "Fast hub dashboard:"
time python3 ./bin/repos.py fast --hub-dashboard

# Expected:
# - Fast commands should be significantly faster for package detail
# - Results should be consistent between legacy and fast versions
# - Fast commands should complete in under 1 second
```

### 6. Error Handling & Edge Cases
```bash
# Test with corrupted cache (backup first)
echo "=== UAT: Error Handling ==="
cp deps_cache.tsv deps_cache.tsv.backup

# Test with missing cache
rm deps_cache.tsv
python3 ./bin/repos.py fast --conflicts
# Expected: Error message about missing cache

# Restore cache
mv deps_cache.tsv.backup deps_cache.tsv

# Test invalid arguments
python3 ./bin/repos.py fast --invalid-flag
python3 ./bin/repos.py fast
# Expected: Proper help/error messages
```

### 7. Data Integrity Validation
```bash
# Verify TSV cache data integrity
echo "=== UAT: Data Integrity ==="

# Check repo count consistency
echo "Repo count in aggregation vs actual repos:"
grep "total_repos" deps_cache.tsv
grep -c "^[0-9]\+\s" deps_cache.tsv | head -1

# Check dependency count consistency
echo "Dependency count in aggregation vs actual deps:"
grep "total_deps" deps_cache.tsv
grep -c "^[0-9]\+\s.*\sdep\s" deps_cache.tsv

# Verify no orphaned dependencies (should return 0)
echo "Checking for orphaned dependencies (should be 0):"
python3 -c "
import sys
sys.path.append('bin')
from repos import hydrate_tsv_cache
eco = hydrate_tsv_cache()
orphans = [dep for dep in eco.deps.values() if dep.repo_id not in eco.repos]
print(f'Orphaned dependencies: {len(orphans)}')
if orphans: print('ERROR: Found orphaned dependencies!')
"
```

### 8. TOML Compatibility Tests
```bash
# Test TOML import compatibility
echo "=== UAT: TOML Import Compatibility ==="

# Test with Python 3.11+ (if available)
python3 -c "
import sys
print(f'Python version: {sys.version}')
try:
    import tomllib
    print('✅ tomllib available (Python 3.11+)')
except ImportError:
    print('⚠️  tomllib not available, should use external toml')
    try:
        import toml
        print('✅ External toml package available')
    except ImportError:
        print('❌ No TOML library available - will fail')
"

# Test load_toml function directly
python3 -c "
import sys
sys.path.append('bin')
from repos import load_toml
test_toml = 'test_key = \"test_value\"'
result = load_toml(test_toml, is_string=True)
print(f'TOML parsing test: {result}')
"
```

### 9. Complete Integration Test
```bash
# Full workflow test
echo "=== UAT: Complete Integration Test ==="

# 1. Generate cache
python3 ./bin/repos.py data

# 2. Run all fast commands
python3 ./bin/repos.py fast --conflicts
python3 ./bin/repos.py fast --pkg-detail serde
python3 ./bin/repos.py fast --hub-dashboard

# 3. Verify consistency with legacy commands
echo "Checking serde usage count consistency..."
legacy_count=$(python3 ./bin/repos.py pkg serde | grep -o "Total usage count: [0-9]\+" | grep -o "[0-9]\+")
fast_count=$(python3 ./bin/repos.py fast --pkg-detail serde | grep -o "Used in: [0-9]\+" | grep -o "[0-9]\+")
echo "Legacy count: $legacy_count, Fast count: $fast_count"
if [ "$legacy_count" = "$fast_count" ]; then
    echo "✅ Usage counts match"
else
    echo "❌ Usage counts don't match!"
fi
```

## 📋 UAT Success Criteria

### ✅ All tests must pass:
1. **Performance**: Fast commands complete in under 1 second
2. **Accuracy**: Results consistent with legacy commands
3. **Error Handling**: Graceful handling of edge cases
4. **Data Integrity**: No orphaned dependencies or inconsistent counts
5. **TOML Compatibility**: Works with both tomllib and external toml
6. **Cache System**: TSV generation and hydration working correctly

### 🎯 Expected Improvements:
- **Package Detail**: 2-3x faster than legacy version
- **Hub Dashboard**: Instant response vs multiple API calls
- **Conflicts**: Instant analysis vs filesystem scanning

## 🚨 Failure Indicators:
- Commands taking longer than 2 seconds
- Inconsistent data between fast and legacy commands
- KeyError or other exceptions during execution
- Missing or corrupted cache files
- Incorrect package counts or statistics

Run all commands and verify success criteria are met before deployment.