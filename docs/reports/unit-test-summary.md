# Unit Test Summary — Part 3

**Date:** 7 November 2026  
**Command:** `python manage.py test -v 2`  
**Detailed log:** `docs/reports/unit-test-log.txt`

## Overall result

- **373 tests passed** in 7.437 seconds.
- Django system checks reported no issues.
- Django used an in-memory SQLite test database for this run.

## Results by app

| App | Tests run | TC IDs explicitly present in test names/docstrings |
|---|---:|---|
| accounts | 47 | TC-02, TC-03 |
| allocation | 146 | TC-08, TC-09, TC-10, TC-11 |
| complaints | 18 | TC-13; TC-15 for the Part 3 status-page test (confirm the numeric ID against the approved Test Plan); FR-6.3, FR-6.4, FR-6.5 service coverage |
| core | 42 | TC-04, TC-20 |
| fees | 18 | TC-14 |
| notifications | 18 | TC-16, TC-31 |
| reports | 8 | No TC ID explicitly present in the test names/docstrings |
| rooms | 36 | No TC ID explicitly present in the test names/docstrings |
| students | 40 | No TC ID explicitly present in the test names/docstrings |
| **Total** | **373** | |

## Mapping note

TC IDs above come from the current automated test names and file-level test-plan docstrings. Tests without an explicit TC ID remain unmapped here; cross-reference them with the approved System Test Plan before treating this as a complete traceability mapping. The complaint status page test is `test_warden_can_move_complaint_to_in_progress_through_page` in `apps/complaints/tests/test_issue_27.py`.
