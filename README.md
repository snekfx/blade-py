# BLADE 🗡️
*Advanced Dependency Management and Repository Analysis Tool*

## Overview

BLADE is a powerful dependency management and repository analysis tool designed for modern software ecosystems. Currently focused on Rust/Cargo repositories with plans for multi-language support (Bash, Python, JavaScript), BLADE provides comprehensive ecosystem analysis, dependency conflict detection, and automated update management.

Built from the ground up to handle complex repository ecosystems, BLADE excels at providing lightning-fast analysis through intelligent caching, offering both detailed dependency insights and ecosystem-wide operations with safety guarantees.

### Key Highlights
- 🚀 **Lightning-fast analysis** via TSV caching system
- 🔍 **Deep dependency insights** with conflict detection
- 🔄 **Automated ecosystem updates** with safety checks
- 📊 **Rich visualization** and reporting
- 🎯 **Learning system** for dependency optimization
- 📝 **Repository notes** and metadata management
- 🛡️ **Git safety checks** and force operations

## Current Focus: Rust Ecosystem

BLADE is currently optimized for Rust/Cargo repositories and tightly integrated with the "hub" ecosystem pattern - a centralized repository that manages shared dependencies across multiple related projects.

**Hub Integration Features:**
- Hub-centric dependency analysis
- Automated hub synchronization
- Gap analysis (packages used widely but not in hub)
- Opportunity detection for consolidation

## Installation & Setup

### Prerequisites
- Python 3.8+
- Git
- Rust/Cargo (for Rust ecosystem analysis)
- Optional: `boxy` tool for enhanced formatting

### Configuration

BLADE needs to know where your Rust repos and hub are located. Two options:

**Option 1: Use blade-config.sh (auto-detect)**
```bash
source ./blade-config.sh
```
Auto-detects paths and exports `RUST_REPO_ROOT` and `HUB_HOME` for current session.

**Option 2: Set manually in ~/.bashrc or ~/.zshrc**
```bash
export RUST_REPO_ROOT="$HOME/repos/code/rust"
export HUB_HOME="$RUST_REPO_ROOT/prods/oodx/hub"  # Or use HUB_PATH
```

**Supported variables:** `HUB_HOME` (recommended) or `HUB_PATH` (legacy). Auto-detection searches: `rust/prods/oodx/hub`, `rust/oodx/projects/hub`, `rust/oodx/hub`, `rust/hub`.

### Installation

```bash
# 1. Configure environment
source ./blade-config.sh  # Or add exports to ~/.bashrc

# 2. Deploy to system
./bin/deploy.sh  # Installs to ~/.local/bin/snek/blade

# 3. Use blade
blade --help
```

**Development mode (no install):**
```bash
source ./blade-config.sh
python blade.py --help
```

### XDG Directory Structure
BLADE follows XDG Base Directory specifications with snekfx structure:
- **Data**: `~/.local/share/snek/blade/` (for deps_cache.tsv and exported data)
- **Config**: `~/.config/snek/blade/` (for future configuration files)
- **Cache**: `~/.cache/snek/blade/` (for future cache files)

Note: The system also respects `XDG_DB_HOME` as a preferred data directory over `XDG_DATA_HOME`.

**Important**: This is a migration from previous hub-specific paths to the new standardized snekfx XDG structure.

### Hub Ecosystem Setup
For hub-integrated workflows:
1. Ensure your repositories follow hub dependency patterns
2. Configure SSH profiles for multi-host Git operations
3. XDG data directories are automatically created when blade runs
4. Ensure `~/.local/bin/odx/hub/` is in your PATH for system-wide blade access

## Core Commands

### Analysis Commands
```bash
# Default conflict analysis view
blade

# Repository listing and overview
blade repos

# Package usage analysis across ecosystem
blade usage              # or: blade u, blade q

# Detailed review with latest versions
blade review

# Hub-centric dashboard
blade hub

# Repository-specific dependency view
blade deps <repo-name>

# Package-specific analysis
blade pkg <package-name>
```

### Search & Discovery
```bash
# Search packages by pattern
blade search <pattern>

# View dependency graph for package
blade graph <package-name>

# Ecosystem statistics
blade stats

# Show outdated packages
blade outdated
```

### Update Operations
```bash
# Update specific repository
blade update <repo-name> [--dry-run] [--force-commit] [--force]

# Ecosystem-wide updates
blade eco [--dry-run] [--force-commit] [--force]

# Check latest version from crates.io
blade latest <package-name>
```

### Learning System
```bash
# Learn a package (add to hub with latest version)
blade learn <package-name>

# Learn all opportunity packages
blade learn all

# View/manage repository notes
blade notes <repo-name> [--create]
```

### Data Management
```bash
# Export raw analysis data to XDG data directory
blade export

# List discovered repositories
blade ls [--live]

# Generate/refresh data cache
blade data [--fast-mode]

# Clean build artifacts
blade superclean
```

### Private Git Dependencies
```bash
# Fix cargo config for private git repos (GitLab, GitHub, etc.)
blade fix-git [--dry-run]
```

**What it does:**
- Adds `git-fetch-with-cli = true` to `~/.cargo/config.toml` (non-destructive)
- Checks SSH config for GitLab/GitHub profiles
- Provides setup instructions for private repos

**For private repos, ensure:**
1. `~/.cargo/config.toml` has `[net]` section with `git-fetch-with-cli = true`
2. `~/.ssh/config` has host entries for gitlab.com/github.com
3. Cargo.toml uses SSH URLs: `rsb = { git = "ssh://git@gitlab.com/oodx/rsb.git", branch = "main" }`

## Command Flags

### Global Flags
- `--live`: Force live discovery instead of cache
- `--fast-mode`: Disable progress bars and interactive elements
- `--ssh-profile <profile>`: SSH profile for git operations

### Update Flags
- `--dry-run`: Show what would be updated without making changes
- `--force-commit`: Automatically commit changes with "auto:hub bump" message
- `--force`: Bypass git safety checks (main branch requirement and clean working directory)

### Special Flags
- `--create`: Create hub metadata section (for notes command)

## Advanced Features

### Dependency Conflict Detection
BLADE identifies version conflicts across your ecosystem:
- **Version mismatches** between repositories
- **Hub synchronization gaps**
- **Outdated dependencies** with available updates
- **Opportunity packages** (widely used but not in hub)

### Git Safety System
BLADE includes comprehensive git safety checks:
- Ensures operations on main branch (unless `--force`)
- Verifies clean working directory
- Automatic commit messages with `--force-commit`
- SSH profile support for multi-host environments

### Learning System
The learning system helps optimize your ecosystem:
- **Learn packages**: Add packages to hub with latest versions
- **Opportunity detection**: Identify packages for centralization
- **Bulk learning**: Process all opportunities at once
- **RSB protection**: Prevents circular dependency issues

### Repository Notes & Metadata
BLADE supports rich repository metadata:
```toml
[package.metadata.hub]
notes = "Hub metadata for repository"
hub_sync = "true"  # Set to "false" to skip in updates
priority = "medium"  # Options: high, medium, low
```

### Caching & Performance
- **TSV cache system** for lightning-fast repeated analysis
- **XDG-compliant** data storage with snekfx structure
- **Hydrated data structures** for optimal memory usage
- **Interactive progress** indicators (disable with `--fast-mode`)
- **Automatic directory creation** for data, config, and cache directories

## Hub Ecosystem Integration

### Hub Repository Pattern
BLADE is designed around the "hub" pattern - a central repository containing:
- Shared dependencies across projects
- Version coordination
- Ecosystem-wide standards
- Centralized updates

### Hub Dashboard Features
The `blade hub` command provides:
- **Current packages**: Dependencies already in hub
- **Outdated tracking**: Hub packages needing updates
- **Gap analysis**: Missing packages with high usage
- **Unused detection**: Hub packages not actively used
- **Unique packages**: Repository-specific dependencies

### Ecosystem Operations
```bash
# Update entire ecosystem following hub patterns
blade eco --dry-run

# Force ecosystem update with auto-commits
blade eco --force-commit --force

# Review ecosystem state
blade review
```

## Color-Coded Output

BLADE uses semantic colors for quick visual parsing:
- 🔵 **Blue**: Current/up-to-date packages
- 🟠 **Orange**: Outdated packages needing updates
- 🟢 **Green**: Opportunity packages (high usage, not in hub)
- 🔴 **Red**: Unused packages or errors
- ⚫ **Gray**: Low-priority/unique packages
- 🟣 **Purple**: Special categories and highlights

## Safety & Error Handling

### Git Safety Checks
- Verifies main branch before operations
- Ensures clean working directory
- Prevents destructive operations without explicit flags
- SSH profile validation for multi-host setups

### Error Recovery
- Graceful handling of network failures
- Cargo.toml parsing error recovery
- Rollback capabilities for failed updates
- Detailed error reporting with context

### Force Operations
Use `--force` flag to bypass safety checks when needed:
- Works on non-main branches
- Allows operations with uncommitted changes
- Enables emergency ecosystem repairs
- Should be used with caution

## Future Roadmap

### Multi-Language Support
BLADE is architected for expansion to support:

**Bash Repositories**
- Shell script dependency analysis
- Source file tracking
- Library usage patterns

**Python Repositories**
- requirements.txt and pyproject.toml support
- Virtual environment integration
- PyPI version checking

**JavaScript Repositories**
- package.json analysis
- npm/yarn integration
- Node.js ecosystem patterns

### Planned Features
- **Cross-language dependency tracking**
- **Unified ecosystem dashboards**
- **Language-agnostic update operations**
- **Multi-ecosystem conflict detection**
- **Enhanced learning systems**
- **Plugin architecture**

### Integration Enhancements
- **CI/CD pipeline integration**
- **Automated dependency monitoring**
- **Security vulnerability scanning**
- **License compliance checking**
- **Dependency update automation**

## Examples

### Basic Workflow
```bash
# Deploy blade system-wide
./bin/deploy.sh

# Analyze current ecosystem
blade

# Check for opportunities
blade hub

# Learn high-value packages
blade learn serde
blade learn tokio

# Update specific repository
blade update my-api --dry-run
blade update my-api --force-commit

# Ecosystem-wide update
blade eco --dry-run
blade eco --force-commit --force
```

### Deep Analysis
```bash
# Detailed package analysis
blade pkg serde

# Search for logging packages
blade search log

# View tokio dependency graph
blade graph tokio

# Repository-specific dependencies
blade deps my-service
```

### Maintenance Operations
```bash
# Export data for external analysis (saves to ~/.local/share/snek/blade/)
blade export

# Clean build artifacts
blade superclean

# Refresh cache with live data
blade ls --live
blade data

# Manage repository notes
blade notes my-repo
blade notes my-repo --create
```

## Contributing

BLADE is designed as a standalone tool with a focus on:
- **Performance**: Lightning-fast analysis through intelligent caching
- **Safety**: Comprehensive git and operation safety checks
- **Extensibility**: Architecture ready for multi-language support
- **User Experience**: Rich, color-coded output with clear workflows

When contributing:
1. Maintain backwards compatibility with existing hub ecosystems
2. Follow XDG Base Directory specifications
3. Ensure comprehensive error handling and safety checks
4. Add tests for new language support
5. Update documentation for new features

## License

[License information to be added during migration]

---

*BLADE: Because dependency management should be sharp, precise, and powerful.* 🗡️
