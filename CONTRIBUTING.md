## Contributing

Thanks for improving this demo codebase.

### Quick loop

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
make format
make lint
make test
```

### Pre-commit

```bash
pip install pre-commit
pre-commit install
```

Hooks run **Ruff** lint + format. CI enforces the same checks.

### Pull requests

1. Prefer small commits with clear messages.  
2. Run `pytest` locally before submitting.  
3. Do **not** commit `.env`, API keys, or real customer/policy data snapshots (the corpus here is synthetic).

### Docker smoke

```bash
docker compose up --build
curl -sf http://127.0.0.1:8000/health
```
