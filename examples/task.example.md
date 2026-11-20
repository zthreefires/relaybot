# Add a --dry-run flag to the export command

Repo: the clone the dispatcher picked (codex-run's <workdir>).

Goal: `export` should accept `--dry-run` and print what it would write without writing files.

Constraints:
- Keep the existing CLI output format.
- Add a test next to the existing export tests and run the test suite.
- Do not push; leave the change uncommitted for review.

Background the dispatcher knows: the export code was split into its own module last month;
the maintainer prefers small, focused diffs.
