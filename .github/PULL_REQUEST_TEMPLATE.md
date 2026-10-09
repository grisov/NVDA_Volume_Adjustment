## Summary
<!-- Describe the changes made in this PR and why they are necessary. -->

## Related Issue
<!-- Link to related issue(s), e.g., Fixes #123 -->

## Type of Change
- [ ] Bug fix (fixes an issue without breaking existing API/behavior)
- [ ] New feature (adds new capability to the add-on)
- [ ] Performance improvement
- [ ] Code refactoring (no functional changes)
- [ ] Dependency update / CI pipeline tweak

## NVDA Testing & Verification Environment
- **Minimum NVDA Version Tested:** <!-- e.g. 2024.1 -->
- **Latest NVDA Version Tested:** <!-- Specify exact version number, e.g. 2026.2 (do not use "latest alpha") -->
- **OS / Windows Version:** <!-- Full Windows version and build number, e.g. Windows 11 23H2 (build 22631.4169) -->

### Screen Reader & Accessibility Impact
- [ ] **Speech Output**: Verified speech feedback in affected NVDA modes/dialogs.
- [ ] **Braille Output**: Checked braille output/formatting.
- [ ] **Gestures & Shortcuts**: Verified keyboard shortcuts and NVDA input gestures.

## Add-on Manifest & Metadata Verification
- [ ] **`buildVars.py`**: Verified version strings, `minimumNVDAVersion`, and `lastTestedNVDAVersion`.
- [ ] **`changelog.md`**: Added a description of the change under the unreleased/current section.
- [ ] **i18n / Translatable Strings**: Ensured all user-visible strings use gettext (`_()`), and updated `.pot` file via `scons pot` if new strings were added.

## Testing strategy
<!-- Describe the manual or automated testing performed for this change. (Note: standard linting, formatting, and tests are automated via CI/CD) -->
