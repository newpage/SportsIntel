# SportsIntel Development Instructions

- Keep changes small and focused on the active sprint.
- Preserve API compatibility and existing behavior unless the sprint explicitly changes it.
- Keep NFL predictions explainable through structured factors and metadata.
- Introduce new intelligence signals as observation-only.
- Do not change picks, ratings, or displayed confidence unless the sprint explicitly requires it.
- Follow existing model, provider, UI, and test patterns.
- Run the backend tests and frontend build before completing work.
- PR work is not complete until all required CI checks pass. Review failed
  workflow logs and fix failures on the same branch; never bypass, disable, or
  weaken a check merely to make CI green.
