# Cherry-Pick Automation Workflow

This document describes the automated cherry-pick workflow that synchronizes changes from the upstream repository (keiyoushi/extensions) to this fork (FelipeGFA/extensoes).

## Overview

The workflow automatically:
1. Identifies commits that are behind the upstream repository
2. Analyzes each commit for potential conflicts
3. Cherry-picks safe commits
4. Replaces APK files when versions match (assuming upstream is more efficient)
5. Skips conflicted commits and creates issues for manual review

## Workflow Files

### `.github/workflows/cherry-pick-upstream.yml`

Main GitHub Actions workflow that orchestrates the entire process.

**Triggers:**
- **Schedule**: Daily at 2 AM UTC
- **Manual**: Via workflow_dispatch with optional max_commits parameter

**Key Features:**
- Processes up to 10 commits by default (configurable via manual trigger)
- Uses intelligent analysis script to determine action for each commit
- Handles three scenarios: safe cherry-pick, APK replacement, conflicts
- Creates GitHub issues for commits requiring manual intervention
- Provides detailed summary in workflow output

### `scripts/analyze_commit.py`

Python script that analyzes upstream commits to determine the appropriate action.

**Analysis Types:**
1. **APK File Analysis**: Compares versions and detects when replacement is needed
2. **Index JSON Analysis**: Checks for version conflicts in extension metadata
3. **Merge Conflict Detection**: Simulates cherry-pick to detect potential conflicts

**Exit Codes:**
- `0`: Safe to cherry-pick
- `1`: APK replacement needed
- `2`: Conflict detected
- `3`: Error occurred

## Workflow Process

### Step 1: Setup
- Checks out the `repo` branch
- Configures git with bot credentials
- Sets up Python 3.11
- Adds upstream remote (keiyoushi/extensions)

### Step 2: Identify Behind Commits
```bash
git log --reverse --pretty=format:"%H" HEAD..upstream/repo
```
This gets all commits in upstream that are not in the current branch, ordered from oldest to newest.

### Step 3: Analyze Each Commit

For each commit, the workflow:

1. **Runs analysis script**:
   ```bash
   python3 scripts/analyze_commit.py <commit_sha>
   ```

2. **Processes based on decision**:

   **Safe (exit code 0)**:
   - Executes `git cherry-pick <commit_sha>`
   - If successful, increments success counter
   - If failed, aborts and marks as conflict

   **Replace APK (exit code 1)**:
   - Extracts APK files from commit
   - Removes current version of affected APKs
   - Checks out new APK from upstream commit
   - Updates index.json files if changed
   - Creates commit with automated message

   **Conflict (exit code 2)**:
   - Skips commit
   - Adds to conflict list for manual review
   - No changes made

### Step 4: Push Changes

If any commits were successfully processed:
```bash
git push origin repo
```

### Step 5: Report Conflicts

If conflicts or errors occurred:
- Creates or updates GitHub issue with label `cherry-pick-conflicts`
- Includes summary of all affected commits
- Provides link to workflow run for details

## APK Replacement Logic

The workflow includes special handling for APK files:

**Scenario**: Current repo has `tachiyomi-all.nhentai-v1.4.54.apk` and upstream commit also has `v1.4.54`

**Analysis**:
- Script detects version match
- Assumes upstream version is more efficient (better optimization, bug fixes)
- Recommends replacement

**Action**:
1. Removes current `tachiyomi-all.nhentai-v1.4.54.apk`
2. Checks out upstream `tachiyomi-all.nhentai-v1.4.54.apk`
3. Updates index.json with upstream metadata
4. Creates commit: "chore: APK replacement from upstream"

## Manual Intervention

Commits requiring manual intervention will be listed in GitHub issues with:
- Commit SHA
- Commit message
- Link to workflow run
- Summary of why manual review is needed

To manually cherry-pick:
```bash
git fetch upstream repo
git cherry-pick <commit_sha>
# Resolve conflicts if any
git push origin repo
```

## Configuration

### Adjusting Max Commits

To process more than 10 commits at once:
1. Go to Actions → Cherry-pick Upstream Commits → Run workflow
2. Enter desired number in "Maximum number of commits to process"
3. Click "Run workflow"

### Changing Schedule

Edit `.github/workflows/cherry-pick-upstream.yml`:
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

Use [crontab.guru](https://crontab.guru/) to generate custom schedules.

## Monitoring

### Workflow Runs
- View at: `https://github.com/FelipeGFA/extensoes/actions/workflows/cherry-pick-upstream.yml`
- Check "Summary" for detailed report

### Issues
- Filter by label: `cherry-pick-conflicts`
- Auto-created when conflicts detected
- Updated with new conflicts rather than creating duplicate issues

## Troubleshooting

### Workflow Fails to Start
- Check if workflow file has valid YAML syntax
- Verify branch permissions allow workflow execution

### Script Errors
- Review workflow logs for Python traceback
- Test locally: `python3 scripts/analyze_commit.py <commit_sha>`

### False Positives in Conflict Detection
- Review analysis output in workflow logs
- May need to adjust analysis logic in `scripts/analyze_commit.py`

### APK Replacement Not Working
- Verify APK filename follows pattern: `name-v{version}.apk`
- Check that base name matches between old and new APK
- Review file paths in commit (should be in `apk/` directory)

## Security Considerations

- Workflow uses `GITHUB_TOKEN` with `contents: write` permission
- Bot commits are signed with `github-actions[bot]` identity
- Workflow cannot push to protected branches without additional configuration
- Script runs in isolated runner environment

## Future Enhancements

Potential improvements:
- Add support for custom conflict resolution strategies
- Implement rollback mechanism for failed cherry-picks
- Add metrics and analytics for sync success rate
- Support for multiple upstream branches
- Automatic PR creation for conflict resolution

## Related Documentation

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Git Cherry-Pick Guide](https://git-scm.com/docs/git-cherry-pick)
- [Scripts README](scripts/README.md)
