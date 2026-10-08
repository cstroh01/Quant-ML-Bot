# Plan: 053
Module `scripts/model_registry.py` (manifest, registry, promotion records; no order code).
- **U1** manifest schema + verified load (FR-001).
- **U2** fold-local training wrapper over existing `walk_forward_cv`/`model_cv` contracts (FR-002), synthetic data.
- **U3** champion/challenger registry, promotion decision reading immutable evidence, rollback (FR-005/006/007).
- **U4** offline evaluation pipeline with costed baselines (FR-003/004) — after 046/033 acceptance.
- **U5** (`exec/`, reviewed) paper loop consumes the approved champion; SMA stays comparator.
