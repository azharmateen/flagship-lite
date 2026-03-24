# flagship-lite

[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-blue?logo=anthropic&logoColor=white)](https://claude.ai/code)


**Feature flags that live in your repo. No SaaS, no vendor lock-in.**

Define flags in YAML, evaluate them locally with deterministic rollouts, and serve them via HTTP. Zero infrastructure required.

## Why flagship-lite?

- **No SaaS dependency** -- flags live in `flags.yaml`, committed to your repo
- **Deterministic rollouts** -- same user always gets the same result (hash-based)
- **Targeting rules** -- match on user_id, email, environment, regex, and more
- **Stale flag detection** -- find flags that are always-on, unused, or ancient
- **HTTP server** -- optional FastAPI server for non-Python services
- **Python SDK** -- one-liner in your code: `if flag_enabled("new_checkout", user_id="123")`

## Install

```bash
pip install flagship-lite
```

## Quick Start

```bash
# Create flags.yaml with examples
flagship-lite init

# List all flags
flagship-lite list

# Evaluate a flag
flagship-lite eval new_checkout --user-id 123 --env production

# Toggle a flag
flagship-lite toggle dark_mode

# Find stale flags
flagship-lite stale

# Start HTTP server
flagship-lite serve --port 8100
```

## flags.yaml

```yaml
flags:
  - name: new_checkout
    description: New checkout flow with improved UX
    enabled: true
    rollout_percentage: 25.0
    environments: [staging, production]
    targeting_rules:
      - attribute: email
        operator: ends_with
        value: "@company.com"
    tags: [frontend, checkout]
```

## Python SDK

```python
from flagship_lite import flag_enabled

# Simple check
if flag_enabled("new_checkout", user_id="user-123"):
    show_new_checkout()

# With full context
if flag_enabled("dark_mode", email="user@beta.com", environment="production"):
    enable_dark_mode()
```

## Targeting Rules

| Operator | Example | Matches |
|----------|---------|---------|
| `eq` | `email eq admin@co.com` | Exact match |
| `neq` | `env neq production` | Not equal |
| `contains` | `email contains @beta` | Substring |
| `starts_with` | `user_id starts_with vip_` | Prefix |
| `ends_with` | `email ends_with @co.com` | Suffix |
| `in` | `country in [US, CA, UK]` | List membership |
| `regex` | `email regex ^.*@(alpha\|beta)\.com$` | Regex match |

## Percentage Rollout

Rollout is deterministic: a hash of `flag_name:user_id` maps to a 0-99 bucket. Same user always gets the same result. No database needed.

```yaml
- name: new_feature
  enabled: true
  rollout_percentage: 10.0  # 10% of users
```

## HTTP Server

```bash
flagship-lite serve --port 8100
```

```
GET  /flags                         # List all flags
GET  /flags/<name>                  # Get flag details
GET  /flags/<name>/eval?user_id=X   # Evaluate flag
POST /flags/<name>/toggle           # Toggle flag
```

## License

MIT
