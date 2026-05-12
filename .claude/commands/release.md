---
description: Build, test, and release Python packages via uv wrapper
argument-hint: [package-name] [version-bump]
allowed-tools: Bash, Read, Edit, MultiEdit, Grep, Glob
---

Release a package using the uv wrapper's release workflow.

**Your task: Release the specified package.**

## Step 1: Navigate to package

For workspace packages, cd into the package directory first:
```bash
cd packages/<package-name>
```

## Step 2: Ensure CHANGELOG is ready

Check CHANGELOG.md has entries in the [Unreleased] section:
- Document what was Added, Changed, Fixed, or Removed
- Use clear, user-focused descriptions
- Follow Keep a Changelog format

If no CHANGELOG.md exists: `uv changelog init`

## Step 3: Version Bump

```bash
uv version --bump <patch|minor|major>
```

This atomically:
- Updates version in pyproject.toml
- Syncs uv.lock
- Moves [Unreleased] to new version in CHANGELOG.md
- Commits changes
- Creates git tag (v1.0.0 or package-v1.0.0 for workspace packages)

## Step 4: Push

```bash
git push && git push --tags
```

## Step 5: Build & Publish

```bash
uv build
uv publish
```

`uv publish` shows a review summary and provides a confirmation token. The user must run `uv publish --confirm <token>` themselves (requires GPG for PyPI token via `pass`).

**Do NOT run `uv publish --confirm` — that requires the user's GPG key.**

## Key Points

- **uv wrapper enforces**: Clean git state before bump and publish
- **uv wrapper blocks**: Publishing if tag is behind HEAD or stale dist files exist
- **uv wrapper handles**: Workspace tag prefixes automatically (package-v1.0.0)
- **uv wrapper gates**: Publishing behind a time-limited confirmation token + GPG
