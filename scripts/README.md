# Scripts

This directory contains automation scripts used by GitHub Actions workflows.

## analyze_commit.py

Analyzes upstream commits from keiyoushi/extensions to determine if they can be safely cherry-picked into this repository.

### Usage

```bash
python3 analyze_commit.py <commit_sha> [--repo-path <path>]
```

### Exit Codes

- **0**: Safe to cherry-pick - No conflicts detected
- **1**: APK replacement needed - Same version detected, upstream assumed more efficient
- **2**: Conflict detected - Manual intervention required
- **3**: Error occurred during analysis

### Analysis Process

1. **APK File Analysis**
   - Detects version changes in APK files
   - If current repo has v1.4.54 and upstream updates to v1.4.54, recommends replacement (assumes upstream is more efficient)
   - If current version is older, marks as safe to update
   - If current version is newer, flags as conflict

2. **index.json Analysis**
   - Compares extension versions between current and upstream
   - Detects version conflicts in extension metadata

3. **Merge Conflict Detection**
   - Simulates cherry-pick using `git apply --check`
   - Detects potential merge conflicts

### Example Output

```
Analyzing commit abc1234...
Commit message: Update nhentai extension to v1.4.54...
Changed files: apk/tachiyomi-all.nhentai-v1.4.54.apk, index.json
INFO: APK version match detected: tachiyomi-all.nhentai-v1.4.54
INFO: Current repo has v1.4.54, upstream updates to v1.4.54
INFO: Recommending replacement (upstream assumed more efficient)
DECISION: replace_apk (APK needs replacement)

=== FINAL DECISION: replace_apk ===
```

## Contributing

When adding new scripts, please:
1. Include proper error handling
2. Add docstrings and comments
3. Update this README with usage information
4. Make scripts executable (`chmod +x`)
