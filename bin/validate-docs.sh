#!/bin/bash
# validate-docs.sh - Meta Process v3 Documentation Validator
# Purpose: Verify documentation integrity and process compliance
# Usage: ./bin/validate-docs.sh [--verbose]

set -e

VERBOSE=false
[[ "$1" == "--verbose" ]] && VERBOSE=true

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0

# Helper functions
error() {
    echo -e "${RED}✗ ERROR${NC}: $1" >&2
    ((ERRORS++))
}

warning() {
    echo -e "${YELLOW}⚠ WARNING${NC}: $1" >&2
    ((WARNINGS++))
}

success() {
    [[ "$VERBOSE" == true ]] && echo -e "${GREEN}✓${NC} $1"
}

# === PHASE 1: File Existence Checks ===
check_file_exists() {
    local file=$1
    local description=$2
    if [[ -f "$file" ]]; then
        success "$description exists"
    else
        error "$description missing: $file"
    fi
}

# === PHASE 2: Process File Structure ===
check_process_files() {
    success "Checking process file structure..."

    check_file_exists "START.txt" "START.txt (entry point)"
    check_file_exists "docs/procs/PROCESS.txt" "PROCESS.txt"
    check_file_exists "docs/procs/HANDOFF.md" "HANDOFF.md"
    check_file_exists "docs/procs/QUICK_REF.txt" "QUICK_REF.txt"
    check_file_exists "docs/procs/TASKS.txt" "TASKS.txt"
    check_file_exists "docs/procs/DONE.txt" "DONE.txt"
    check_file_exists "docs/procs/ROADMAP.txt" "ROADMAP.txt"
}

# === PHASE 3: Last Updated Timestamps ===
check_timestamps() {
    success "Checking Last Updated timestamps..."

    local files=(
        "docs/procs/PROCESS.txt"
        "docs/procs/HANDOFF.md"
        "docs/procs/QUICK_REF.txt"
        "docs/procs/TASKS.txt"
        "docs/procs/DONE.txt"
        "docs/procs/ROADMAP.txt"
    )

    for file in "${files[@]}"; do
        if [[ -f "$file" ]]; then
            if grep -q "^Last Updated:" "$file"; then
                local timestamp=$(head -1 "$file" | grep -oP '(?<=Last Updated: )\d{4}-\d{2}-\d{2}' || echo "")
                if [[ -n "$timestamp" ]]; then
                    success "$file has timestamp: $timestamp"
                else
                    warning "$file has Last Updated but wrong format: $(head -1 "$file")"
                fi
            else
                error "$file missing 'Last Updated: YYYY-MM-DD' at top"
            fi
        fi
    done
}

# === PHASE 4: Content Validation ===
check_content() {
    success "Checking critical content patterns..."

    # START.txt should point to key documents
    if grep -q "PROCESS.txt" START.txt; then
        success "START.txt references PROCESS.txt"
    else
        error "START.txt doesn't reference PROCESS.txt"
    fi

    if grep -q "QUICK_REF.txt" START.txt; then
        success "START.txt references QUICK_REF.txt"
    else
        error "START.txt doesn't reference QUICK_REF.txt"
    fi

    # HANDOFF.md should have proper template
    if grep -q "Session Summary" docs/procs/HANDOFF.md; then
        success "HANDOFF.md has Session Summary section"
    else
        warning "HANDOFF.md template may be missing Session Summary"
    fi

    # TASKS.txt should not have completed items
    if grep -i "completed\|✓\|done\|finished" docs/procs/TASKS.txt | grep -v "Success Criteria" > /dev/null; then
        warning "TASKS.txt may contain completed items (should only have pending work)"
    else
        success "TASKS.txt appears clean (no completed items)"
    fi
}

# === PHASE 5: Directory Structure ===
check_structure() {
    success "Checking directory structure..."

    local dirs=(
        "docs"
        "docs/procs"
        "docs/dev"
        "src"
        "tests"
        "bin"
    )

    for dir in "${dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            success "Directory exists: $dir"
        else
            warning "Directory not found: $dir"
        fi
    done
}

# === PHASE 6: Root Directory Clutter ===
check_root_clutter() {
    success "Checking root directory for process documents..."

    # Count markdown and text files in root (excluding expected ones)
    local clutter=$(find . -maxdepth 1 -type f \( -name "*.md" -o -name "*.txt" \) ! -name "START.txt" ! -name "README.md" ! -name "LICENSE*" ! -name ".gitignore" 2>/dev/null | wc -l)

    if [[ $clutter -gt 2 ]]; then
        warning "Root directory has $clutter extra doc files (should only have START.txt, README.md, LICENSE)"
    else
        success "Root directory structure looks clean"
    fi
}

# === Main Execution ===
main() {
    echo "========================================="
    echo "   Meta Process v3 Documentation Validator"
    echo "========================================="
    echo ""

    check_process_files
    echo ""

    check_timestamps
    echo ""

    check_content
    echo ""

    check_structure
    echo ""

    check_root_clutter
    echo ""

    # === SUMMARY ===
    echo "========================================="
    if [[ $ERRORS -eq 0 ]]; then
        echo -e "${GREEN}✓ VALIDATION PASSED${NC}"
        if [[ $WARNINGS -gt 0 ]]; then
            echo "  ($WARNINGS warnings - see above)"
        fi
        exit 0
    else
        echo -e "${RED}✗ VALIDATION FAILED${NC}"
        echo "  $ERRORS errors found (see above)"
        if [[ $WARNINGS -gt 0 ]]; then
            echo "  $WARNINGS warnings found"
        fi
        exit 1
    fi
}

main
