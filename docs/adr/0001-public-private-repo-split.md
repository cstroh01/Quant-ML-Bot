# ADR 0001: Split into Public Framework and Private Strategy/Execution Repository

## Status
Accepted

## Date
2026-09-06

## Context
Quant-ML-Bot is built around strict quantitative and engineering principles:
point-in-time correctness (Rule 1), purged and embargoed walk-forward cross-validation
(Rule 2), realistic cost modeling (Rule 3), rigorous baseline comparison (Rule 4), and
layer separation (Rule 8). The roadmap progresses deliberately:
$$\text{backtest} \longrightarrow \text{paper trading} \longrightarrow \text{small live capital}$$

As the project approaches live deployment, a fundamental architectural tension emerges
between two competing objectives:

1. **Open-Source Credibility & Community Contribution**: A public framework provides
   transparent verification of quantitative mechanics, invites peer review of statistical
   methodologies (e.g. cross-validation leakage guards, feature standardization), and
   maintains clean CI testing without bespoke hidden environments.
2. **Proprietary Alpha & Live Capital Security**: A capital-trading system cannot expose its
   operational edge. Disclosing tuned hyperparameter configurations, trained model
   checkpoints, execution routing logic, or broker account connectivity compromises trading
   performance and creates severe security liabilities (Rule 7: *"Execution code is never
   autonomous; credentials live in a gitignored .env and never appear in the repository"*).

Attempting to maintain both in a single repository inevitably fails: either the public repo
accidentally leaks proprietary edge and credentials, or private confidentiality concerns
stifle public collaboration, version control, and automated CI pipelines.

## Decision
We split the system into two distinct repositories with a clean one-way dependency boundary:

### 1. `Quant-ML-Bot` (Public Repository)
The public repository serves as the open-source algorithmic trading and ML framework:
- **Scope**: Core framework code (`data.py`, `features.py`, `estimators.py`, `model_cv.py`,
  `signals.py`, `backtest_harness.py`, `metrics.py`), documentation, test suites, and
  spec-kit development specifications (`.specify/`).
- **Baselines & Fixtures**: Houses only untuned fallback configurations, simple baselines
  (buy-and-hold, random signal, untuned logistic baseline), synthetic test fixtures, and
  cached historical reference data.
- **Strict Invariants**: Contains **zero** proprietary tuned hyperparameters, **zero**
  production model weights, **zero** live broker credentials, and **zero** automated live order
  routing logic.

### 2. Private Companion Repository (`Quant-ML-Bot-Live` / Private)
A separate, strictly private repository holds proprietary capital-trading assets:
- **Scope**: Production configuration files, tuned model parameters, walk-forward checkpoint
  artifacts, broker adapters (Alpaca, Interactive Brokers, etc.), real-time execution engines
  (`exec/`), and production deployment scripts.
- **Dependency Model**: Consumes `Quant-ML-Bot` as an upstream dependency (via pinned git
  submodule or versioned private package import).
- **Environment**: Manages live `.env` secrets, live logging, trade databases, and actual
  portfolio risk/allocation limits.

## Consequences

### Positive
- **Guaranteed Alpha & Credential Protection**: Proprietary parameters, winning feature
  combinations, and broker API secrets cannot be accidentally committed or leaked through
  public pull requests, open issues, or CI logs.
- **Clean Architecture & Interface Discipline (Rule 8)**: Forcing the private trading
  system to import the public framework as an external module ensures clean API
  boundaries. Framework code cannot harbor strategy-specific shortcuts or ad-hoc broker
  dependencies.
- **Frictionless Open-Source Collaboration**: External contributors and automated agent
  lanes can develop, test, and run CI against the public framework without requiring access
  to private keys, live data feeds, or capital accounts.
- **Independent Release Cadence**: Framework improvements and refactors can be committed,
  tested, and released without forcing immediate deployment to live trading infrastructure.

### Negative / Tradeoffs
- **Two-Repo Coordination**: Improvements to core execution or feature logic require a
  two-step workflow (commit and verify in the public framework, then update dependency
  pinning in the private repo).
- **Integration Testing Overhead**: End-to-end integration tests that verify private broker
  execution against public framework signals must run in private CI or local developer
  environments.
