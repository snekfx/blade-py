# Blade Upgrade Plan: Multi-Language Dependency Management

## Overview

This document outlines the architectural upgrade plan for Blade, evolving it from a Rust-specific dependency analyzer to a comprehensive multi-language dependency management system. The upgrade will be implemented as a parallel build to preserve the existing `blade.py` functionality.

## Current State

- **File**: Single monolithic `blade.py` (5063 lines)
- **Scope**: Rust repositories only
- **Features**: Dependency analysis, version tracking, updates, ecosystem reporting
- **Location**: `blade-py/blade.py`

## Target Architecture

### Vision
Transform Blade into a language-agnostic dependency management tool that handles Rust, Python, Node.js, and Bash repositories with consistent commands and unified reporting.

### Core Design Principles

1. **Language Agnostic Core**: Core models and abstractions don't contain language-specific logic
2. **Plugin Architecture**: New languages can be added without modifying core
3. **Consistent Interface**: Same command patterns work across all languages
4. **Preserve Current Tool**: Existing `blade.py` remains functional during migration
5. **Progressive Enhancement**: Features can be added incrementally per language

## Proposed Structure

### Directory Layout

```
blade-next/                    # New parallel implementation
├── blade.py                   # Main CLI router
├── core/
│   ├── __init__.py
│   ├── ecosystem.py           # Language-agnostic ecosystem model
│   ├── repository.py          # Base repository abstractions
│   ├── dependency.py          # Base dependency model
│   ├── scanner.py             # Repository discovery & classification
│   └── config.py              # Configuration management
│
├── languages/                 # Language-specific implementations
│   ├── __init__.py
│   ├── base.py                # Abstract base classes/protocols
│   │
│   ├── rust/
│   │   ├── __init__.py
│   │   ├── analyzer.py        # Cargo.toml parsing
│   │   ├── updater.py         # Cargo dependency updates
│   │   ├── crates.py          # crates.io API client
│   │   ├── models.py          # Rust-specific data models
│   │   └── commands.py        # Rust-specific CLI commands
│   │
│   ├── python/
│   │   ├── __init__.py
│   │   ├── analyzer.py        # pyproject.toml/requirements.txt parsing
│   │   ├── updater.py         # pip/poetry/uv updates
│   │   ├── pypi.py            # PyPI API client
│   │   ├── models.py          # Python-specific data models
│   │   └── commands.py        # Python-specific CLI commands
│   │
│   ├── nodejs/
│   │   ├── __init__.py
│   │   ├── analyzer.py        # package.json/yarn.lock parsing
│   │   ├── updater.py         # npm/yarn/pnpm updates
│   │   ├── npm.py             # npm registry API client
│   │   ├── models.py          # Node-specific data models
│   │   └── commands.py        # Node-specific CLI commands
│   │
│   └── bash/
│       ├── __init__.py
│       ├── analyzer.py        # Shell script analysis
│       ├── deps.py            # External command dependency detection
│       ├── models.py          # Bash-specific data models
│       └── commands.py        # Bash-specific CLI commands
│
├── commands/                  # Global cross-language commands
│   ├── __init__.py
│   ├── scan.py                # Discover all repositories
│   ├── status.py              # Multi-language status overview
│   ├── update.py              # Cross-language update orchestration
│   ├── report.py              # Unified dependency reporting
│   └── export.py              # Data export functionality
│
├── ui/                        # Shared UI components
│   ├── __init__.py
│   ├── colors.py              # Color definitions
│   ├── output.py              # Progress indicators, formatting
│   ├── boxy.py                # Boxy integration
│   └── formatters.py          # Display formatting utilities
│
└── utils/                     # Shared utilities
    ├── __init__.py
    ├── xdg.py                 # XDG directory management
    ├── git.py                 # Git operations
    ├── cache.py               # Caching mechanisms
    └── version.py             # Version parsing and comparison
```

## Command Structure

### Global Commands

```bash
# Repository discovery and overview
blade scan                     # Discover all repos across languages
blade status                   # Overview of all ecosystems
blade report                   # Unified dependency report
blade export                   # Export data in various formats

# Cross-language operations
blade update --all             # Update all languages
blade outdated                 # Show outdated deps across languages
blade conflicts                # Find version conflicts
blade stats                    # Statistics across ecosystems
```

### Language-Specific Subcommands

```bash
# Rust (current blade.py functionality)
blade rust status              # Rust ecosystem status
blade rust review              # Detailed Rust dependency review
blade rust update <repo>       # Update specific Rust repo
blade rust eco                 # Update entire Rust ecosystem
blade rust pkg <package>       # Analyze specific crate usage
blade rust latest <package>    # Check latest crate version

# Python
blade python status            # Python ecosystem status
blade python outdated          # Show outdated Python packages
blade python update <repo>     # Update Python dependencies
blade python venv <repo>       # Virtual environment management
blade python pkg <package>     # Analyze specific package usage

# Node.js
blade node status              # Node ecosystem status
blade node audit               # Security audit
blade node update <repo>       # Update Node dependencies
blade node lockfile            # Lockfile management
blade node pkg <package>       # Analyze specific npm package

# Bash
blade bash scan                # Analyze bash script dependencies
blade bash validate            # Check script portability
blade bash deps                # List external command dependencies
blade bash lint                # Shell script linting
```

## Core Abstractions

### Base Protocol Classes

```python
# languages/base.py
from typing import Protocol, List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass

class LanguageAnalyzer(Protocol):
    """Protocol for language-specific analyzers"""

    def detect_repository(self, path: Path) -> bool:
        """Check if path contains this language's repository"""
        ...

    def scan_repository(self, repo_path: Path) -> 'RepoMetadata':
        """Scan repository and extract metadata"""
        ...

    def parse_dependencies(self, manifest_path: Path) -> List['Dependency']:
        """Parse dependencies from manifest file"""
        ...

    def get_latest_version(self, package: str) -> 'Version':
        """Get latest version from package registry"""
        ...

    def update_manifest(self, manifest_path: Path, updates: Dict) -> bool:
        """Update manifest file with new versions"""
        ...

@dataclass
class Repository:
    """Language-agnostic repository representation"""
    path: Path
    language: str
    name: str
    dependencies: List['Dependency']
    dev_dependencies: List['Dependency']
    metadata: Dict

@dataclass
class Dependency:
    """Language-agnostic dependency representation"""
    name: str
    version: str
    dep_type: str  # runtime, dev, build, optional
    source: str    # registry URL
    constraints: str  # version constraints

@dataclass
class Ecosystem:
    """Multi-language ecosystem representation"""
    repositories: Dict[str, List[Repository]]  # language -> repos
    total_deps: int
    languages: List[str]
    conflicts: List['Conflict']
```

## Migration Strategy

### Phase 1: Foundation (Week 1-2)
- [x] Document upgrade plan
- [ ] Create `blade-next/` directory structure
- [ ] Implement core abstractions and base classes
- [ ] Set up plugin loading mechanism
- [ ] Create basic CLI router with subcommand support

### Phase 2: Rust Migration (Week 3-4)
- [ ] Port current `blade.py` functionality to `languages/rust/`
- [ ] Implement `blade rust` subcommand with all current features
- [ ] Validate feature parity with existing tool
- [ ] Add tests for Rust analyzer

### Phase 3: Python Support (Week 5-6)
- [ ] Implement Python analyzer for `pyproject.toml`, `requirements.txt`, `setup.py`
- [ ] Add PyPI API client
- [ ] Implement `blade python` subcommands
- [ ] Support pip, poetry, and uv package managers

### Phase 4: Node.js Support (Week 7-8)
- [ ] Implement Node analyzer for `package.json`, lockfiles
- [ ] Add npm registry API client
- [ ] Implement `blade node` subcommands
- [ ] Support npm, yarn, and pnpm package managers

### Phase 5: Bash Support (Week 9)
- [ ] Implement Bash script analyzer
- [ ] Add external command dependency detection
- [ ] Implement `blade bash` subcommands
- [ ] Add portability checking

### Phase 6: Integration (Week 10)
- [ ] Implement cross-language commands
- [ ] Add unified reporting
- [ ] Create comprehensive test suite
- [ ] Write user documentation

## Benefits

### For Developers
- **Unified Interface**: One tool for all dependency management
- **Consistent Commands**: Same patterns across languages
- **Cross-Language Insights**: See dependencies across entire codebase
- **Batch Operations**: Update everything in one pass

### For Maintenance
- **Modular Design**: Easy to modify and extend
- **Clear Separation**: Language-specific logic is isolated
- **Testable Components**: Each module can be unit tested
- **Plugin Architecture**: New languages added without core changes

### For Operations
- **Single Tool**: Reduced toolchain complexity
- **Comprehensive Reports**: Full dependency visibility
- **Automated Updates**: Consistent update strategy
- **Security Scanning**: Unified vulnerability checking

## Technical Considerations

### Performance
- Lazy loading of language modules
- Parallel scanning of repositories
- Efficient caching of API responses
- Incremental updates

### Compatibility
- Python 3.8+ requirement
- Support for multiple package manager versions
- Graceful degradation for missing features
- Backward compatibility with existing workflows

### Configuration
- XDG-compliant configuration location
- Per-language configuration options
- Global and repository-specific overrides
- Environment variable support

## Success Criteria

1. **Feature Parity**: All current `blade.py` functionality available in new system
2. **Language Support**: Full support for Rust, Python, Node.js, and Bash
3. **Performance**: Scanning and analysis no slower than current tool
4. **User Experience**: Intuitive and consistent command interface
5. **Maintainability**: Clear code structure with comprehensive tests

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| API Rate Limiting | Medium | Implement caching and batch requests |
| Language Complexity | High | Start with basic features, iterate |
| Migration Disruption | Low | Parallel build approach |
| Performance Degradation | Medium | Profile and optimize critical paths |
| Scope Creep | High | Strict phase boundaries, feature freeze |

## Future Enhancements

- **Additional Languages**: Go, Ruby, Java, C/C++
- **CI/CD Integration**: GitHub Actions, GitLab CI
- **Security Scanning**: CVE database integration
- **License Compliance**: Dependency license tracking
- **Metrics Dashboard**: Web-based dependency insights
- **Policy Engine**: Organizational dependency policies
- **Monorepo Support**: Special handling for monorepos

## Conclusion

This upgrade transforms Blade from a Rust-specific tool into a comprehensive, multi-language dependency management system while preserving all existing functionality. The parallel build approach ensures zero disruption to current workflows while enabling progressive enhancement and future extensibility.