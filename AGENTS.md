# Repository Guidelines

## Project Structure & Module Organization
Core FastAPI workflows live in `api_utils/`, with `app.py` managing lifecycle hooks, `routes.py` hosting endpoints such as `/v1/chat/completions`, `request_processor.py` orchestrating each request, and `queue_worker.py` handling async jobs. Automation fallbacks reside in `browser_utils/` (`page_controller.py`, `model_management.py`, `script_manager.py`). Configuration values come from `config/` (`settings.py`, `constants.py`, `selectors.py`) and the `.env`. Shared data contracts sit under `models/`, while streaming helpers live in `stream/`. Entry points like `server.py`, `launch_camoufox.py`, and `gui_launcher.py` are at the repo root, and tests mirror the source layout under `tests/`.

## Build, Test, and Development Commands
Run `poetry install --with dev` to pull runtime and dev dependencies, then `poetry shell` to enter the virtualenv. Launch the API with `poetry run uvicorn server:app --reload --port 2048`. Browser hardened binaries require `camoufox fetch`, and Playwright prerequisites install via `playwright install-deps firefox`. For first-time auth, run `poetry run python launch_camoufox.py --debug`. Execute the full suite with `poetry run pytest` or target a file, e.g., `poetry run pytest tests/test_model_catalog.py`.

## Coding Style & Naming Conventions
Python code follows `black` (88-char lines) and `isort` ordering; run `poetry run black .` and `poetry run isort .` before commits. Enforce linting with `poetry run flake8 .` and type checks via `npx pyright`. Stick to `snake_case` for functions and variables, `PascalCase` for classes, and provide docstrings for public modules, classes, and functions.

## Testing Guidelines
Tests use `pytest` with fixtures housed in `tests/`. Mirror the source tree when adding new tests (e.g., `tests/api_utils/test_request_processor.py`). Cover both happy paths and failure scenarios, especially around queue handling, streaming, and browser fallbacks. Keep existing tests green before introducing new functionality.

## Commit & Pull Request Guidelines
Adopt Conventional Commits (e.g., `feat(queue): handle retry backoff`). PRs should summarize changes, reference issues (`Fixes #123`), and attach logs or screenshots for browser flows. Confirm formatting, lint, type checks, and tests locally before requesting review, and highlight any impact on the request queue, streaming proxy, or automation paths.

## Security & Configuration Tips
Audit `.env` entries against `config/settings.py` before deploying. Avoid committing credentials; use environment variables for secrets. When updating Playwright or Camoufox assets, document the required versions so other contributors can reproduce the environment.
