# Deviations from the submitted SRS, SAD and Test Plan

Add one line per deviation (what changed, why, which document). These are explained at the final demo.

- Sprint 1 foundation: the SAD names the fee payment entity FEE_PAYMENT and the master list entity MASTER_LIST_ENTRY; the code uses `Payment` and `MasterStudent` (names kept from the skeleton, same fields).
- Sprint 1 foundation: failed-login counting lives on the User model (`failed_login_count`, `locked_until`) instead of a separate AUTH_ATTEMPT table (SAD 4.1.2). Same behaviour for FR-1.5.
- Sprint 1 foundation: service layers (`services.py`) are added feature by feature as each issue is built, not all at once.
