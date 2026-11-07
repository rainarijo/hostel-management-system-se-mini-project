# Part 3 Test Case Document

**Project:** Hostel Management System  
**Date:** 7 November 2026  
**Scope:** Part 3 complaint status update test case, with automated test mapping.

This is a Part 3 addendum to the existing System Test Plan. It records the complaint status update path fixed under issue #81. It does not replace the full System Test Plan.

## TC-15 — Warden updates complaint status

> **TC ID check:** TC-15 is used here as the complaint-status case identifier, based on the current sequence of test IDs in the repository. Confirm it against the approved System Test Plan before final submission.

| Field | Details |
|---|---|
| Requirement | FR-6.3 |
| Actor | Warden assigned to the complaint's hostel |
| Preconditions | An open complaint exists in a hostel assigned to the Warden; the Warden is authenticated. |
| Test type | Browser/page integration test |

### Steps and expected results

| Step | Action | Expected result |
|---|---|---|
| 1 | Open the Complaints page as the assigned Warden. | The complaint is listed and an Update link is available. |
| 2 | Select Update for the open complaint. | The status update form loads successfully and offers permitted next statuses. |
| 3 | Select In Progress, enter a remark, and submit. | The request succeeds and returns to the Complaints page. |
| 4 | Verify the complaint status and remark. | The complaint is stored as In Progress with the submitted remark. |

### Automated test mapping

| TC ID | Automated test name | Result in current run |
|---|---|---|
| TC-15 | `test_warden_can_move_complaint_to_in_progress_through_page` | Pass |

Related FR-6.3 service tests in `apps/complaints/tests/test_issue_27.py` also cover the Open-to-In-Progress transition, invalid transitions, and the required remark.

## Existing complaint creation case

| TC ID | Requirement | Automated test mapping |
|---|---|---|
| TC-13 | FR-6.1, FR-6.2 | `test_tc13_student_with_allocation_can_raise_complaint`; related validation and access tests are named with the `test_tc13_` prefix in `apps/complaints/tests/test_raise_complaint.py`. |

## Execution note

The full Django test run recorded in `docs/reports/unit-test-log.txt` completed with 373 tests passing. The TC-15 numeric identifier should be confirmed against the approved System Test Plan before this addendum is merged.
