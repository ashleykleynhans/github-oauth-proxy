# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - 2026-11-01

### Added

- Docker packaging with a `Dockerfile` and `docker-bake.hcl`, plus a GitHub
  Actions workflow that builds and pushes images to GHCR on `main` pushes and
  release tags.
- SLSA provenance and SPDX SBOM attestations on published container images.
- `docker-compose.yml` and `config.example.yml` for running the published image
  with a read-only mounted `config.yml`.
- Type hints, docstrings, `pyproject.toml` configuration, and CI lint and
  type-check jobs using ruff and mypy.
- GitHub funding configuration.

### Changed

- Hardened the OAuth proxy and modernized the toolchain: refactored the GitHub
  client, split and pinned runtime/test/dev/deploy requirements, and removed the
  unused root `__init__.py`.
- The app is now served with waitress instead of Flask's development server,
  with startup logging configured so the serving banner is visible.
- The `/info` response is trimmed to only the fields Spinnaker needs, and
  organization matching is case-insensitive.
- GitHub Actions updated to `actions/checkout@v7` and
  `actions/setup-python@v7`.
- Bumped Python dependencies to their latest releases: `ruff` 0.17.3,
  `mypy` 2.4.1, `pytest` 9.2.0, `boto3` 1.43.123, `zappa` 0.63.0,
  `awscli` 1.46.2, and `setuptools` 84.2.1.
- Bumped `docker/setup-buildx-action` and `docker/login-action` to v4.

### Fixed

- Missing returns in the `/info` handler that caused HTTP 500 responses when
  authentication details were missing.
- `UnboundLocalError` raised when no `config.yml` was present.
- `domain_required_as_primary` was not enforced, making the primary email check
  a no-op.
- Email domain matching now uses exact domain equality instead of substring
  containment.
- GitHub API error responses are parsed as JSON only for error statuses, and
  non-JSON bodies are tolerated.
- Name parsing now handles null, empty, and single-word names.
- Exception details are no longer leaked in 404/500 responses; errors are logged
  server-side instead.
- `get_user_teams` now fails loudly on non-200 responses through the shared
  request helper.

## [1.2.0] - 2026-02-12

### Added

- Team and role information in the `/info` response.
- Unit test suite covering the GitHub client and webhook handlers.
- GitHub Actions workflow to run the tests on pushes and pull requests.
- Additional tests for configuration validation.

### Changed

- Teams and roles are returned as a comma-separated string instead of a JSON
  array.
- Reverted the substitution of null profile values with empty strings; null
  values are returned as-is again.

### Fixed

- Tests no longer fail when `config.yml` is absent.

## [1.1.0] - 2025-09-13

### Added

- HTTP 401 response when the `Authorization` header is missing.

### Changed

- Null values in the GitHub profile are returned as empty strings instead of
  `null`.

## [1.0.0] - 2024-05-31

### Added

- Initial release of the GitHub OAuth2 proxy for Spinnaker.
- `/info` endpoint returning GitHub user details in the format Spinnaker's Gate
  expects.
- `/` health-check endpoint.
- Optional access requirements configured via `config.yml`: GitHub organization
  membership, email domain, and email domain as the primary address.
- Optional mapping of GitHub usernames to Spinnaker usernames.
- Documentation for local development, AWS Lambda deployment with Zappa, and
  Spinnaker Gate configuration.

### Changed

- Python runtime updated to 3.12.

[Unreleased]: https://github.com/ashleykleynhans/github-oauth-proxy/compare/1.3.0...HEAD
[1.3.0]: https://github.com/ashleykleynhans/github-oauth-proxy/compare/1.2.0...1.3.0
[1.2.0]: https://github.com/ashleykleynhans/github-oauth-proxy/compare/1.1.0...1.2.0
[1.1.0]: https://github.com/ashleykleynhans/github-oauth-proxy/compare/1.0.0...1.1.0
[1.0.0]: https://github.com/ashleykleynhans/github-oauth-proxy/releases/tag/1.0.0
