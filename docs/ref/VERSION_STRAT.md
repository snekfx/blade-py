# Rust Semantic Versioning Strategy

## Overview

This document defines the semantic versioning (SemVer) strategy for Rust projects in the oodx ecosystem, based on official Rust/Crates.io guidelines and best practices.

## Rust SemVer Rules

### Breaking Changes (Major Version Bump Required)

#### **API Changes**
- **Function signature changes** - Parameters, return types, generic constraints
- **Removing public items** - Functions, structs, traits, modules, constants
- **Changing public struct fields** - Field types, visibility, adding/removing fields
- **Trait changes** - Adding required methods, changing existing method signatures
- **Enum changes** - Adding/removing variants in `#[non_exhaustive]` enums

#### **Behavioral Changes**
- **MSRV increases** - Minimum Supported Rust Version bumps
- **Dependency major version bumps** - If they affect the public API surface
- **Changing error types** - New error variants, different error structures
- **Performance regressions** - Significant algorithmic changes affecting guarantees

### Non-Breaking Changes (Minor/Patch Allowed)

#### **Minor Version Bumps (New Features)**
- **Adding new public APIs** - New functions, traits, methods, modules
- **Adding optional parameters** - With default values
- **Adding new trait implementations** - For existing types
- **Adding new enum variants** - In `#[non_exhaustive]` enums
- **Relaxing generic constraints** - Making APIs more permissive
- **Adding new optional dependencies** - With feature gates

#### **Patch Version Bumps (Bug Fixes)**
- **Bug fixes** - Internal fixes that don't change public API
- **Performance improvements** - Without changing behavior guarantees
- **Documentation improvements** - Comments, examples, README updates
- **Internal refactoring** - Code organization, private implementation details
- **Dependency patch updates** - That don't affect public API

## Special Cases

### **0.x Versions (Pre-1.0)**
```toml
# For 0.x versions, minor bumps CAN be breaking:
some-crate = "0.3" → "0.4"        # Could be breaking ⚠️
some-crate = "0.3.1" → "0.3.2"    # Should be safe ✅
```

**Rule**: Treat 0.x.y → 0.(x+1).0 as potentially breaking changes.

### **Yanked Versions**
- **Never depend on yanked versions** - They may be removed
- **Update immediately** - If your dependency gets yanked
- **Check for security issues** - Common reason for yanking

### **Pre-release Versions**
```toml
# Pre-release versions:
some-crate = "1.0.0-alpha.1"     # Alpha release
some-crate = "1.0.0-beta.2"      # Beta release
some-crate = "1.0.0-rc.1"        # Release candidate
```

**Rule**: Pre-release versions can have breaking changes between pre-releases.

## oodx Ecosystem Strategy

### **Hub Dependency Management**
- **Patch updates**: Safe to apply automatically
- **Minor updates**: Safe for most dependencies, test thoroughly
- **Major updates**: Require ecosystem-wide coordination through hub
- **0.x updates**: Treat minor bumps as potentially breaking

### **Version Pinning Strategy**
```toml
# Recommended patterns for hub:
serde = "1.0"           # Allow minor + patch updates
chrono = "0.4.42"       # Pin specific version for 0.x crates
clap = "~4.5.0"         # Allow only patch updates for critical deps
```

### **Update Priorities**
1. **Security patches** - Immediate update required
2. **Bug fix patches** - Low risk, high benefit
3. **Minor feature updates** - Evaluate benefit vs. ecosystem impact
4. **Major version updates** - Coordinate across entire ecosystem

## Testing Strategy

### **Before Updates**
- **Run full test suite** - All ecosystem projects
- **Check for deprecation warnings** - May indicate future breaking changes
- **Review changelogs** - Understand what's changing
- **Test integration points** - Cross-project dependencies

### **During Updates**
- **Update incrementally** - One dependency at a time when possible
- **Monitor for compilation errors** - API breakage indicators
- **Run ecosystem tests** - Ensure no behavioral regressions
- **Check performance impacts** - Major algorithmic changes

### **After Updates**
- **Update documentation** - Reflect new version requirements
- **Commit with clear messages** - Document what was updated and why
- **Tag versions** - For ecosystem-wide coordinated updates

## Common Pitfalls

### **Misunderstanding SemVer**
- **❌ "Minor versions are always safe"** - Not true for 0.x versions
- **❌ "Patch updates can't break anything"** - Bug fixes can change behavior
- **❌ "Major version = rewrite"** - Major versions can be small API changes

### **Ecosystem Coordination**
- **❌ Updating dependencies in isolation** - Can cause version conflicts
- **❌ Not testing cross-project impacts** - Integration failures
- **❌ Ignoring MSRV requirements** - Compiler compatibility issues

### **Hub-Specific Considerations**
- **❌ Updating hub without testing consumers** - Breaks downstream projects
- **❌ Not communicating updates** - Teams unaware of dependency changes
- **❌ Mixing major and minor updates** - Difficult to isolate issues

## Custom Metadata in Cargo.toml

### **Hub-Specific Fields**
```toml
[package]
name = "my-project"
version = "0.1.0"

# Hub integration metadata
[package.metadata.hub]
priority = "high"                    # Integration priority: high/medium/low
migration-status = "pending"         # Status: pending/in-progress/complete
original-deps = ["serde", "chrono"]  # Dependencies before hub integration
hub-features = ["text", "data"]      # Required hub features
update-strategy = "conservative"     # Update approach: conservative/aggressive

# Dependency analysis metadata
[package.metadata.deps-analysis]
last-reviewed = "2025-09-18"         # Last dependency review date
conflicts-resolved = ["regex", "uuid"] # Previously resolved conflicts
semver-policy = "strict"             # SemVer adherence: strict/relaxed
```

### **Safe Custom Fields**
- **Cargo ignores unknown fields** - No build impact
- **Git handles them normally** - Standard version control
- **Use metadata sections** - Official recommendation: `package.metadata.yourname`
- **Prefix field names** - Avoid conflicts with future Cargo features

### **Hub Ecosystem Benefits**
- **Track migration progress** - Which projects are hub-ready
- **Coordinate updates** - Priority and strategy information
- **Historical context** - What dependencies were replaced
- **Automation support** - Scripts can read metadata for decisions

## Tools and Automation

### **Version Analysis**
- **`cargo outdated`** - Check for available updates
- **`cargo audit`** - Security vulnerability scanning
- **`./bin/repos.py`** - Hub ecosystem repository and dependency analysis
- **`semv`** - Semantic version management (see semv integration)

### **Testing Automation**
- **CI/CD pipelines** - Automated testing across ecosystem
- **Dependency bots** - Automated patch update PRs
- **Integration tests** - Cross-project compatibility validation

## Integration with semv Tool

The `semv` tool automates version management following our SemVer strategy:

### **semv Commit Label Strategy**
```bash
# Breaking changes → Major bump (1.0.0 → 2.0.0)
git commit -m "major: redesign public API"
git commit -m "breaking: remove deprecated methods"
git commit -m "api: change function signatures"

# New features → Minor bump (1.0.0 → 1.1.0)
git commit -m "feat: add hub integration command"
git commit -m "feature: ecosystem analysis tools"
git commit -m "add: new dependency resolution"
git commit -m "minor: enhanced visual design"

# Bug fixes/docs → Patch bump (1.0.0 → 1.0.1)
git commit -m "fix: correct version parsing"
git commit -m "patch: resolve color inconsistencies"
git commit -m "bug: handle missing dependencies"
git commit -m "hotfix: critical security update"
git commit -m "up: documentation improvements"

# Development work → Dev build (1.0.0-dev.1)
git commit -m "dev: work in progress on meteor integration"
```

### **semv Integration Commands**
```bash
# Current project status
semv info                    # Show version sources and next version
semv get all                 # Check Cargo.toml vs git tags
semv pend                    # Review pending changes since last tag

# Version management
semv next                    # Preview next version (dry run)
semv bump                    # Create and push new version tag
semv set rust 0.2.0          # Update Cargo.toml version

# Hub-specific workflow
semv audit                   # Full repository and version state
semv sync                    # Sync versions across files
```

### **Hub Ecosystem Coordination**
```bash
# Before major dependency updates:
./bin/repos.py conflicts      # Check version conflicts
./bin/repos.py hub            # Hub ecosystem status
semv pend                    # Review pending changes
semv next                    # Confirm version impact

# After completing analysis tools:
git commit -m "feat: production-ready analysis tools with smart visual design"
semv bump                    # Creates v0.2.0 tag (minor bump for new features)

# For breaking hub changes:
git commit -m "major: change hub feature structure"
semv next                    # Would show v1.0.0 (major bump)
```

### **Version Strategy Alignment**
- **semv detects**: Commit patterns → version type
- **VERSION_STRAT.md defines**: What constitutes breaking vs. non-breaking
- **./bin/repos.py provides**: Comprehensive ecosystem analysis
- **Combined workflow**: Safe, coordinated version management

### **Hub Development Workflow**
1. **Check ecosystem**: `./bin/repos.py conflicts` and `./bin/repos.py hub` - understand current state
2. **Make changes**: Following VERSION_STRAT.md guidelines
3. **Commit with labels**: Use semv-compatible commit messages
4. **Review impact**: `semv pend` and `semv next`
5. **Coordinate updates**: Ensure hub consumers can handle changes
6. **Release**: `semv bump` for coordinated ecosystem release

---

## Integration with Current Hub Tools

### repos.py Command Integration
The hub ecosystem uses `./bin/repos.py` for all dependency analysis and ecosystem management:

```bash
# Version conflict detection and analysis
./bin/repos.py conflicts    # Replaces manual conflict checking
./bin/repos.py stats        # Ecosystem overview and metrics

# Dependency review workflow
./bin/repos.py review       # Enhanced review with latest versions
./bin/repos.py outdated     # Packages with available updates

# Hub status dashboard
./bin/repos.py hub          # Hub integration status and gaps

# Package-specific analysis
./bin/repos.py pkg <name>   # Deep dive into specific packages
./bin/repos.py deps <repo>  # Repository dependency analysis
./bin/repos.py search <pattern>  # Package search across ecosystem
./bin/repos.py graph <package>   # Dependency relationship mapping
```

### Enhanced Version Management Workflow
```bash
# 1. Analyze current ecosystem state
./bin/repos.py conflicts    # Identify version conflicts
./bin/repos.py outdated     # Check for available updates

# 2. Review specific package impacts
./bin/repos.py pkg serde    # Analyze specific package usage
./bin/repos.py graph serde  # Map dependency relationships

# 3. Make version changes following SemVer strategy
git commit -m "feat: update serde with backward compatibility"

# 4. Validate ecosystem after changes
./bin/repos.py hub          # Check hub integration status
./bin/repos.py review       # Full ecosystem review

# 5. Use semv for coordinated releases
semv bump                   # Create version tag
```

---

**Key Principle**: *In the oodx ecosystem, we prioritize stability and coordination over rapid updates. Every version change should be evaluated for its impact across all dependent projects.*