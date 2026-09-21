# Contributing

Thanks for your interest in contributing to **AI Bidding Workbench for Power Grid Projects**.

## Ways to contribute

You can help by:

- reporting reproducible bugs;
- improving OCR, document parsing, RAG, reranking, or LLM integration;
- adding or improving tests;
- improving deployment, security, and observability;
- improving documentation and examples;
- proposing provider abstractions for models, storage, or infrastructure.

## Before opening an issue

Please search existing issues first. When reporting a bug, include:

- environment and deployment mode;
- minimal reproduction steps;
- expected and actual behavior;
- relevant logs with secrets and private bidding data removed;
- screenshots only when they do not contain confidential information.

Do **not** upload customer documents, credentials, API keys, internal bid files, or other sensitive data.

## Development setup

1. Create and activate a Python virtual environment.
2. Install backend dependencies with `pip install -r requirements.txt`.
3. Install frontend dependencies with `cd frontend && npm install`.
4. Copy `.env.example` to `.env` and configure only your own development credentials.
5. Start PostgreSQL/pgvector with Docker as described in the README.
6. Run the backend with Gunicorn and the frontend with the documented development workflow.

See the README and `docs/` for the current architecture and deployment instructions.

## Pull requests

Keep pull requests focused and explain:

- what problem the change solves;
- the major implementation choices;
- how the change was tested;
- whether configuration, database migrations, deployment, or documentation are affected.

For behavior changes, add or update tests whenever practical. For user-facing or deployment changes, update the relevant documentation in the same pull request.

## Code quality and security

- Never commit secrets or production credentials.
- Avoid logging private bidding content, personal information, or authentication data.
- Preserve backward compatibility unless the change is explicitly documented.
- Prefer small, reviewable changes over unrelated large refactors.
- Validate database migrations and model-provider changes before merging.

## AI-assisted contributions

AI coding tools, including Codex, are welcome when used responsibly. Contributors remain responsible for reviewing generated changes, running relevant tests, verifying security implications, and ensuring that submitted code is understandable and maintainable.

## License

By contributing, you agree that your contributions will be licensed under the repository's [MIT License](LICENSE).
