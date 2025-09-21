#!/bin/bash
set -e

# Configuration
SNAKE_BIN_DIR="$HOME/.local/bin/snek"

# Resolve repository root from bin/
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Extract version from Cargo.toml at repo root for display
VERSION=$(grep '^version' "$ROOT_DIR/Cargo.toml" | head -1 | cut -d'"' -f2 2>/dev/null || echo "unknown")

# Display deployment ceremony
echo "╔════════════════════════════════════════════════╗"
echo "║              BLADE DEPLOYMENT                  ║"
echo "╠════════════════════════════════════════════════╣"
echo "║ Package: Blade Dependency Management Tool      ║"
echo "║ Version: v$VERSION                             ║"
echo "║ Target:  $SNAKE_BIN_DIR/                       ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# Deploy Blade tool
echo "⚔️  Deploying Blade tool..."
mkdir -p "$SNAKE_BIN_DIR"

REPOS_SOURCE="$ROOT_DIR/blade.py"
BLADE_TARGET="$SNAKE_BIN_DIR/blade"

if [ -f "$REPOS_SOURCE" ]; then
    # Deploy as blade
    if ! cp "$REPOS_SOURCE" "$BLADE_TARGET"; then
        echo "❌ Failed to copy blade to $BLADE_TARGET"
        exit 1
    fi

    if ! chmod +x "$BLADE_TARGET"; then
        echo "❌ Failed to make blade executable"
        exit 1
    fi

    echo "✅ Blade tool deployed to $BLADE_TARGET"

    # Test the deployment
    echo "🧪 Testing blade deployment..."
    if command -v blade >/dev/null 2>&1; then
        echo "✅ blade is available in PATH"
    else
        echo "⚠️  Warning: blade not found in PATH (may need to restart shell)"
    fi
else
    echo "❌ Error: repos.py not found at $REPOS_SOURCE"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║          DEPLOYMENT SUCCESSFUL!                ║"
echo "╚════════════════════════════════════════════════╝"
echo "  Deployed: Blade v$VERSION                      "
echo "  Location: $BLADE_TARGET                        "
echo ""
echo "⚔️  Blade dependency management commands:"
echo "   blade hub                   # Hub package status with safety analysis"
echo "   blade conflicts             # Version conflicts across ecosystem"
echo "   blade review                # Comprehensive dependency review"
echo "   blade usage                 # Usage analysis by priority"
echo "   blade outdated              # Find outdated packages"
echo "   blade update <repo>         # Update specific repository dependencies"
echo "   blade eco                   # Update entire ecosystem"
echo "   blade search <package>      # Search for package information"
echo "   blade --help                # Full command reference"
echo ""
echo "🚀 Ready to slice through your dependency management!"
