# CLAUDE.md

IoT Monitoring Platform — a portfolio of seven connected projects (serverless + containerised ingestion, two analytics pipelines, an Azure lakehouse, a Kafka device gateway, an AI assistant) sharing one DynamoDB data contract. Live at iot.gonzalezsanchez.dev.

## Git workflow

- Never commit directly to `main`. Work on `feature/…`, `fix/…`, `docs/…`, or `chore/…` branches and merge via GitHub PR only — no local merges.
- Keep at most one feature branch open alongside `main`; delete branches (local + remote) once their PR is merged.
- Pull `main` before starting work — this repo is used from multiple machines, the local checkout may be stale.
- `main` is production: every merge deploys via GitHub Actions (images to GHCR, Docker Compose on a self-hosted server).

## Repo gotchas

- `temp/` is a private submodule (planning notes), but unlike a typical vendored submodule it's actively developed in place — its own branches, commits, PRs. Never commit its content to this repo; only the submodule pointer is tracked, and it is bumped only on explicit request (a plain `git add temp && git commit` on `main`, no PR needed for the pointer bump itself).
- Run `git config --local submodule.recurse false` once per machine/clone. With it left at Git's default (`true`), any root-level `git checkout`/`git pull` silently resets `temp/`'s working tree to the recorded pointer commit — destructive to whatever branch/work was checked out inside `temp/`, and exactly wrong for a submodule that's developed in place rather than just consumed. If you hit this on a machine where it's still `true`: recover with `git -C temp checkout main && git -C temp pull`, then set the config so it stops recurring.

## Conventions

- Python 3.11. ruff (line length 100, rules E/F/I/UP) and mypy with `disallow_untyped_defs` run in CI and pre-commit.
- Dependencies: pip with pinned `requirements.txt` / `requirements-dev.txt` per project. Not uv, not poetry — don't migrate.
- FastAPI services follow models → services → repositories layering; no business logic in route handlers.
- DynamoDB writes: convert floats to `Decimal`, and let tests assert the *type* (`Decimal("22.5") == 22.5` is true, so equality alone misses regressions).
- All documentation is in English. Public docs live in each project's `README.md`; component details (deploy/destroy, Terraform) in sub-READMEs like `infrastructure/README.md`.

## Testing

- Each backend project has its own pytest suite (AWS mocked with moto, HTTP with httpx); CI enforces 80%+ coverage before merge.
- Run a project's tests from its own directory, e.g. `cd backend/project3b-iot-gateway && pytest`.

## Code review

Specialised reviewer agents live in `.claude/agents/` — use `python-reviewer`, `terraform-reviewer`, or `dbt-reviewer` for stack-specific review instead of a general pass.
