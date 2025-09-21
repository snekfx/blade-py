# Boxy Integration for Hub Repository Tools

## Overview
This document describes the integration of Boxy (the box drawing utility) with Hub's repository management tools (`repos.py`) to provide enhanced visual output for all view commands.

## Integration Approach

### 1. Environment Variable Control
- **Variable**: `REPOS_USE_BOXY=true`
- **Default**: Disabled (for backward compatibility)
- **Purpose**: Allows users to opt-in to enhanced visual output

### 2. Helper Function
A simple subprocess wrapper `render_with_boxy()` has been added to repos.py that:
- Checks if Boxy is available via `shutil.which("boxy")`
- Falls back gracefully to plain text if unavailable
- Handles errors silently, returning original content

### 3. Theme Mapping
Different command outputs use semantic themes:

| Command | Theme | Use Case |
|---------|-------|----------|
| `stats` | info | General statistics and metrics |
| `conflicts` | warning | Version conflicts requiring attention |
| `outdated` | warning | Packages with available updates |
| `deps` | info | Repository dependency listings |
| `search` | info | Search results |
| `graph` | info | Dependency relationships |
| Errors | error | Critical issues and failures |
| Success | success | Successful operations |

## Implementation Status

### ✅ Completed
- Added `render_with_boxy()` helper function
- Created `test_boxy.py` demonstration script
- Tested all theme variations
- Documented integration approach

### 🔄 Ready for Integration
The following view commands can be enhanced with Boxy:
1. `view_stats()` - Wrap statistics in info theme
2. `view_conflicts()` - Use warning theme for conflicts
3. `view_outdated()` - Warning for breaking, success for minor updates
4. `view_repo_deps()` - Info theme for dependency lists
5. `view_search()` - Info theme with result highlighting
6. `view_graph()` - Info theme for relationship visualization
7. `view_query()` - Info theme for usage analysis
8. `view_hub_dashboard()` - Success/warning based on status

## Usage Examples

### Basic Integration Pattern
```python
def view_command(ecosystem):
    if USE_BOXY:
        # Collect output in a buffer
        output = []
        output.append("Line 1")
        output.append("Line 2")

        # Render with boxy
        boxed = render_with_boxy(
            "\n".join(output),
            title="📊 Command Title",
            theme="info",
            header="Hub Analysis"
        )
        print(boxed)
    else:
        # Original output
        print("Line 1")
        print("Line 2")
```

### Testing
```bash
# Test without Boxy (default)
./bin/repos.py stats

# Test with Boxy enabled
export REPOS_USE_BOXY=true
./bin/repos.py stats

# Run demo script
./bin/test_boxy.py
```

## Benefits

1. **Enhanced Readability**: Clear visual separation of command outputs
2. **Semantic Theming**: Visual cues for different information types
3. **Professional Appearance**: Consistent, polished output formatting
4. **Backward Compatible**: Falls back gracefully when disabled or unavailable
5. **Zero Dependencies**: Uses subprocess shim, no Python packages required

## Performance Considerations

- **Overhead**: ~10-20ms per render (process spawn + formatting)
- **Suitable for**: Interactive CLI usage, report generation
- **Not recommended for**: High-volume batch processing, piped output

## Future Enhancements

1. **Streaming Support**: For large outputs (e.g., `review` command)
2. **Custom Themes**: User-defined theme configurations
3. **Width Detection**: Auto-detect terminal width for responsive layouts
4. **Native Integration**: Direct PyO3 bindings for better performance
5. **Progress Boxes**: Integration with ProgressSpinner for operations

## Configuration

### Global Settings
```bash
# Enable Boxy globally
echo 'export REPOS_USE_BOXY=true' >> ~/.bashrc

# Disable for specific command
REPOS_USE_BOXY=false ./bin/repos.py stats
```

### Per-Command Control
Future enhancement could add command-line flags:
```bash
./bin/repos.py stats --boxy        # Force enable
./bin/repos.py stats --no-boxy     # Force disable
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Boxy not found | Install via `cargo install boxy` or use binary from releases |
| Garbled output | Check terminal UTF-8 support |
| Performance slow | Disable for batch operations |
| Colors not showing | Check terminal color support and TERM variable |

## Summary

The Boxy integration provides a clean, optional enhancement layer for Hub's repository management tools. The subprocess shim approach ensures:
- Zero maintenance overhead
- No additional dependencies
- Graceful degradation
- Future-proof architecture

The integration is ready for gradual adoption across all view commands while maintaining full backward compatibility.