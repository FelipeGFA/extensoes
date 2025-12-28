#!/usr/bin/env python3
"""
Analyze upstream commits for potential conflicts before cherry-picking.

This script analyzes commits from upstream (keiyoushi/extensions) to determine
if they can be safely cherry-picked, need APK replacement, or require manual intervention.

Exit codes:
0 - Safe to cherry-pick
1 - APK replacement needed
2 - Conflict detected, manual intervention required
3 - Error occurred
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CommitAnalyzer:
    """Analyzes commits for safe cherry-picking."""

    def __init__(self, commit_sha: str, repo_path: str = "."):
        self.commit_sha = commit_sha
        self.repo_path = Path(repo_path)
        self.apk_pattern = re.compile(r'(.+)-v(\d+\.\d+\.\d+)\.apk$')

    def run_git_command(self, cmd: List[str]) -> Tuple[int, str, str]:
        """Run a git command and return the result."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)

    def get_commit_files(self) -> List[str]:
        """Get list of files changed in the commit."""
        returncode, stdout, stderr = self.run_git_command([
            'git', 'diff-tree', '--no-commit-id', '--name-only', '-r', self.commit_sha
        ])
        
        if returncode != 0:
            print(f"ERROR: Failed to get commit files: {stderr}", file=sys.stderr)
            return []
        
        return [line.strip() for line in stdout.strip().split('\n') if line.strip()]

    def get_file_content(self, file_path: str, commit: str) -> Optional[str]:
        """Get content of a file at a specific commit."""
        returncode, stdout, stderr = self.run_git_command([
            'git', 'show', f'{commit}:{file_path}'
        ])
        
        if returncode != 0:
            return None
        
        return stdout

    def parse_apk_version(self, apk_name: str) -> Optional[Tuple[str, str]]:
        """Parse APK filename to extract base name and version."""
        match = self.apk_pattern.match(apk_name)
        if match:
            return match.group(1), match.group(2)
        return None

    def compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.
        Returns: -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        try:
            parts1 = [int(x) for x in v1.split('.')]
            parts2 = [int(x) for x in v2.split('.')]
            
            # Pad with zeros to make equal length
            max_len = max(len(parts1), len(parts2))
            parts1.extend([0] * (max_len - len(parts1)))
            parts2.extend([0] * (max_len - len(parts2)))
            
            for p1, p2 in zip(parts1, parts2):
                if p1 < p2:
                    return -1
                elif p1 > p2:
                    return 1
            return 0
        except (ValueError, AttributeError):
            return 0

    def get_current_apk_version(self, base_name: str) -> Optional[str]:
        """Get current APK version in the repo for a given base name."""
        apk_dir = self.repo_path / 'apk'
        if not apk_dir.exists():
            return None
        
        pattern = f"{base_name}-v*.apk"
        for apk_file in apk_dir.glob(pattern):
            parsed = self.parse_apk_version(apk_file.name)
            if parsed:
                return parsed[1]
        return None

    def analyze_apk_changes(self, changed_files: List[str]) -> str:
        """
        Analyze APK file changes to determine if replacement is needed.
        
        Returns: 'safe', 'replace_apk', or 'conflict'
        """
        apk_changes = [f for f in changed_files if f.startswith('apk/') and f.endswith('.apk')]
        
        if not apk_changes:
            return 'safe'
        
        for apk_file in apk_changes:
            apk_name = Path(apk_file).name
            parsed = self.parse_apk_version(apk_name)
            
            if not parsed:
                continue
            
            base_name, upstream_version = parsed
            current_version = self.get_current_apk_version(base_name)
            
            if current_version is None:
                # New APK, safe to add
                print(f"INFO: New APK detected: {apk_name}")
                continue
            
            version_cmp = self.compare_versions(current_version, upstream_version)
            
            if version_cmp == 0:
                # Same version - upstream might be more efficient
                print(f"INFO: APK version match detected: {base_name}-v{upstream_version}")
                print(f"INFO: Current repo has v{current_version}, upstream updates to v{upstream_version}")
                print(f"INFO: Recommending replacement (upstream assumed more efficient)")
                return 'replace_apk'
            elif version_cmp < 0:
                # Current version is older - safe to update
                print(f"INFO: APK update detected: {base_name} from v{current_version} to v{upstream_version}")
                return 'safe'
            else:
                # Current version is newer - potential conflict
                print(f"WARNING: Current APK v{current_version} is newer than upstream v{upstream_version}")
                return 'conflict'
        
        return 'safe'

    def analyze_index_json(self, changed_files: List[str]) -> str:
        """
        Analyze index.json and index.min.json changes.
        
        Returns: 'safe' or 'conflict'
        """
        index_files = [f for f in changed_files if f in ['index.json', 'index.min.json']]
        
        if not index_files:
            return 'safe'
        
        for index_file in index_files:
            # Get upstream version
            upstream_content = self.get_file_content(index_file, self.commit_sha)
            if not upstream_content:
                print(f"WARNING: Could not read upstream {index_file}", file=sys.stderr)
                continue
            
            # Get current version
            current_content = self.get_file_content(index_file, 'HEAD')
            if not current_content:
                print(f"INFO: {index_file} is new in upstream")
                continue
            
            try:
                upstream_data = json.loads(upstream_content)
                current_data = json.loads(current_content)
                
                # Build version maps
                upstream_versions = {
                    ext.get('pkg'): ext.get('version') 
                    for ext in upstream_data 
                    if isinstance(ext, dict)
                }
                current_versions = {
                    ext.get('pkg'): ext.get('version') 
                    for ext in current_data 
                    if isinstance(ext, dict)
                }
                
                # Check for version conflicts
                for pkg, upstream_ver in upstream_versions.items():
                    if pkg in current_versions:
                        current_ver = current_versions[pkg]
                        if current_ver and upstream_ver:
                            cmp_result = self.compare_versions(current_ver, upstream_ver)
                            if cmp_result > 0:
                                print(f"WARNING: Version conflict in {index_file}: {pkg}")
                                print(f"  Current: {current_ver}, Upstream: {upstream_ver}")
                                return 'conflict'
                            elif cmp_result == 0:
                                print(f"INFO: Version match in {index_file}: {pkg} v{current_ver}")
                
            except json.JSONDecodeError as e:
                print(f"ERROR: Failed to parse {index_file}: {e}", file=sys.stderr)
                return 'conflict'
        
        return 'safe'

    def check_merge_conflict(self) -> bool:
        """
        Check if the commit would cause merge conflicts.
        Uses git diff and git apply --check to simulate the cherry-pick.
        """
        # Get the diff for this commit
        returncode, stdout, stderr = self.run_git_command([
            'git', 'format-patch', '-1', self.commit_sha, '--stdout'
        ])
        
        if returncode != 0:
            print(f"ERROR: Failed to generate patch: {stderr}", file=sys.stderr)
            return True
        
        patch_content = stdout
        
        # Try to apply the patch with --check flag
        try:
            result = subprocess.run(
                ['git', 'apply', '--check', '--3way'],
                input=patch_content,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"WARNING: Potential merge conflict detected:", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return True
            
            return False
        except subprocess.TimeoutExpired:
            print("ERROR: Merge conflict check timed out", file=sys.stderr)
            return True
        except Exception as e:
            print(f"ERROR: Failed to check for merge conflicts: {e}", file=sys.stderr)
            return True

    def analyze(self) -> Tuple[str, int]:
        """
        Main analysis function.
        
        Returns: (decision, exit_code)
        decision: 'safe', 'replace_apk', or 'conflict'
        exit_code: 0 (safe), 1 (replace_apk), 2 (conflict), 3 (error)
        """
        print(f"Analyzing commit {self.commit_sha}...")
        
        # Get commit message for context
        returncode, commit_msg, stderr = self.run_git_command([
            'git', 'log', '--format=%B', '-n', '1', self.commit_sha
        ])
        
        if returncode == 0 and commit_msg:
            print(f"Commit message: {commit_msg.strip()[:100]}...")
        
        # Get changed files
        changed_files = self.get_commit_files()
        if not changed_files:
            print("ERROR: No files changed in commit or failed to get files", file=sys.stderr)
            return 'conflict', 3
        
        print(f"Changed files: {', '.join(changed_files)}")
        
        # Analyze APK changes
        apk_decision = self.analyze_apk_changes(changed_files)
        if apk_decision == 'replace_apk':
            print("DECISION: replace_apk (APK needs replacement)")
            return 'replace_apk', 1
        elif apk_decision == 'conflict':
            print("DECISION: conflict (APK version conflict)")
            return 'conflict', 2
        
        # Analyze index.json changes
        index_decision = self.analyze_index_json(changed_files)
        if index_decision == 'conflict':
            print("DECISION: conflict (index.json version conflict)")
            return 'conflict', 2
        
        # Check for general merge conflicts
        if self.check_merge_conflict():
            print("DECISION: conflict (merge conflict detected)")
            return 'conflict', 2
        
        print("DECISION: safe (no conflicts detected)")
        return 'safe', 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze upstream commits for safe cherry-picking'
    )
    parser.add_argument(
        'commit_sha',
        help='The commit SHA to analyze'
    )
    parser.add_argument(
        '--repo-path',
        default='.',
        help='Path to the git repository (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Validate commit SHA format
    if not re.match(r'^[0-9a-f]{7,40}$', args.commit_sha):
        print(f"ERROR: Invalid commit SHA format: {args.commit_sha}", file=sys.stderr)
        return 3
    
    analyzer = CommitAnalyzer(args.commit_sha, args.repo_path)
    decision, exit_code = analyzer.analyze()
    
    # Output the decision for the workflow to capture
    print(f"\n=== FINAL DECISION: {decision} ===")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
