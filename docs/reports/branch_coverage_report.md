# Part 3 – Branch Coverage Report

| Item | Value |
|------|-------|
| Date | 2026-11-08 |
| Tool | coverage.py 7.17.2 (branch coverage enabled) |
| Command | `python -m coverage run manage.py test` |
| Scope | `apps/` (source = `apps`); `*/migrations/*` and `*/tests/*` omitted |
| Source data | [coverage.txt](coverage.txt), [coverage.json](coverage.json) |
| HTML report | [coverage_html/index.html](coverage_html/index.html) |

## 1. Overall Branch Coverage

| Metric | Count | Percentage |
|--------|------:|-----------:|
| Total branches | 828 | — |
| Missing branches | 196 | — |
| Covered branches | 632 | — |
| Partially covered lines (`BrPart`) | 140 | — |
| Branch coverage | 632 of 828 | **76.33%** |

Branch coverage is calculated as `(total branches - missing branches) / total branches * 100`, or `(828 - 196) / 828 * 100 = 76.33%`. `BrPart` is reported separately: it counts lines with an executed branch whose possible outcomes are not all covered; it is not the count of wholly missing branches.

The overall figures agree with the `TOTAL` row in [coverage.txt](coverage.txt): 828 branches and 140 `BrPart`. The JSON report records 632 covered branches and 196 missing branches.

## 2. Branch Coverage per App

| App | Total branches | Missing branches | BrPart | Branch coverage |
|-----|---------------:|-----------------:|-------:|----------------:|
| accounts | 84 | 22 | 20 | 73.81% |
| allocation | 244 | 57 | 49 | 76.64% |
| complaints | 34 | 9 | 5 | 73.53% |
| core | 66 | 25 | 5 | 62.12% |
| fees | 58 | 31 | 13 | 46.55% |
| notifications | 32 | 7 | 7 | 78.13% |
| reports | 72 | 7 | 7 | 90.28% |
| rooms | 154 | 26 | 24 | 83.12% |
| students | 84 | 12 | 10 | 85.71% |
| **Total** | **828** | **196** | **140** | **76.33%** |

## 3. Five Files with the Most Partially Covered Branches

The files below are ranked by `BrPart` from the `coverage.txt` report. The explanations summarize the source conditions associated with the partial branches; `BrPart` is distinct from the missing-branch counts.

| # | File | BrPart | What is not fully covered |
|---|------|-------:|---------------------------|
| 1 | `apps/allocation/services.py` | 34 | Partial branches span allocation scope and eligibility checks, integrity-error handling, and room-change request validation such as existing requests, confirmed-allocation eligibility, and destination-bed availability. |
| 2 | `apps/rooms/views.py` | 12 | Partial branches include successful versus unsuccessful hostel/room saves, active versus inactive and allocated versus unallocated deactivation paths, and availability filtering/response paths for different roles and inputs. |
| 3 | `apps/accounts/views.py` | 11 | Partial branches include authenticated-user redirects, password-reset rate-limit and account/token outcomes, and account-role/deactivation safeguards for the last active administrator. |
| 4 | `apps/allocation/views.py` | 9 | Partial branches include profile/form handling for application and room-change submissions, pending-status checks, and invalid or rejected allocation/decision outcomes. |
| 5 | `apps/fees/services.py` | 9 | Partial branches include staff authorization and hostel scope, allocation/fee-record and duplicate-submission outcomes, and payment amount, mode, reference, and date validation. |

## 4. HTML Report

The line-by-line HTML report is at [coverage_html/index.html](coverage_html/index.html).
