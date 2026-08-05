# Main branch protection

Configure branch protection for `main` in GitHub repository settings after the
Sprint 14.7 workflow has completed successfully at least once. Repository
settings are intentionally not managed by source code in this sprint.

Recommended required status checks:

- `Backend quality`
- `PostgreSQL integration`
- `Frontend quality`
- `Docker validation`

Also require pull requests before merging and require branches to be up to date
before merge. Do not permit required checks to be skipped solely to merge a
change. Administrators should follow the same required checks except during a
documented incident response.

Workflow display names are part of the protection contract. If a job name is
changed in `.github/workflows/ci.yml`, update the required check in GitHub before
removing the old name so pull requests are not left permanently blocked.
