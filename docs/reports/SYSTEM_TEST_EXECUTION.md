# System Test Execution Report

## 1. Document Information

| Field | Details |
|---|---|
| Project | Hostel Management System |
| Document | System Test Execution Report |
| Version | 1.0 |
| Test Environment | GitHub Codespace |
| Framework | Django |
|Test Execution Status | Executed with limitations
| Reference Documents | SRS, Software Test Plan, SAD |

## 2. Test Objective

The objective of system test execution is to verify that the Hostel Management System satisfies the functional and non-functional requirements specified in the Software Requirements Specification (SRS). Testing is performed to validate the application's functionality, security, usability, reliability, and correctness.

## 3. Test Environment

| Component | Details |
|---|---|
| Development Environment | GitHub Codespace |
| Application Framework | Django |
| Database | SQLite for development and automated testing |
| Testing Framework | Django Test Framework |
| Security Testing Tool | OWASP ZAP Baseline |
| Source Control | GitHub |

## 4.1 Automated Test Execution Log

| Execution ID | Command | Tests Executed | Passed | Failed | Errors | Duration | Result |
|---|---|---:|---:|---:|---:|---:|---|
| STE-001 | `python manage.py test` | 373 | 373 | 0 | 0 | 8.091 | PASS |
| STE-002 | `python manage.py check` | N/A | N/A | 0 | 0 | Not recorded | PASS |
Automated Test Suite: 373 tests passed
Execution Time: 8.091 seconds
Django System Check: Passed

The automated test suite completed successfully. Django reported no system check issues. Test output included authorization denial and object-scope security event logs generated during execution.

## 4.2 Manual System Test Execution Log

| Test Case ID | Test Scenario | Expected Result | Actual Result | Status | Evidence |
|---|---|---|---|---|---|
| STC-01 | Student registration and email verification | Eligible student can register and verify email | Registration and verification completed successfully | PASS  | [Evidence](evidence/STC-01/) |
| STC-02 | Student profile functionality | Student can view and update profile | Profile updated successfully | PASS | [Evidence](evidence/STC-02/) |
| STC-03 | Student room application | Application eligibility is displayed correctly | Application window was closed; application submission unavailable | BLOCKED / NOT FULLY VERIFIED | [Evidence](evidence/STC-03/) |
| STC-04 | Allocation history and fees | Allocation history and fee information are displayed | No allocation history or dues displayed for the test student | PASS* | [Evidence](evidence/STC-04/) |
| STC-05 | Fee functionality | Fee information is accessible to the student | Fee page displayed no dues because the student had no allocation | PASS* | [Evidence](evidence/STC-05/) |
| STC-06 | Complaint functionality | Complaint eligibility is enforced | Complaint creation unavailable without active room allocation | PASS* | [Evidence](evidence/STC-06/) |
| STC-07 | Room change functionality | Room change eligibility is enforced | Room change request unavailable without confirmed allocation | PASS* | [Evidence](evidence/STC-07/) |
| STC-08 | Role-based access control | Student cannot access Warden dashboard | Access denied message displayed | PASS | [Evidence](evidence/STC-08/) |
| STC-09 | Performance testing | Dashboard loads within the defined threshold | Dashboard network finish time recorded as approximately 1.38 seconds; formal load testing was not performed | PASS - Provisional | [Evidence](evidence/STC-09/) || STC-10 | Backup and recovery | Database backup can be restored successfully | Backup integrity and restoration integrity checks returned `ok` | PASS | [Evidence](evidence/STC-10/) |
| STC-11 | Usability testing | Users complete tasks within the specified time | 8 out of 10 participants completed within 300 seconds (80%) | PASS* | [Evidence](evidence/STC-11/) |


## 5. Usability Test Execution

The usability test evaluated whether first-time student users could complete a room application within 300 seconds.

| Metric | Result |
|---|---|
| Total Participants | 10 |
| Participants Meeting Target | 8 |
| Participants Requiring Assistance | 2 |
| Completion Rate | 80% |
| Acceptance Threshold | 80% |
| Result | Threshold Met |

The two participants requiring assistance encountered difficulties related to roommate SRN clarity and locating the room application link.

## 6. Security Test Execution

OWASP ZAP Baseline testing was performed against the application.

| Severity | Findings |
|---|---:|
| Informational | 5 |
| Low | 6 |
| Medium | 1 |
| High | 0 |
| Critical | 0 |

The scan reported no High or Critical findings. However, lower-severity findings remain and require review. The scan result does not establish that all security requirements have been satisfied.

## 7. Test Execution Limitations

The following deviations and limitations were identified:

1. The implementation uses `Payment` and `MasterStudent` entities instead of the names specified in the SAD.
2. Failed-login counting is maintained through the User model fields `failed_login_count` and `locked_until`.
3. Service layers were introduced incrementally during feature implementation.
4. TC-10 concurrency testing simulates the database constraint race instead of using concurrent threads.
5. Backup and restore scripts and systemd timers were not executed in CI or on a production VM.

## 8. Overall Test Execution Status

System testing was performed through automated Django test execution, manual browser-based system test cases, usability testing, security testing, and database backup and recovery verification.

The automated test suite completed successfully with 373 passing tests in the previously recorded execution. The Django system check reported no issues. Usability testing achieved an 80% completion rate, meeting the specified acceptance threshold. OWASP ZAP Baseline testing reported no High or Critical findings.

Manual browser testing verified student registration, profile management, role-based access restrictions, allocation and fee empty-state handling, complaint eligibility, and room change eligibility. Database backup and restoration procedures were also executed successfully with integrity checks returning `ok`.

Some test cases remain partially verified due to the absence of an active room allocation, the closed application window, and the lack of formal load-based performance testing.

Therefore, the overall system test execution is considered **executed with limitations**, with individual test results documented according to the evidence available.

## 9. Conclusion

The available test evidence indicates that the Hostel Management System has passed the reported automated Django tests and met the specified usability acceptance threshold. Security baseline testing identified no High or Critical findings, although lower-severity findings remain. Additional verification is required for requirements that have not been fully executed or evidenced.
