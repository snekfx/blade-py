#!/usr/bin/env python3
"""
Walker - Repository discovery and analysis tool
Walks filesystem to find git projects and determines their type, language, and structure.

Usage:
  python walker.py             # Scan from current directory
  python walker.py --root PATH # Scan from specific root
  python walker.py --update    # Update existing repo data
  python walker.py --stats     # Show repository statistics

Purpose:
  General-purpose repository surveyor across all languages and ecosystems.
  Provides structured metadata about discovered repos for other tools to consume.
"""

import os
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set
from datetime import datetime
import argparse

@dataclass
class Repository:
    """Repository metadata"""
    path: str
    name: str
    languages: List[str]
    primary_language: str
    manifest_files: List[str]
    key_scripts: Dict[str, bool]  # Track build.sh, test.sh, deploy.sh
    has_readme: bool  # Track if README exists
    remote_url: Optional[str]
    branch: Optional[str]
    last_commit: Optional[str]
    discovered_at: str

class RepoDiscovery:
    """Repository discovery and classification system"""

    LANGUAGE_MARKERS = {
        'rust': ['Cargo.toml'],
        'python': ['pyproject.toml', 'setup.py', 'requirements.txt', 'Pipfile'],
        'nodejs': ['package.json'],
        'typescript': ['tsconfig.json', 'package.json'],
        'go': ['go.mod'],
        'java': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
        'csharp': ['.csproj', '.sln'],
        'ruby': ['Gemfile'],
        'php': ['composer.json'],
        'elixir': ['mix.exs'],
        'bash': ['build.map', 'parts/', 'build.sh', 'bin/build.sh'],
        'docker': ['Dockerfile', 'docker-compose.yml'],
        'kubernetes': ['k8s.yaml', 'deployment.yaml'],
        'terraform': ['main.tf', '*.tf'],
        'ansible': ['playbook.yml', 'ansible.cfg'],
        'docs': ['README.md', 'DOCS.md', 'index.md'],  # Primary doc indicators
    }

    # BashFX specific patterns
    BASHFX_MARKERS = {
        'build.map': 'BashFX build map',
        'parts/': 'BashFX parts directory',
        'build.sh': 'BashFX build script',
        'bin/build.sh': 'BashFX build script in bin'
    }

    # Key bash scripts to track
    BASH_KEY_SCRIPTS = ['test.sh', 'deploy.sh', 'install.sh', 'setup.sh']

    # Path hints for language detection
    PATH_LANGUAGE_HINTS = {
        'shell/bashfx': 'bash',
        'code/rust': 'rust',
        'code/python': 'python',
        'code/shell': 'bash',
        'code/nodejs': 'nodejs',
    }

    IGNORE_DIRS = {
        'node_modules', 'target', 'dist', 'build', '__pycache__',
        '.git', '.svn', 'vendor', 'venv', '.venv', 'env',
        'site-packages', '.idea', '.vscode', 'coverage',
        '.pytest_cache', '.mypy_cache', 'htmlcov'
    }

    def __init__(self, root_path: Path = None):
        self.root_path = root_path or Path.home() / 'repos'
        self.data_dir = self.get_data_directory()
        self.data_file = self.data_dir / 'repositories.json'
        self.ensure_data_directory()

    def get_data_directory(self) -> Path:
        """Get XDG-compliant data directory"""
        xdg_data = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))
        return Path(xdg_data) / 'blade'

    def ensure_data_directory(self):
        """Ensure data directory exists"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def find_git_repos(self, start_path: Path) -> List[Path]:
        """Find all git repositories under start_path"""
        git_repos = []

        def should_skip(path: Path) -> bool:
            """Check if directory should be skipped"""
            return path.name in self.IGNORE_DIRS or path.name.startswith('.')

        def is_git_repo(path: Path) -> bool:
            """Check if path is a git repository"""
            git_dir = path / '.git'
            return git_dir.exists() and git_dir.is_dir()

        for root, dirs, _ in os.walk(start_path):
            root_path = Path(root)

            # Skip ignored directories
            dirs[:] = [d for d in dirs if not should_skip(Path(root) / d)]

            # Check if current directory is a git repo
            if is_git_repo(root_path):
                git_repos.append(root_path)
                # Don't traverse into git repos
                dirs.clear()

        return git_repos

    def detect_languages(self, repo_path: Path) -> tuple[List[str], List[str], Dict[str, bool]]:
        """Detect languages used in repository based on manifest files and path hints"""
        detected_languages = []
        found_manifests = []

        # Check for path-based language hints
        repo_str = str(repo_path)
        for path_hint, language in self.PATH_LANGUAGE_HINTS.items():
            if path_hint in repo_str:
                detected_languages.append(language)
                found_manifests.append(f"[path hint: {path_hint}]")

        for language, markers in self.LANGUAGE_MARKERS.items():
            for marker in markers:
                if marker.endswith('/'):
                    # Handle directory markers
                    if (repo_path / marker.rstrip('/')).is_dir():
                        detected_languages.append(language)
                        found_manifests.append(marker)
                        if language == 'bash':
                            # Check for other BashFX markers
                            for bashfx_marker in self.BASHFX_MARKERS:
                                if bashfx_marker.endswith('/'):
                                    if (repo_path / bashfx_marker.rstrip('/')).is_dir():
                                        found_manifests.append(f"{bashfx_marker} (BashFX)")
                                else:
                                    if (repo_path / bashfx_marker).exists():
                                        found_manifests.append(f"{bashfx_marker} (BashFX)")
                        break
                elif marker.endswith('*'):
                    # Handle wildcards
                    pattern = marker.replace('*', '')
                    matching_files = list(repo_path.glob(f'*{pattern}'))
                    if matching_files:
                        detected_languages.append(language)
                        found_manifests.extend([f.name for f in matching_files])
                else:
                    # Direct file check
                    if (repo_path / marker).exists():
                        detected_languages.append(language)
                        found_manifests.append(marker)
                        break

        # Track key scripts (build.sh, test.sh, deploy.sh)
        key_scripts = {
            'build.sh': False,
            'test.sh': False,
            'deploy.sh': False
        }

        # Check for these key scripts in root and bin/
        for script_name in key_scripts.keys():
            if (repo_path / script_name).exists():
                key_scripts[script_name] = True
            elif (repo_path / 'bin' / script_name).exists():
                key_scripts[script_name] = True

        # If no language detected, check for bash scripts as fallback
        if not detected_languages:
            # Check for key bash scripts
            bash_scripts = []
            for script in self.BASH_KEY_SCRIPTS:
                if (repo_path / script).exists():
                    bash_scripts.append(script)
                if (repo_path / 'bin' / script).exists():
                    bash_scripts.append(f'bin/{script}')

            # Check for .sh files in root
            sh_files = list(repo_path.glob('*.sh'))

            # If we found bash indicators, mark as bash
            if bash_scripts or sh_files:
                detected_languages.append('bash')
                found_manifests.extend(bash_scripts)
                if sh_files:
                    found_manifests.append(f"{len(sh_files)} .sh files")

        # Check for README (important for code repos)
        readme_patterns = ['README.md', 'README.txt', 'README.rst', 'README']
        has_readme = any((repo_path / pattern).exists() for pattern in readme_patterns)

        # If still no language detected, check if it's a documentation-only repo
        if not detected_languages:
            # Count markdown and text files
            md_files = list(repo_path.glob('*.md')) + list(repo_path.glob('**/*.md'))
            txt_files = list(repo_path.glob('*.txt')) + list(repo_path.glob('**/*.txt'))

            # Only mark as docs if it has substantial documentation AND no code
            if (len(md_files) + len(txt_files)) >= 3:  # At least 3 doc files
                # Double-check it's not a code repo with docs
                has_code = False
                code_extensions = ['.py', '.js', '.rs', '.go', '.java', '.c', '.cpp', '.rb', '.sh']
                for ext in code_extensions:
                    if list(repo_path.glob(f'*{ext}')) or list(repo_path.glob(f'**/*{ext}')):
                        has_code = True
                        break

                # Only classify as docs if no code files found
                if not has_code:
                    detected_languages.append('docs')
                    found_manifests.append(f"{len(md_files)} .md, {len(txt_files)} .txt files")

        # Remove duplicates while preserving order
        detected_languages = list(dict.fromkeys(detected_languages))
        found_manifests = list(dict.fromkeys(found_manifests))

        return detected_languages, found_manifests, key_scripts, has_readme

    def get_primary_language(self, languages: List[str]) -> str:
        """Determine primary language based on priority and presence"""
        if not languages:
            return 'unknown'

        # Priority order for primary language (code before docs)
        priority = ['rust', 'python', 'nodejs', 'typescript', 'go', 'java', 'bash', 'docs']

        for lang in priority:
            if lang in languages:
                return lang

        return languages[0]

    def get_git_info(self, repo_path: Path) -> Dict[str, Optional[str]]:
        """Get git repository information"""
        info = {'remote_url': None, 'branch': None, 'last_commit': None}

        try:
            # Get remote URL
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                info['remote_url'] = result.stdout.strip()

            # Get current branch
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                info['branch'] = result.stdout.strip()

            # Get last commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                info['last_commit'] = result.stdout.strip()[:8]

        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return info

    def analyze_repository(self, repo_path: Path) -> Repository:
        """Analyze a single repository"""
        languages, manifests, key_scripts, has_readme = self.detect_languages(repo_path)
        primary_language = self.get_primary_language(languages)
        git_info = self.get_git_info(repo_path)

        return Repository(
            path=str(repo_path),
            name=repo_path.name,
            languages=languages,
            primary_language=primary_language,
            manifest_files=manifests,
            key_scripts=key_scripts,
            has_readme=has_readme,
            remote_url=git_info['remote_url'],
            branch=git_info['branch'],
            last_commit=git_info['last_commit'],
            discovered_at=datetime.now().isoformat()
        )

    def scan(self, update: bool = False) -> List[Repository]:
        """Scan for repositories"""
        print(f"🔍 Scanning for repositories under: {self.root_path}")

        # Load existing data if updating
        existing_repos = {}
        if update and self.data_file.exists():
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                existing_repos = {r['path']: r for r in data.get('repositories', [])}

        # Find all git repositories
        git_repos = self.find_git_repos(self.root_path)
        print(f"📦 Found {len(git_repos)} git repositories")

        # Analyze each repository
        repositories = []
        for repo_path in git_repos:
            print(f"  Analyzing: {repo_path.name}...", end='')

            # Check if we should update or reuse existing data
            if update and str(repo_path) in existing_repos:
                repo_data = existing_repos[str(repo_path)]
                # Update git info only
                git_info = self.get_git_info(repo_path)
                repo_data.update(git_info)
                repo = Repository(**repo_data)
            else:
                repo = self.analyze_repository(repo_path)

            repositories.append(repo)

            # Display summary
            lang_str = f"{repo.primary_language}"
            if len(repo.languages) > 1:
                others = [l for l in repo.languages if l != repo.primary_language]
                lang_str += f" (+{','.join(others)})"
            print(f" [{lang_str}]")

        return repositories

    def save_repositories(self, repositories: List[Repository]):
        """Save repository data to file"""
        data = {
            'version': '1.0',
            'scan_date': datetime.now().isoformat(),
            'root_path': str(self.root_path),
            'total_repos': len(repositories),
            'repositories': [asdict(r) for r in repositories]
        }

        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n✅ Saved repository data to: {self.data_file}")

    def load_repositories(self) -> Optional[Dict]:
        """Load repository data from file"""
        if not self.data_file.exists():
            return None

        with open(self.data_file, 'r') as f:
            return json.load(f)

    def display_stats(self):
        """Display repository statistics"""
        data = self.load_repositories()
        if not data:
            print("❌ No repository data found. Run scan first.")
            return

        repos = data['repositories']

        # Calculate statistics
        language_counts = {}
        multi_language_count = 0

        for repo in repos:
            # Count primary languages
            primary = repo['primary_language']
            language_counts[primary] = language_counts.get(primary, 0) + 1

            # Count multi-language repos
            if len(repo['languages']) > 1:
                multi_language_count += 1

        # Display statistics
        print("\n📊 Repository Statistics")
        print("=" * 50)
        print(f"Total repositories: {len(repos)}")
        print(f"Scan date: {data['scan_date'][:19]}")
        print(f"Root path: {data['root_path']}")

        print("\n🔤 Languages Distribution:")
        for lang, count in sorted(language_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(repos)) * 100
            bar = '█' * int(percentage / 2)
            print(f"  {lang:12} {count:3} [{bar:25}] {percentage:.1f}%")

        print(f"\n🌐 Multi-language repos: {multi_language_count} ({multi_language_count/len(repos)*100:.1f}%)")

        # Find repos with most languages
        if multi_language_count > 0:
            sorted_repos = sorted(repos, key=lambda x: len(x['languages']), reverse=True)[:5]
            print("\n🏆 Most polyglot repositories:")
            for repo in sorted_repos:
                if len(repo['languages']) > 1:
                    print(f"  {repo['name']:30} {', '.join(repo['languages'])}")

        # Analyze key scripts distribution
        script_counts = {'build.sh': 0, 'test.sh': 0, 'deploy.sh': 0}
        for repo in repos:
            if 'key_scripts' in repo:
                for script, exists in repo['key_scripts'].items():
                    if exists:
                        script_counts[script] += 1

        if any(script_counts.values()):
            print("\n🔧 Key Scripts Distribution:")
            for script, count in script_counts.items():
                percentage = (count / len(repos)) * 100
                bar = '█' * int(percentage / 3)
                print(f"  {script:12} {count:3} [{bar:16}] {percentage:.1f}%")

        # Analyze README distribution (exclude docs-only repos)
        readme_count = 0
        code_repos = 0
        for repo in repos:
            if repo['primary_language'] != 'docs':
                code_repos += 1
                if repo.get('has_readme', False):
                    readme_count += 1

        if code_repos > 0:
            readme_percentage = (readme_count / code_repos) * 100
            missing_readmes = code_repos - readme_count
            print(f"\n📖 README Coverage (code repos only):")
            print(f"  Has README:    {readme_count:3}/{code_repos} ({readme_percentage:.1f}%)")
            print(f"  Missing README: {missing_readmes:3}/{code_repos} ({100-readme_percentage:.1f}%)")

    def export_by_language(self):
        """Export repository lists grouped by language"""
        data = self.load_repositories()
        if not data:
            print("❌ No repository data found. Run scan first.")
            return

        repos = data['repositories']

        # Group by language
        by_language = {}
        for repo in repos:
            for lang in repo['languages']:
                if lang not in by_language:
                    by_language[lang] = []
                by_language[lang].append({
                    'name': repo['name'],
                    'path': repo['path'],
                    'primary': lang == repo['primary_language']
                })

        # Save language-specific files
        for lang, lang_repos in by_language.items():
            output_file = self.data_dir / f'repos_{lang}.json'
            with open(output_file, 'w') as f:
                json.dump({
                    'language': lang,
                    'count': len(lang_repos),
                    'repositories': lang_repos
                }, f, indent=2)
            print(f"  Exported {lang}: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Repository discovery and classification tool')
    parser.add_argument('--root', type=str, help='Root directory to scan (default: ~/repos)')
    parser.add_argument('--update', action='store_true', help='Update existing repository data')
    parser.add_argument('--stats', action='store_true', help='Display repository statistics')
    parser.add_argument('--export', action='store_true', help='Export repositories by language')

    args = parser.parse_args()

    # Determine root path
    root_path = Path(args.root) if args.root else None
    discovery = RepoDiscovery(root_path)

    if args.stats:
        # Display statistics
        discovery.display_stats()
    elif args.export:
        # Export by language
        discovery.export_by_language()
        print("\n✅ Language-specific exports complete")
    else:
        # Perform scan
        repositories = discovery.scan(update=args.update)

        if repositories:
            discovery.save_repositories(repositories)

            # Display summary
            print("\n📋 Summary by Language:")
            lang_counts = {}
            for repo in repositories:
                lang_counts[repo.primary_language] = lang_counts.get(repo.primary_language, 0) + 1

            for lang, count in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {lang:12} {count:3} repositories")

if __name__ == "__main__":
    main()