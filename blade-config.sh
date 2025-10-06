#!/usr/bin/env bash
# Blade configuration helper
# Sets up environment variables for blade.py and blade-repo.py

# Auto-detect rust root
detect_rust_root() {
    local current_dir="$PWD"

    # Walk up directory tree looking for 'rust' directory
    while [[ "$current_dir" != "/" ]]; do
        if [[ "$(basename "$current_dir")" == "rust" ]]; then
            echo "$current_dir"
            return 0
        fi
        if [[ -d "$current_dir/rust" ]]; then
            echo "$current_dir/rust"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done

    # Fallback to common locations
    if [[ -d "$HOME/repos/code/rust" ]]; then
        echo "$HOME/repos/code/rust"
        return 0
    fi

    return 1
}

# Auto-detect hub path
detect_hub_path() {
    local rust_root="$1"

    # Try new location first
    if [[ -f "$rust_root/prods/oodx/hub/Cargo.toml" ]]; then
        echo "$rust_root/prods/oodx/hub"
        return 0
    fi

    # Try old location
    if [[ -f "$rust_root/oodx/projects/hub/Cargo.toml" ]]; then
        echo "$rust_root/oodx/projects/hub"
        return 0
    fi

    # Try other common locations
    if [[ -f "$rust_root/oodx/hub/Cargo.toml" ]]; then
        echo "$rust_root/oodx/hub"
        return 0
    fi

    if [[ -f "$rust_root/hub/Cargo.toml" ]]; then
        echo "$rust_root/hub"
        return 0
    fi

    return 1
}

# Main configuration
main() {
    # Detect or use provided RUST_REPO_ROOT
    if [[ -z "$RUST_REPO_ROOT" ]]; then
        RUST_REPO_ROOT=$(detect_rust_root)
        if [[ $? -eq 0 ]]; then
            export RUST_REPO_ROOT
            echo "✓ Auto-detected RUST_REPO_ROOT: $RUST_REPO_ROOT"
        else
            echo "⚠ Could not auto-detect RUST_REPO_ROOT. Please set manually:"
            echo "  export RUST_REPO_ROOT=/path/to/rust"
            return 1
        fi
    else
        echo "✓ Using existing RUST_REPO_ROOT: $RUST_REPO_ROOT"
    fi

    # Detect or use provided HUB_HOME/HUB_PATH
    # Prioritize HUB_HOME (standard var) over HUB_PATH
    if [[ -z "$HUB_HOME" && -z "$HUB_PATH" ]]; then
        HUB_HOME=$(detect_hub_path "$RUST_REPO_ROOT")
        if [[ $? -eq 0 ]]; then
            export HUB_HOME
            echo "✓ Auto-detected HUB_HOME: $HUB_HOME"
        else
            echo "⚠ Could not auto-detect HUB_HOME. Please set manually:"
            echo "  export HUB_HOME=/path/to/hub"
            return 1
        fi
    elif [[ -n "$HUB_HOME" ]]; then
        echo "✓ Using existing HUB_HOME: $HUB_HOME"
    else
        echo "✓ Using existing HUB_PATH: $HUB_PATH"
    fi

    echo ""
    echo "Configuration complete! You can now run blade.py and blade-repo.py"
    echo ""
    echo "To make this permanent, add to your ~/.bashrc or ~/.zshrc:"
    echo "  export RUST_REPO_ROOT=\"$RUST_REPO_ROOT\""
    if [[ -n "$HUB_HOME" ]]; then
        echo "  export HUB_HOME=\"$HUB_HOME\""
    else
        echo "  export HUB_PATH=\"$HUB_PATH\""
    fi
}

# If sourced, run main; if executed, also run main
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
else
    main "$@"
fi
