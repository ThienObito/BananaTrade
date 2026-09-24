# BananaTrade

Paper-trading research system. Phase 0 provides configuration and a guarded 9Router gateway.

## Windows setup

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Set `NINEROUTER_API_KEY`, then replace model placeholders in `config/models.yaml`. No live trading is implemented.
