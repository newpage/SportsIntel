## Summary

<!-- What changed and why? -->

## Architecture impact

<!-- Note affected boundaries, interfaces, and compatibility. Use "None" when appropriate. -->

## Prediction invariants

- [ ] Picks are unchanged unless explicitly required.
- [ ] Model probabilities, displayed confidence, ratings, and consensus behavior are unchanged unless explicitly required.
- [ ] New intelligence or diagnostic behavior remains observation-only where required.

## Tests performed

<!-- List local and CI validation with results. -->

## Database/schema impact

<!-- Describe migrations, compatibility, and data lifecycle. Use "None" when appropriate. -->

## Deployment impact

<!-- Describe configuration, rollout, or operational changes. Use "None" when appropriate. -->

## Rollback notes

<!-- Explain how to safely revert this change. -->

## Checklist

- [ ] Changes are small and sprint-focused.
- [ ] API compatibility is preserved or explicitly documented.
- [ ] Backend tests pass.
- [ ] Frontend type checking and production build pass.
- [ ] PostgreSQL integration passes when applicable.
- [ ] Docker validation passes.
- [ ] Required GitHub Actions checks pass.
- [ ] No secrets or credentials were committed.
