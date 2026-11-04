# Repository instructions

This repository stores reusable skills, not their users' project outputs.

- Keep each skill self-contained under `skills/<name>/` with a valid `SKILL.md`.
- Read the relevant skill before changing its behavior. Preserve its invocation policy and third-party licenses.
- Keep case photos, personal landmarks, generated models, weights, runtimes, credentials, and machine-specific configuration out of commits.
- Update the generated catalog using `python scripts/manage_skills.py catalog`; run `python scripts/manage_skills.py check` and appropriate behavior tests.
- Do not claim a skill's visual outputs passed merely because syntax, metadata, or contract tests passed.
- Keep Chinese user documentation clear and actionable. Never silently overwrite installed local customizations when syncing.
- Do not force-push or overwrite unrelated skills. Publishing a code change does not authorize uploading users' case data.
