#!/bin/bash
set -e

# Configuration
SNAKE_BIN_DIR="$HOME/.local/bin/snek"

# Resolve repository root from bin/
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Extract version from blade.py or default
VERSION=$(grep -E "^__version__|^VERSION\s*=" "$ROOT_DIR/blade.py" | head -1 | cut -d'"' -f2 2>/dev/null || echo "2.0.0-dev")

# Display deployment ceremony
echo "╔════════════════════════════════════════════════╗"
echo "║              BLADE DEPLOYMENT                  ║"
echo "╠════════════════════════════════════════════════╣"
echo "║ Package: Blade Dependency Management Tool      ║"
echo "║ Version: v$VERSION                             ║"
echo "║ Target:  $SNAKE_BIN_DIR/                       ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# Create bin directory
mkdir -p "$SNAKE_BIN_DIR"

# Deploy Blade tool
echo "⚔️  Deploying Blade tool..."
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
    echo "❌ Error: blade.py not found at $REPOS_SOURCE"
    exit 1
fi

# Deploy Walker tool
echo ""
echo "🚶 Deploying Walker tool..."
WALKER_SOURCE="$ROOT_DIR/bin/walker.py"
WALKER_TARGET="$SNAKE_BIN_DIR/walker"

if [ -f "$WALKER_SOURCE" ]; then
    if ! cp "$WALKER_SOURCE" "$WALKER_TARGET"; then
        echo "❌ Failed to copy walker to $WALKER_TARGET"
        exit 1
    fi

    if ! chmod +x "$WALKER_TARGET"; then
        echo "❌ Failed to make walker executable"
        exit 1
    fi

    echo "✅ Walker tool deployed to $WALKER_TARGET"

    if command -v walker >/dev/null 2>&1; then
        echo "✅ walker is available in PATH"
    else
        echo "⚠️  Warning: walker not found in PATH (may need to restart shell)"
    fi
else
    echo "❌ Error: walker.py not found at $WALKER_SOURCE"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║          DEPLOYMENT SUCCESSFUL!                ║"
echo "╚════════════════════════════════════════════════╝"
echo "  Deployed Tools (v$VERSION):"
echo "    • Blade  → $BLADE_TARGET"
echo "    • Walker → $WALKER_TARGET"
echo ""
echo "  Location: $SNAKE_BIN_DIR/"
echo ""
echo "⚔️  Blade dependency management:"
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
echo "🚶 Walker repository discovery:"
echo "   walker                      # Scan from current directory"
echo "   walker --root <path>        # Scan from specific root"
echo "   walker --stats              # Show repository statistics"
echo ""
echo "🚀 Ready to slice through your dependency management!"
