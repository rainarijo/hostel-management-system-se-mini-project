# System Test Execution Report

## 1. Document Information

| Field | Details |
|---|---|
| Project | Hostel Management System |
| Document | System Test Execution Report |
| Version | 1.0 |
| Test Environment | GitHub Codespace |
| Framework | Django |
| Test Execution Status | Partially documented |
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
| STE-001 | `python manage.py test` | 371 | 371 | 0 | 0 | 7.281 seconds | PASS |
| STE-002 | `python manage.py check` | N/A | N/A | 0 | 0 | Not recorded | PASS |

The automated test suite completed successfully. Django reported no system check issues. Test output included authorization denial and object-scope security event logs generated during execution.


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

The previously reported automated Django test execution completed with 371 passing tests. Usability testing met its acceptance threshold, and the ZAP baseline reported zero High or Critical findings.

Further evidence is required to confirm the execution status of all system-level and non-functional test cases. Therefore, the overall system test execution is considered partially documented pending final verification.

## 9. Conclusion

The available test evidence indicates that the Hostel Management System has passed the reported automated Django tests and met the specified usability acceptance threshold. Security baseline testing identified no High or Critical findings, although lower-severity findings remain. Additional verification is required for requirements that have not been fully executed or evidenced.
