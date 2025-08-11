---
description: Build, test, and publish Python packages with proper versioning and PyPI deployment
argument-hint: <package-name> [version-bump]
allowed-tools: Bash, Read, Edit, MultiEdit, Grep, Glob, Task
---

Build, test, and release a Python package from the monorepo. Handle both private packages (GitHub only) and public packages (PyPI).

**Your task: Execute a complete package release workflow appropriate for the package type.**

## Phase 1: Pre-flight Checks

**Run Makefile preflight:**
```bash
make preflight-<package>
```
This checks:
- Package exists
- Build system configured
- Private/Public status (shows ⚠️ if private)
- README exists
- Current version

**Additional checks for PUBLIC packages:**
- Determine package type:
  - TOOLS (termtap, webtap, logtap) → Install locally with `uv tool install`
  - LIBRARIES (tmux-popup) → Package for `uv add`
- **Verify PyPI image compatibility** (not in Makefile):
  - Check all README image URLs use `https://raw.githubusercontent.com/` format
  - Fix any relative paths or blob URLs before proceeding
  - This prevents post-publish patches

## Phase 2: Version Management

**If version bump requested (patch/minor/major):**
```bash
make bump-<package> BUMP=<type>
```

**Otherwise:**
- Use current version from pyproject.toml
- Confirm version with user before proceeding

## Phase 3: Build & Test

**Execute build pipeline:**
```bash
make clean-<package>              # Clean old artifacts
make build-<package>              # Build with --no-sources
make test-build-<package>         # Test imports work
```

**Verify build artifacts:**
- Check `packages/<package>/dist/` contains wheel and sdist
- Ensure version numbers match pyproject.toml

## Phase 4: Git Operations

**Commit any pending changes:**
```bash
git add -A
git commit -m "chore: prepare <package> v<version> for release

- Update version to <version>
- <any other changes>"
```

**Create release tag:**
```bash
make release-<package>  # Creates git tag, installs tools locally if applicable
```

## Phase 5: Distribution

### For PUBLIC packages (no Private classifier):
```bash
make publish-<package>  # Publishes to PyPI using pass pypi/uv-publish
```

**Verify PyPI publication:**
```bash
# Check version on PyPI
curl -s https://pypi.org/pypi/<package>/json | jq -r '.info.version'

# Check with uv
uv pip install --dry-run <package>==<version>
```

### For PRIVATE packages (has Private classifier):
- Skip PyPI publication
- Package remains GitHub-only
- Users install via: `uv tool install "git+https://github.com/USER/REPO.git#subdirectory=packages/<package>"`
- Inform user that package is private and won't be published to PyPI

## Phase 6: Push to GitHub

```bash
git push origin main
git push origin <package>-v<version>
```

## Phase 7: Post-Release Verification

**For PUBLIC packages:**
- Verify package appears on PyPI
- Check README renders correctly with images
- Test installation: `uv add <package>` or `uv tool install <package>`

**For PRIVATE packages:**
- Verify tag is pushed to GitHub
- Document installation method in README
- Ensure GitHub installation works

## Key Strategies

- **Respect privacy**: Never attempt PyPI publish for private packages
- **Package-local builds**: Each package has its own `dist/` directory
- **Tool vs Library distinction**: Different installation methods
- **PyPI compatibility first**: Fix image URLs before building, not after
- **Atomic releases**: Complete each phase before moving to next
- **Token security**: Use `pass` for PyPI authentication

Start by checking if the package exists, determining its privacy status, and confirming the version to release.