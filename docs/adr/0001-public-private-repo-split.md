# ADR 0001: Split into Public Framework and Private Strategy/Execution Repository

## Status
Proposed (amended 2026-09-08; see Addendum below — reverted from an erroneous "Accepted" mark, pending Camden's sign-off)

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

## Addendum (2026-09-08): Scope amended, status reverted pending review

### Status correction

This ADR's Status field read "Accepted" as committed 2026-09-06 (commit
`d69a6d4`, an Antigravity session). Camden had not reviewed it at that point.
**Status is corrected to `Proposed`** as of this addendum. It becomes
`Accepted` only once Camden signs off on the amended scope below — an agent
marking its own architectural decision final is not the same thing as the
decision being made.

### Amended decisions (Camden, 2026-09-08)

1. **Dependency model resolved**: the private repo consumes the public repo
   as a **versioned package** (pinned, e.g. via `pip install git+ssh://...@vX.Y.Z`
   or a private package index), not a git submodule. Submodules are simpler
   to wire up but keep the two repos in a detached-HEAD relationship that is
   easy to desync silently; a versioned package forces an explicit,
   reviewable bump every time the private repo takes a new framework
   version — the same discipline this project already applies to every
   other dependency (`requirements.txt`, pinned by exact version).

2. **Split trigger widened**: the repo split must be substantively true —
   not necessarily mechanically split into two git remotes — **before
   advanced ML/quant logic goes in**, not merely before live capital touches
   the account. "Substantively true" means: no code that constitutes real
   predictive edge is written directly into the public tree in the first
   place, even while both trees still live in one repository during active
   development. The *physical* two-repo split (separate remotes, package
   versioning, private CI) still happens on its own schedule — see
   *Sequencing* below — but the *discipline* of not committing edge-bearing
   logic to the tree that will become public starts now.

3. **Scope narrowed**: the original Decision section (above) listed
   `estimators.py`, `signals.py`, and `model_cv.py` as public in full. That
   is revised:

   - **Stays public, unchanged**: `data.py`, `backtest_harness.py`,
     `model_cv.py` (the leakage-guard machinery — purge/embargo, walk-forward
     folds — is itself the open-source credibility asset; it is generic
     mechanics, not edge), `metrics.py`, `plotting.py`, the cost-hurdle
     module (spec 012), the test suite, and all specs/docs.
   - **`estimators.py` stays public as an interface + registry pattern.**
     Confirmed 2026-09-08: its current `ESTIMATOR_REGISTRY` entries
     (logistic, ridge, hgb×2) hold generic search grids and sklearn
     defaults, not tuned values — this is exactly the "untuned fallback
     configuration" this ADR already calls for. If/when a grid search
     produces an actually-tuned single configuration (post spec 013), that
     tuned value moves private; the registry *shape* (a dict of
     name→factory+grid) stays public.
   - **`signals.py` becomes an interface, not an implementation.** The
     public repo ships the contract — a function that takes a prediction
     series and cost parameters and returns a position/signal series, plus
     a reference implementation (the untuned logistic baseline already
     proven out in spec 014's control comparison) — good enough to prove
     the framework works end-to-end, not good enough to trade. The real,
     edge-bearing signal-generation logic that follows from spec 013's
     multi-ticker expansion and beyond lives in the private companion
     repo, built against the public interface.

### Why this doesn't require new design work today

Spec 012 (cost-aware entry rule, confirmed unblocked 2026-09-08) already
implements this boundary correctly on its own terms, independent of this
amendment: it consumes a prediction series, does not import
`backtest_harness.py` or `estimators.py`, and is scoped estimator-agnostic
(FR-012). The module-boundary table already in `CLAUDE.md` (signal layer
must not know about fills/sizing/accounting) is the same discipline this
amendment asks for — this addendum formalizes an existing practice into an
explicit repo-split requirement, it does not introduce a new one.

**No plug-in scaffolding (abstract base class, private stub package) is
being built yet.** Nothing downstream requires it before spec 013 lands and
the shape of the real signal logic is known. Building that scaffolding now,
ahead of the wall that makes it necessary, would be sequencing out of order
per this project's own project-first principle. What starts now is
discipline only: no tuned parameter, trained checkpoint, or the eventual
production signal implementation gets committed to this tree, even before
the physical two-repo split exists.

### Sequencing

The physical split (second git remote, package versioning, private CI) is
not on the critical path for 012 → 015 → 013 and should not be pulled
forward — doing so now would add two-repo coordination overhead while the
framework itself is still moving fast, for no protective benefit, since
nothing edge-bearing exists in the tree yet (confirmed by the 2026-09-08
grep check: no tracked secrets, no tracked tuned configs). The physical
split happens once `signals.py`'s real implementation is about to be
written — i.e., after spec 013, when multi-ticker signal logic starts
turning into something worth protecting.
