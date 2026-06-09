# Contributing

This repository is a technical assignment submission, so changes should be easy to review, reproducible, and explicit about verification.

## Commit Messages

Use a structured multi-line commit message:

```text
type(scope): concise summary

- describe the first concrete change
- describe the second concrete change
- note verification or follow-up when relevant
```

Allowed types:

- `feat`: new user-facing or assignment-facing capability
- `fix`: bug fix or correctness improvement
- `chore`: repository, dependency, or housekeeping change
- `docs`: documentation-only change
- `test`: test-only change
- `refactor`: code structure change without behavior change
- `perf`: performance improvement
- `ci`: CI/CD or automation change

Example:

```text
ci(github): add local pipeline verification workflow

- install Python dependencies in GitHub Actions
- run clean full pipeline, repeated incremental run, and pytest
- keep workflow free of secrets and external service dependencies
```

To use the included template locally:

```bash
git config commit.template .gitmessage
```

## Verification

Before pushing, run:

```bash
make clean
make run
make run-incremental
make test
```

GitHub Actions runs linting and unit tests on pushes and pull requests to `main`. The full end-to-end pipeline remains a local verification step because the assessment data files are intentionally not tracked in Git.
