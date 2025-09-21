# boxy 📦

A fast command-line utility that draws Unicode boxes around text with proper emoji/Unicode width handling using the unicode-width crate.

## Features

- ✨ Unicode-width crate for accurate emoji/Unicode width calculation (with custom fallback available)
- 🎨 Multiple box styles (normal, rounded, double, heavy, ascii)
- 🌈 Colored borders and text with predefined color schemes
- 🎨 Text color control with auto-matching and explicit colors
- 🎭 **5-level theme hierarchy system** with flexible theme loading
- 🎯 **Theme management commands** (hierarchy, dryrun, list, show)
- 📋 Title and footer support with emoji/variable expansion (inside borders)
- 🎯 Icon decorations for content
- 📏 Fixed width boxes with intelligent word wrapping and truncation
- 🔄 Advanced text wrapping with explicit line breaks and wrap hints
- 🎯 Three wrapping modes: auto-width wrapping (default), fixed-width with wrapping, and fixed-width with truncation
- 🔄 Pipeline integration with box stripping modes
- 🧩 Advanced layout control (align/dividers/padding for header/title/body/status/footer)
- 🛠️ Param stream (--params) to set header/title/status/footer/layout/colors alongside piped body
- 🎛️ Title/status color overrides (--title-color/--status-color)
- 🧪 BOXY_THEME default theme (env)
- 🔍 **Comprehensive emoji debugging system** for development
- 🚀 Written in Rust for speed
- 📝 Handles multi-line text and ANSI color codes

## Installation

```bash
# Build from source
cargo build --release

# Deploy to local bin
./deploy.sh
```

## Usage

```bash
# Basic usage
echo "Hello World" | boxy

# With style and color
echo "Hello World" | boxy --style rounded --color blue
echo "Hello World" | boxy -s double -c red

# With title and footer
echo "Hello World" | boxy --title "🚀 My App" --footer "v1.0"
echo "Content" | boxy --header "Header" --footer "✅ Done"

# With icon decoration and text colors
echo "Important message" | boxy --icon "⚠️" --color yellow --text red
echo "Success!" | boxy --icon "✅" --color green --text auto  # Text matches box color

# Using themes (includes icon, color, and styling)
echo "Something went wrong" | boxy --theme error
echo "Build successful" | boxy --theme success --text auto

# Text wrapping and width control
echo "This is a long message that will be wrapped intelligently" | boxy --width 20 --wrap
echo "This message will be truncated with ellipsis" | boxy --width 20
echo "Auto-width wrapping is the default behavior" | boxy

# Full width or auto width
echo "Use full terminal width" | boxy --width max
echo "Use content-based width (default)" | boxy --width auto

# Status inside the box (with alignment)
echo "Body" | boxy --status "sc:centered status" --width 40

# Layout control (align/dividers/padding)
# hl|hc|hr (header align), fl|fc|fr (footer), sl|sc|sr (status)
# dt|dtn (divider after title), ds|dsn (divider before status)
# stn (space before title), ptn (space after title), psn (space before status), ssn (space after status)
# bl|bc|br (body align), bp (pad body to match title emoji/icon)
echo "Body" | boxy --header H --title "😀 Title" --status Status --footer F \
    --layout "bp,bc,stn,ptn,psn,ssn" --width 50

# Variable expansion in titles
export VERSION="v1.2.3"
echo "Build complete" | boxy --title "🏗️ Build $VERSION" --color green

# Multi-line text
echo -e "Line 1\nLine 2\nLine 3" | boxy

# Pipeline integration - strip box decoration
echo "Content" | boxy | boxy --no-boxy          # Preserves colors
echo "Content" | boxy | boxy --no-boxy=strict   # Pure ASCII output

# With emojis (handles width correctly!)
echo -e "🎉 Party Time\n🚀 Launch\n🔥 Fire" | boxy -s rounded -c orange

# Param stream (metadata alongside piped body)
echo -e "Line 1\nLine 2" | boxy --params "hd='Header'; tl='Title'; st='Status'; ly='bl,bp,stn,ptn,psn,ssn'" --width max

# Title/Status color overrides
echo "Body" | boxy --title "Title" --status Status --title-color crimson --status-color jade
```

### CLI Reference (v0.11.0)

**Input & Content:**
- Pipe content to `boxy` or pass via `--params` (metadata only)
- `--params <stream>` - Parse metadata stream: `hd='header'; ft='footer';` etc.

**Visual Styling:**
- `--style <STYLE>` - Border style: normal, rounded, double, heavy, ascii
- `--color <COLOR>` - Border color from 90+ palette
- `--text <COLOR>` - Text color: 'auto' matches border, 'none' default
- `--width <N|max|auto>` - Set width: number, 'max' (terminal), or 'auto'
- `--wrap` - Enable hint-aware wrapping for fixed widths

**Content Sections:**
- `--header <TEXT>` - External header (above the box)
- `--title <TEXT>` - Title line (first in-box line; emoji-aware icon)
- `--status <TEXT>` - Status line inside box (use sl:|sc:|sr: prefixes)
- `--footer <TEXT>` - Footer text (inside bottom border)
- `--icon <ICON>` - Add icon to content (deprecated - use --title)

**Color Controls:**
- `--title-color <COLOR>` - Color for title line (overrides --text)
- `--status-color <COLOR>` - Color for status line (overrides --text)
- `--header-color <COLOR>` - Color for header line
- `--footer-color <COLOR>` - Color for footer line

**Layout Controls:**
- `--layout <spec>` - Align/divide/pad: hl|hc|hr, fl|fc|fr, sl|sc|sr, dt|dtn, ds|dsn, stn|ptn|psn|ssn, bl|bc|br, bp
- `--pad <a|b>` - Blank line above (a) and/or below (b) the body

**Theme System:**
- `--theme <name>` - Apply semantic theme (error, success, warning, info, critical)
- `boxy theme list` - List all available themes
- `boxy theme show <name>` - Show theme details
- `boxy theme create <name>` - Create new theme interactively
- `boxy theme import <file>` - Import theme from YAML
- `boxy theme export <name>` - Export theme to YAML
- `boxy theme edit <name>` - Edit existing theme
- `boxy theme hierarchy` - Display theme loading hierarchy
- `boxy theme dryrun <name>` - Test theme with sample content

**Utility Commands:**
- `--no-boxy[=strict]` - Strip box decoration (strict removes all formatting)
- `--no-color` - Disable Jynx integration and color output
- `boxy width` - Show terminal width diagnostics
- `--colors` - Preview all 90+ available colors
- `--help` - Show help message
- `--version` - Show version information

**Environment Variables:**
- `BOXY_THEME=<name>` - Set default theme (overridden by --theme)
- `BOXY_MIN_WIDTH=<N>` - Set minimum box width (default: 5)
- `BOXY_MULTIPLEX_MODE=<mode>` - Control multiplex behavior
- `BOXY_USE_CUSTOM_WIDTH=1` - Use custom width calculation fallback (instead of unicode-width crate)
- `HOME` - Used for theme hierarchy and configuration paths
- `USER` - Used in theme variable expansion

## Text Wrapping and Width Control

Boxy provides sophisticated text wrapping capabilities with three distinct modes and special markers for precise control over line breaks and wrap points.

### Wrapping Modes

#### 1. Auto-Width Wrapping (Default)
When no `--width` is specified, boxy automatically wraps text at terminal boundaries:

```bash
# Default behavior - wraps at terminal width
echo "This is a very long line that will be automatically wrapped at the terminal boundary to fit nicely within your screen" | boxy

# Explicit auto-width (same as above)
echo "Long text here..." | boxy --width auto
```

**Behavior**: Automatic wrapping, wrap hints (`#W#`, `#T#`) are removed from output.

#### 2. Fixed-Width with Wrapping
Use `--width <N> --wrap` for intelligent hint-aware wrapping:

```bash
# Fixed width with smart wrapping
echo "This text will wrap#W#intelligently at word boundaries" | boxy --width 25 --wrap

# With wrap hints for better control
echo "First part#W#second part#W#third part" | boxy --width 20 --wrap
```

**Behavior**: Uses wrap hints when lines exceed width, falls back to optimal word boundaries.

#### 3. Fixed-Width with Truncation
Use `--width <N>` without `--wrap` for truncation with ellipsis:

```bash
# Truncation mode
echo "This long message will be cut off..." | boxy --width 20

# Shows: "This long message..."
```

**Behavior**: Truncates with ellipsis (`...`) when content exceeds width.

### Special Markers

#### `#NL#` - Explicit Newline Marker
Force line breaks at specific points in your text:

```bash
# Basic newline usage
echo "First line#NL#Second line#NL#Third line" | boxy

# Mixed with other content
echo "Header text#NL#Body content continues here" | boxy --width 30

# Works in all modes
echo "Line 1#NL#Line 2" | boxy --width 15 --wrap
echo "Line 1#NL#Line 2" | boxy --width 15
echo "Line 1#NL#Line 2" | boxy
```

#### `#W#` - Wrap Hints
Preferred wrap points (only used when line exceeds width):

```bash
# Wrap hints guide intelligent breaking
echo "Download#W#complete#W#successfully" | boxy --width 15 --wrap

# If the line fits, hints are ignored
echo "Short#W#text" | boxy --width 20 --wrap  # No wrapping needed

# Multiple hints provide options
echo "Very#W#long#W#message#W#with#W#many#W#options" | boxy --width 12 --wrap
```

#### `#T#` - Ellipsis + Wrap Hints
Combination of truncation and wrap markers:

```bash
# Prefer wrapping, but truncate if needed
echo "First#T#second#T#third#T#fourth" | boxy --width 10 --wrap

# In truncation mode, acts like ellipsis point
echo "Beginning#T#middle#T#end" | boxy --width 15
```

### Intelligent Word Boundary Detection

When wrap hints are unavailable or in wrong positions, boxy uses lookahead algorithms to find optimal word boundaries:

```bash
# Smart boundary detection
echo "supercalifragilisticexpialidocious wonderful" | boxy --width 20 --wrap

# Handles complex cases
echo "URL: https://example.com/very/long/path continues here" | boxy --width 25 --wrap

# Mixed content with punctuation
echo "Error: file.txt not found! Please check the path." | boxy --width 18 --wrap
```

### Hint Validation and Fallbacks

Boxy validates hint positions and provides intelligent fallbacks:

```bash
# Hints in good positions - used as-is
echo "Perfect#W#placement#W#here" | boxy --width 15 --wrap

# Hints in wrong positions - falls back to word boundaries
echo "Wrongplacement#W#he#W#re" | boxy --width 15 --wrap

# No unnecessary ellipsis when words fit naturally
echo "Short text" | boxy --width 20 --wrap  # No truncation applied
```

### Advanced Examples

```bash
# Complex document formatting
echo "TITLE#NL#This is the body content that will wrap#W#nicely at appropriate#W#word boundaries for readability." | boxy --width 30 --wrap

# Mixed markers
echo "Header#NL#First paragraph with#W#wrap hints#NL#Second paragraph#T#with ellipsis hints" | boxy --width 25 --wrap

# Pipeline with wrapping
cat long_file.txt | boxy --title "📄 Document" --width 40 --wrap

# Status updates with controlled breaks
echo "Processing file 1#NL#Processing file 2#NL#Processing file 3#NL#✅ All complete!" | boxy --theme success
```

### Wrapping Behavior Summary

| Mode | Flag Combination | Behavior |
|------|------------------|----------|
| Auto-width | (no `--width`) or `--width auto` | Wraps at terminal width, removes hints |
| Auto-width | `--width max` | Uses full terminal width, removes hints |
| Fixed + Wrap | `--width N --wrap` | Hint-aware wrapping with word boundaries |
| Fixed + Truncate | `--width N` (no `--wrap`) | Truncates with ellipsis |

**Key Points**:
- `#NL#` markers work in ALL modes and are always processed
- Wrap hints (`#W#`, `#T#`) are only processed in fixed-width + wrap mode
- Auto-width mode removes hint markers from output
- Intelligent word boundary detection provides fallbacks when hints aren't optimal
- No unnecessary ellipsis when content fits naturally

## Box Styles

- `normal` - Standard box drawing characters `┌─┐│└┘`
- `rounded` - Rounded corners `╭─╮│╰╯`
- `double` - Double lines `╔═╗║╚╝`
- `heavy` - Heavy lines `┏━┓┃┗┛`
- `ascii` - ASCII compatible `+-+|++`

## Colors & Text Styling

### Available Colors (90+ Palette)

**Legacy Colors (v0.5.0):**
- `red`, `red2`, `deep`, `deep_green`, `orange`, `yellow`
- `green`, `green2`, `blue`, `blue2`, `cyan`, `magenta`
- `purple`, `purple2`, `white`, `white2`, `grey`, `grey2`, `grey3`

**Rich Color Spectrum:**

*Red Spectrum:* `crimson`, `ruby`, `coral`, `salmon`, `rose`, `brick`

*Orange Spectrum:* `amber`, `tangerine`, `peach`, `rust`, `bronze`, `gold`

*Yellow Spectrum:* `lemon`, `mustard`, `sand`, `cream`, `khaki`

*Green Spectrum:* `lime`, `emerald`, `forest`, `mint`, `sage`, `jade`, `olive`

*Blue Spectrum:* `azure`, `navy`, `royal`, `ice`, `steel`, `teal`, `indigo`

*Purple Spectrum:* `violet`, `plum`, `lavender`, `orchid`, `mauve`, `amethyst`

*Cyan Spectrum:* `aqua`, `turquoise`, `sky`, `ocean`

*Monochrome:* `black`, `charcoal`, `slate`, `silver`, `pearl`, `snow`

**Semantic Colors:**

*Alerts:* `error`, `warning`, `danger`, `alert`

*Success:* `success`, `complete`, `verified`, `approved`

*Info:* `info`, `note`, `hint`, `debug`

*States:* `pending`, `progress`, `blocked`, `queued`, `active`, `inactive`

*Priority:* `critical`, `high`, `medium`, `low`, `trivial`

**Preview All Colors:**
```bash
boxy --colors  # Shows complete color palette with visual preview
```

### Text Colors (`--text`)
- Use any color from the list above: `--text red`, `--text blue2`
- Use `auto` to match box color: `--text auto`
- Omit flag for default terminal text color

## Jynx Integration

Boxy integrates with the Jynx color system for enhanced terminal compatibility and color management:

### Color System Integration
- **Automatic Detection**: Boxy automatically detects and uses Jynx when available
- **Terminal Compatibility**: Respects terminal color capabilities through Jynx
- **Fallback Support**: Gracefully degrades when Jynx is unavailable

### Control Options
```bash
# Disable Jynx integration and all color output
echo "content" | boxy --no-color

# Standard usage (Jynx auto-detected)
echo "content" | boxy --color blue
```

### Environment Integration
Jynx integration provides:
- Intelligent terminal capability detection
- Color palette optimization for different terminal types
- Consistent color rendering across terminal emulators
- Automatic fallback for unsupported terminals

### Themes
Predefined combinations of icon, color, and styling:
```bash
--theme error      # ❌ with red styling
--theme success    # ✅ with green styling
--theme warning    # ⚠️ with orange styling
--theme info       # ℹ️ with blue styling
--theme debug      # 🐛 with dark green styling
--theme blueprint  # 📐 with technical blue ASCII styling
--theme critical   # ⛔ with double border critical styling
# ... and many more
```

## Theme Hierarchy System

Boxy uses a **5-level theme hierarchy** that searches for themes in the following priority order:

### 1. Local boxy files (highest priority)
- Files like `boxy*.yaml` or `boxy*.yml` in the current directory
- Alphabetically first file is selected if multiple exist
- Example: `boxy_alpha.yaml`, `boxy_custom.yml`

### 2. Local .themes directory
- Hidden `.themes/` directory in current working directory
- Contains project-specific themes
- Example: `.themes/my_project_theme.yml`

### 3. Local themes directory
- Public `themes/` directory in current working directory
- Shared themes for the project
- Example: `themes/default.yml`, `themes/custom.yml`

### 4. XDG themes directory
- System-wide themes in XDG config location
- Path: `~/.local/etc/rsb/boxy/themes/`
- Global user themes

### 5. Built-in themes (lowest priority)
- Compiled fallback themes
- Always available as last resort

### Theme Management Commands

**Basic Operations:**
```bash
# View the theme loading hierarchy
boxy theme hierarchy

# List all available themes from all levels
boxy theme list

# Show details for a specific theme
boxy theme show success

# Test a theme with sample content before using
boxy theme dryrun error
```

**Advanced Theme Management:**
```bash
# Interactive theme creation
boxy theme create my_theme        # Create new theme interactively

# Theme import/export
boxy theme export success > my_theme.yml  # Export theme to YAML
boxy theme import my_theme.yml             # Import theme from YAML

# Theme editing
boxy theme edit my_theme          # Edit existing theme in editor
```

**Environment Variables:**
```bash
# Set default theme (overridden by --theme)
export BOXY_THEME=success
echo "content" | boxy             # Uses success theme by default
```

### Creating Custom Themes

You can create themes at any level of the hierarchy:

```yaml
# Example: ./themes/my_theme.yml
themes:
  my_custom:
    color: "blue"
    text_color: "white"
    style: "rounded"
    text_style: "bold"
    title: "🎯 Custom"
```

Then use with: `echo "Hello" | boxy --theme my_custom`

## Environment Variables

Boxy supports several environment variables for configuration and debugging:

### Theme Configuration
```bash
# Set default theme (overridden by --theme flag)
export BOXY_THEME=success
echo "Deployment complete" | boxy  # Uses success theme
```

### Layout Configuration
```bash
# Set minimum box width (default: 5)
export BOXY_MIN_WIDTH=20
echo "Short" | boxy  # Box will be at least 20 characters wide
```

### Advanced Configuration
```bash
# Enable multiplex mode features
export BOXY_MULTIPLEX_MODE=enabled

# Use custom width calculation fallback (instead of unicode-width crate)
export BOXY_USE_CUSTOM_WIDTH=1
```

### Variable Expansion
Boxy supports variable expansion in text content using `$VAR` syntax:

```bash
# Variables available for expansion
export USER=developer
echo "Welcome $USER to the system" | boxy --title "Greeting"
# Output: "Welcome developer to the system"

# Built-in variables
echo "Home: $HOME" | boxy
echo "User: $USER" | boxy
```

### Configuration Paths
```bash
# Theme hierarchy uses standard paths
# ~/.local/etc/rsb/boxy/themes/    (XDG themes directory)
# ./themes/                       (Local themes directory)
# ./.themes/                      (Hidden local themes)
# ./boxy*.yaml                    (Local boxy files)
```

## Examples

```bash
# System info box with title  
echo -e "🦀 Rust powered\n⚡ Lightning fast\n🔒 Memory safe" | boxy --title "📦 boxy v0.11.0" -s rounded -c blue

# Error alert with themed styling and auto text color
echo "File not found: config.json" | boxy --theme error --text auto --title "🚨 Error"

# Status dashboard with custom text colors
echo -e "✅ Tests passing\n🔧 Build complete\n📦 Ready to deploy" | boxy --title "🎯 CI/CD Status" --footer "✅ All systems go" -c green --text white

# Mixed styling approach
echo "Deploy to production?" | boxy --theme warning --text auto --width 25

# Interactive menu with controlled line breaks
echo "1. Deploy to staging#NL#2. Deploy to production#NL#3. Rollback#NL#4. Exit" | boxy --title "🚀 Deployment Menu" -s rounded

# Long text with intelligent wrapping
echo "Processing large dataset with#W#multiple stages including#W#data validation and#W#transformation steps" | boxy --width 25 --wrap --theme info

# Theme management and testing
boxy theme hierarchy                           # View theme loading priority
boxy theme dryrun success                     # Test theme before using
echo "Task completed" | boxy --theme success  # Apply the tested theme

# Pipeline processing
command_output | boxy --title "📋 Results" | tee results.txt
cat results.txt | boxy --no-boxy | grep "ERROR"
```

## Integration with Bash

Add to your `.bashrc` or script:

```bash
box() {
    echo "$1" | $HOME/.local/bin/odx/boxy "$@"
}

# Usage examples
box "Hello World" -s rounded -c blue --text auto
box "Deploy complete" --theme success --text auto
box "Error occurred" --theme error --width 30
box "Long message with#W#intelligent wrapping" --width 20 --wrap
```

## Advanced Features

### Text Wrapping and Line Control
- **Three wrapping modes**: auto-width (default), fixed-width with wrapping, fixed-width with truncation
- **Explicit line breaks**: `#NL#` markers for precise line control
- **Intelligent wrap hints**: `#W#` and `#T#` markers for optimal text flow
- **Smart word boundaries**: Lookahead algorithm for natural line breaks
- **Hint validation**: Automatic fallback to optimal positions when hints are poorly placed

### Title and Footer
- Support emoji and environment variable expansion
- Auto-truncation with `...` when too long
- Centered alignment within box

### Icon Decoration
- Adds visual flair to first content line
- Supports emoji and colored characters
- Suppresses theme icon automatically when title begins with an emoji

### Pipeline Integration
- `--no-boxy`: Strip box while preserving colors/formatting
- `--no-boxy=strict`: Pure ASCII output for script processing
- Perfect for command chains and text processing

### Param Stream (--params)
- Keys: `hd` (header), `tl` (title), `st` (status), `ft` (footer), `ic` (icon), `tc` (title color), `sc` (status color), `ly` (layout tokens)
- Body is always taken from stdin; params only set metadata

### Default Theme
- Set `BOXY_THEME` to a valid theme name to apply by default (overridden by `--theme`)

## Why boxy?

Unlike bash-based box drawing tools, boxy correctly handles:
- **Unicode-width crate emoji calculation** (🚀 = 2 columns) with custom fallback
- **Intelligent text wrapping** with explicit markers and smart word boundaries
- **Multiple wrapping modes** for different use cases (auto, fixed+wrap, fixed+truncate)
- Unicode variation selectors (ℹ️ vs ℹ)
- Zero-width joiners and modifiers
- CJK characters (中文, 日本語, 한국어)
- Mixed ASCII and Unicode content
- ANSI color preservation in pipeline modes
- **Comprehensive emoji debugging** for development and troubleshooting

### Width Calculation System
Boxy uses the unicode-width crate as its primary width calculation engine, providing:
- Accurate emoji width detection with proper Unicode handling
- Better handling of complex Unicode sequences and grapheme clusters
- Protected macro system preventing width calculation regressions
- Custom fallback implementation available via BOXY_USE_CUSTOM_WIDTH=1
- ANSI escape sequence stripping for proper terminal color support
- Custom debugging capabilities for width issues

#### Protected Width Macros
Three protected macros ensure stable width calculations:
- `box_width!` - Main box width calculation (src/draw.rs)
- `max_width!` - Content maximum width calculation (src/components.rs)
- `inner_target_width!` - Inner content target width calculation (src/components.rs)

These macros abstract the width calculation implementation and prevent regressions.

## Known Issues & Solutions

### Emoji & Unicode Alignment Issues

During development, several critical alignment and width calculation issues were identified and resolved. If you encounter similar problems when working with emoji or Unicode content, these solutions may help:

#### 1. **ANSI Color Code Width Issue**
**Problem**: ANSI escape sequences (color codes) were being counted in width calculations, causing misaligned boxes.

**Solution**: Strip ANSI codes before width calculation using the `strip_ansi_escapes` function. Width calculations should only consider visible characters.

```rust
// Before width calculation, strip ANSI codes
let clean_text = strip_ansi_escapes(&text);
let width = calculate_width(&clean_text);
```

#### 2. **Emoji Truncation Issue**
**Problem**: Multi-codepoint emoji (like ℹ️ - information symbol with variation selector) were being split during text truncation, breaking visual alignment and rendering.

**Solution**: Handle emoji as complete grapheme clusters during truncation operations. Never split emoji in the middle of their codepoint sequence.

```rust
// Use grapheme-aware truncation
use unicode_segmentation::UnicodeSegmentation;
let graphemes: Vec<&str> = text.graphemes(true).collect();
// Truncate by grapheme clusters, not bytes or chars
```

#### 3. **Mixed Width Padding Issue**
**Problem**: Lines containing different emoji and symbol widths weren't getting consistent padding, resulting in ragged box edges.

**Solution**:
- Use unicode-width library for accurate emoji width detection
- Calculate the maximum content width across all lines
- Pad all lines to this maximum width for uniform alignment
- Account for emoji width (typically 2 columns) vs ASCII (1 column)

```rust
// Calculate max width across all content lines
let max_width = content_lines.iter()
    .map(|line| unicode_width::UnicodeWidthStr::width(&strip_ansi_escapes(line)))
    .max()
    .unwrap_or(0);

// Pad each line to max_width for uniform alignment
```

#### 4. **Complex Unicode Sequence Handling**
**Problem**: Unicode sequences with variation selectors, zero-width joiners, and modifiers weren't handled consistently.

**Solution**:
- Process text as grapheme clusters rather than individual codepoints
- Use proper Unicode normalization
- Test with complex emoji sequences during development

#### Development Tips
- Always test with mixed emoji and ASCII content
- Use the built-in `emoji_debug` binary to analyze problematic characters
- Verify alignment with sequences like `"✅ Success"` and `"ℹ️ Info"`
- Check that ANSI color codes don't affect width calculations

## Terminal Width Diagnostics

Boxy includes a built-in width utility for troubleshooting layout issues and verifying terminal capabilities:

### Width Command
```bash
# Show comprehensive terminal width information
boxy width
```

### Information Provided
- **Terminal Dimensions**: Current terminal width and height
- **Display Width Test**: Verification of width calculation accuracy
- **Character Width Testing**: Test how specific characters are measured
- **Layout Diagnostics**: Information for troubleshooting box sizing issues

### Use Cases
- **Layout Troubleshooting**: When boxes appear too wide or narrow
- **Terminal Compatibility**: Verify width detection across different terminals
- **CI/CD Integration**: Ensure consistent layout in automated environments
- **Multi-platform Testing**: Validate behavior across operating systems

### Example Output
The width command provides detailed information about:
- Detected terminal width vs actual usable width
- Character width calculation methods
- Terminal capability flags
- Recommendations for optimal box sizing

## Emoji Debugging System

For developers working with Unicode and emoji, boxy includes comprehensive debugging tools:

### Built-in Emoji Debug Binary
```bash
# Debug a single emoji or character
cargo run --bin emoji_debug "✅"
cargo run --bin emoji_debug "ℹ️"

# Compare multiple characters side by side
cargo run --bin emoji_debug compare "✅" "ℹ️" "🚀" "X"
```

### Debug Information Provided
- Character width calculations
- Unicode codepoint breakdowns
- Visual alignment testing
- Grapheme cluster analysis
- Comparison utilities for troubleshooting

This debugging system is invaluable when working with complex Unicode sequences or when boxy's width calculations don't match expectations.

## License

RSB Framework, Oxidex (ODX), and REBEL libraries, services, and software are offered under a **multi-license model**:

| License | Who it’s for | Obligations |
|---------|--------------|-------------|
| [AGPL-3.0](./LICENSE) | Open-source projects that agree to release their own source code under the AGPL. | Must comply with the AGPL for any distribution or network service. |
| [Community Edition License](./docs/LICENSE_COMMUNITY.txt) | Personal, educational, or academic use **only**. Not for companies, organizations, or anyone acting for the benefit of a business. | Must meet all CE eligibility requirements and follow its terms. |
| [Commercial License](./docs/LICENSE_COMMERCIAL.txt) | Companies, contractors, or anyone needing to embed the software in closed-source, SaaS, or other commercial products. | Requires a signed commercial agreement with Dr. Vegajunk Hackware. |

By **downloading, installing, linking to, or otherwise using RSB Framework, Oxidex, or REBEL libraries, services, and software**, you:

1. **Accept** the terms of one of the licenses above, **and**  
2. **Represent that you meet all eligibility requirements** for the license you have chosen.

> Questions about eligibility or commercial licensing: **licensing@vegajunk.com**
