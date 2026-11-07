# Part 3 Test Case Document

**Project:** Hostel Management System  
**Date:** 7 November 2026  
**Scope:** Part 3 complaint management test case updates.

This addendum records the complaint status update scenario covered by the Part 3 fix to issue #81. It supplements the existing System Test Plan.

## TC-13 — Complaint management

**Requirements:** FR-6.1, FR-6.2, FR-6.3  
**Actors:** Student; Warden assigned to the complaint's hostel.

### Existing complaint creation scenario

| Field | Details |
|---|---|
| Preconditions | Student is authenticated and has an active room allocation. |
| Action | Student submits a complaint with a valid category and description. |
| Expected result | Complaint is created for the student's active room with an Open status and a unique complaint number. |
| Automated tests | `test_tc13_student_with_allocation_can_raise_complaint` and related `test_tc13_` tests in `apps/complaints/tests/test_raise_complaint.py`. |

### Part 3 scenario — Warden updates complaint status

| Field | Details |
|---|---|
| Preconditions | An Open complaint exists in a hostel assigned to the Warden; the Warden is authenticated. |
| Automated test | `test_warden_can_move_complaint_to_in_progress_through_page` in `apps/complaints/tests/test_issue_27.py`. |

| Step | Action | Expected result |
|---|---|---|
| 1 | Open the Complaints page as the assigned Warden. | The complaint is listed and an Update link is available. |
| 2 | Select Update for the Open complaint. | The status update form loads successfully and offers permitted next statuses. |
| 3 | Select In Progress, enter a remark, and submit. | The request succeeds and returns to the Complaints page. |
| 4 | Verify the complaint status and remark. | The complaint is stored as In Progress with the submitted remark. |

### Traceability note

The repository copy of `STP_Hostel_Management_System.pdf` maps HMS-F-060 (Complaint management) to TC-13 and HMS-F-050 (Dashboards, reports and exports) to TC-15. The STP cover labels that copy “Sample”; confirm the TC-13 mapping against the approved System Test Plan before final submission.
