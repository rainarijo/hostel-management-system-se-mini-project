# Part 3 – Code Coverage Report

| Item | Value |
|------|-------|
| Date | 2026-11-08 |
| Tool | coverage.py 7.17.2 (branch coverage enabled) |
| Command | `python -m coverage run manage.py test` |
| Scope | `apps/` (source = `apps`); `*/migrations/*` and `*/tests/*` omitted |
| Source data | [coverage.txt](coverage.txt), [coverage.json](coverage.json) |
| HTML report | [coverage_html/index.html](coverage_html/index.html) |

## 1. Overall Coverage

| Metric | Covered | Total | Coverage |
|--------|--------:|------:|---------:|
| **Statements** | 3,154 | 3,488 (334 missed) | **90.42%** |
| Branches | 632 | 828 (196 missed, 140 partial) | 76.33% |
| Combined (statements + branches, `TOTAL` line in coverage.txt) | – | – | 87.72% (displayed as 88%) |

`TOTAL` line from coverage.txt:

```
TOTAL    3488    334    828    140    88%
```

The 88% in the `TOTAL` line is the combined statement and branch figure that coverage.py reports when branch coverage is on. Statement coverage alone is 90.42%, calculated as (3488 − 334) / 3488.

## 2. Coverage per App

| App | Statements | Missed | Statement Coverage |
|-----|-----------:|-------:|-------------------:|
| accounts | 380 | 27 | 92.89% |
| allocation | 989 | 107 | 89.18% |
| complaints | 195 | 18 | 90.77% |
| core | 382 | 68 | 82.20% |
| fees | 251 | 47 | 81.27% |
| notifications | 215 | 9 | 95.81% |
| reports | 220 | 7 | 96.82% |
| rooms | 503 | 32 | 93.64% |
| students | 353 | 19 | 94.62% |
| **Total** | **3,488** | **334** | **90.42%** |

## 3. NFR-MNT-1 Compliance

> **NFR-MNT-1:** Automated unit tests shall cover at least 70% of statements in the allocation, fee and access-control modules.

| Module | Files | Statements | Missed | Statement Coverage | Target | Result |
|--------|-------|-----------:|-------:|-------------------:|-------:|:------:|
| Allocation | `apps/allocation/` | 989 | 107 | 89.18% | 70% | **Met** |
| Fees | `apps/fees/` | 251 | 47 | 81.27% | 70% | **Met** |
| Access control | `apps/core/permissions.py` + `apps/accounts/` | 434 | 28 | 93.55% | 70% | **Met** |

Breakdown of the access-control row: `apps/core/permissions.py` has 54 statements with 1 missed (98.15%), and `apps/accounts/` has 380 statements with 27 missed (92.89%).

All three modules meet NFR-MNT-1. Two fee files fall below 70% on their own (see Section 4), but the requirement is measured at module level.

## 4. Five Files with the Lowest Statement Coverage

Files with zero statements are left out.

| # | File | Statements | Missed | Statement Coverage | What is untested |
|---|------|-----------:|-------:|-------------------:|------------------|
| 1 | `apps/core/management/commands/seed_data.py` | 56 | 56 | 0.00% | The development sample-data command (lines 6–96) never runs during the test suite. |
| 2 | `apps/fees/forms.py` | 26 | 13 | 50.00% | `PaymentForm.clean_paid_on` (rejecting future dates) and `clean` (requiring a transaction reference for non-cash payments) are never called (lines 41–44, 47–60). |
| 3 | `apps/fees/views.py` | 73 | 24 | 67.12% | The Warden/Admin fee list (26–43), the payment-recording form handling (70–107) and the Student/Warden receipt access checks (129–133) are not tested. |
| 4 | `apps/accounts/validators.py` | 7 | 2 | 71.43% | The `LetterAndDigitValidator` rejection path (line 9) and `get_help_text` (line 13) are not tested. |
| 5 | `apps/complaints/views.py` | 65 | 14 | 78.46% | The Admin branch of `_warden_scope` (26), the invalid-transition error on status update (99–100) and the student `reopen` view body (127–143) are not tested. |

Missing line numbers come from the `Missing` column of [coverage.txt](coverage.txt).

## 5. HTML Report

The line-by-line HTML report is at [coverage_html/index.html](coverage_html/index.html).
