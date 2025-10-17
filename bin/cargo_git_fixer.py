#!/usr/bin/env python3
"""
Cargo Git Config Fixer - Ensures proper setup for private git dependencies

Checks and fixes:
1. ~/.cargo/config.toml has git-fetch-with-cli = true
2. Detects git auth failures in dependencies
3. Suggests SSH config improvements
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import subprocess

try:
    import tomllib
    def load_toml(file_path):
        with open(file_path, 'rb') as f:
            return tomllib.load(f)
except ImportError:
    import toml
    def load_toml(file_path):
        return toml.load(file_path)

class CargoGitFixer:
    def __init__(self):
        self.cargo_config_path = Path.home() / ".cargo" / "config.toml"
        self.cargo_config_dir = Path.home() / ".cargo"

    def check_cargo_config(self) -> Tuple[bool, Optional[str]]:
        """Check if cargo config has git-fetch-with-cli enabled"""
        if not self.cargo_config_path.exists():
            return False, "~/.cargo/config.toml does not exist"

        try:
            config = load_toml(self.cargo_config_path)
            net_section = config.get('net', {})

            if net_section.get('git-fetch-with-cli') == True:
                return True, None
            else:
                return False, "git-fetch-with-cli is not enabled in [net] section"
        except Exception as e:
            return False, f"Error reading config: {e}"

    def fix_cargo_config(self, dry_run: bool = False) -> bool:
        """Add git-fetch-with-cli to cargo config without clobbering"""
        try:
            # Ensure .cargo directory exists
            self.cargo_config_dir.mkdir(parents=True, exist_ok=True)

            # Read existing config if it exists
            existing_config = ""
            if self.cargo_config_path.exists():
                with open(self.cargo_config_path, 'r') as f:
                    existing_config = f.read()

            # Check if [net] section exists
            has_net_section = '[net]' in existing_config
            has_git_fetch = 'git-fetch-with-cli' in existing_config

            if has_git_fetch:
                print("✓ git-fetch-with-cli already configured")
                return True

            # Build new config content
            if dry_run:
                print("\n📋 Would add to ~/.cargo/config.toml:")
                print("=" * 50)

            if not has_net_section:
                # Add entire [net] section
                addition = "\n[net]\ngit-fetch-with-cli = true\n"
                if dry_run:
                    print(addition)
                else:
                    with open(self.cargo_config_path, 'a') as f:
                        f.write(addition)
                    print(f"✓ Added [net] section with git-fetch-with-cli = true")
            else:
                # Add just the setting to existing [net] section
                lines = existing_config.split('\n')
                new_lines = []
                in_net_section = False
                added = False

                for line in lines:
                    new_lines.append(line)
                    if line.strip() == '[net]':
                        in_net_section = True
                    elif in_net_section and line.strip().startswith('['):
                        # Reached next section, add before it
                        if not added:
                            new_lines.insert(-1, 'git-fetch-with-cli = true')
                            added = True
                        in_net_section = False
                    elif in_net_section and not line.strip():
                        # Empty line in [net] section, add before it
                        if not added:
                            new_lines.insert(-1, 'git-fetch-with-cli = true')
                            added = True

                # If still not added, add at end of [net] section
                if in_net_section and not added:
                    new_lines.append('git-fetch-with-cli = true')

                new_config = '\n'.join(new_lines)

                if dry_run:
                    # Show diff
                    print("git-fetch-with-cli = true  (in [net] section)")
                else:
                    with open(self.cargo_config_path, 'w') as f:
                        f.write(new_config)
                    print(f"✓ Added git-fetch-with-cli = true to [net] section")

            if dry_run:
                print("=" * 50)
                print("\n⚠️  Dry run mode - no changes made")
            else:
                print(f"\n✅ Cargo config updated: {self.cargo_config_path}")
                print("   Git dependencies will now use system git with SSH auth")

            return True

        except Exception as e:
            print(f"❌ Error fixing cargo config: {e}")
            return False

    def check_ssh_config(self) -> Dict[str, List[str]]:
        """Parse SSH config to find host mappings"""
        ssh_config_path = Path.home() / ".ssh" / "config"
        host_mappings = {}  # hostname -> [aliases]

        if not ssh_config_path.exists():
            return host_mappings

        try:
            with open(ssh_config_path, 'r') as f:
                current_host = None
                current_hostname = None

                for line in f:
                    line = line.strip()

                    # Parse Host directive
                    if line.lower().startswith('host '):
                        hosts = line[5:].strip().split()
                        current_host = hosts
                        current_hostname = None

                    # Parse HostName directive
                    elif line.lower().startswith('hostname '):
                        current_hostname = line[9:].strip()

                        # Store mapping
                        if current_host and current_hostname:
                            if current_hostname not in host_mappings:
                                host_mappings[current_hostname] = []
                            host_mappings[current_hostname].extend(current_host)

            return host_mappings
        except Exception as e:
            print(f"⚠️  Could not read SSH config: {e}")
            return host_mappings

    def suggest_ssh_profile(self, git_url: str) -> Optional[str]:
        """Suggest SSH profile for a git URL based on SSH config"""
        host_mappings = self.check_ssh_config()

        # Extract hostname from git URL
        hostname = None
        if 'gitlab.com' in git_url:
            hostname = 'gitlab.com'
        elif 'github.com' in git_url:
            hostname = 'github.com'
        elif git_url.startswith('ssh://git@'):
            # Extract from ssh://git@hostname/...
            hostname = git_url.split('ssh://git@')[1].split('/')[0]
        elif git_url.startswith('git@'):
            # Extract from git@hostname:...
            hostname = git_url.split('git@')[1].split(':')[0]

        if hostname and hostname in host_mappings:
            aliases = host_mappings[hostname]
            # Return first non-hostname alias (custom profile)
            for alias in aliases:
                if alias != hostname:
                    return alias

        return None

    def test_git_access(self, git_url: str) -> Tuple[bool, str]:
        """Test if git repository is accessible"""
        try:
            # Try git ls-remote to test access
            result = subprocess.run(
                ['git', 'ls-remote', '--heads', git_url],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, "accessible"
            else:
                error_msg = result.stderr.lower()
                if 'permission denied' in error_msg or 'authentication failed' in error_msg:
                    return False, "auth_required"
                elif 'not found' in error_msg or 'could not read' in error_msg:
                    return False, "not_found"
                else:
                    return False, f"error: {result.stderr[:100]}"
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except Exception as e:
            return False, f"error: {str(e)}"

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fix cargo config for private git dependencies')
    parser.add_argument('--check', action='store_true', help='Check current config status')
    parser.add_argument('--fix', action='store_true', help='Fix cargo config')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--test-url', type=str, help='Test access to a git URL')

    args = parser.parse_args()

    fixer = CargoGitFixer()

    if args.test_url:
        print(f"Testing access to: {args.test_url}")
        accessible, status = fixer.test_git_access(args.test_url)
        if accessible:
            print(f"✓ Repository is accessible")
        else:
            print(f"✗ Repository not accessible: {status}")

            # Suggest SSH profile if available
            profile = fixer.suggest_ssh_profile(args.test_url)
            if profile:
                print(f"\n💡 Try using SSH profile: {profile}")
                print(f"   Your SSH config has this profile configured for this host")

    elif args.check:
        print("🔍 Checking cargo git configuration...")
        is_ok, message = fixer.check_cargo_config()

        if is_ok:
            print("✅ Cargo is properly configured for private git dependencies")
            print(f"   git-fetch-with-cli = true is set in {fixer.cargo_config_path}")
        else:
            print(f"⚠️  Configuration issue: {message}")
            print(f"\n💡 Run with --fix to automatically fix this")

    elif args.fix or args.dry_run:
        print("🔧 Fixing cargo git configuration...")
        success = fixer.fix_cargo_config(dry_run=args.dry_run)

        if success and not args.dry_run:
            print("\n📚 Next steps:")
            print("1. Restart any running cargo processes")
            print("2. Ensure your SSH keys are added to ssh-agent")
            print("3. Verify SSH config has entries for your git hosts")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
