# System Validation Report

## 1. Document Information

| Field | Details |
|---|---|
| Project | Hostel Management System |
| Document | System Validation Report |
| Version | 1.0 |
| Validation Environment | GitHub Codespace |
| Reference Document | Software Requirements Specification (SRS) |
| Supporting Documents | Software Test Plan, System Test Execution Report, Usability Test Report, DEVIATIONS.md |
| Validation Status | Partially validated |

## 2. Introduction

System validation is performed to determine whether the Hostel Management System satisfies the specified user requirements and intended operational needs.

The validation process evaluates the implemented functionality, security controls, usability, reliability, and other non-functional requirements using the available automated test results, usability test results, security scan findings, and documented implementation deviations.

## 3. Validation Objectives

The objectives of system validation are:

- To verify that the implemented system conforms to the Software Requirements Specification.
- To validate the major functional workflows of the application.
- To assess compliance with the specified non-functional requirements.
- To evaluate the security and access-control mechanisms.
- To identify deviations, limitations, and requirements requiring further verification.
- To determine whether the available evidence supports system acceptance.

## 4. Validation Approach

The following validation activities were considered:

| Validation Activity | Method |
|---|---|
| Functional validation | Automated Django test suite |
| Application configuration validation | Django system check |
| Usability validation | First-time student usability testing |
| Security validation | OWASP ZAP Baseline scan and security-related automated tests |
| Implementation conformance | Review of DEVIATIONS.md |
| Non-functional requirement validation | Review of available test evidence and execution records |

## 5. Validation Results

### 5.1 Functional Requirements

The automated Django test suite executed 371 tests successfully.

| Validation ID | Validation Activity | Evidence | Status |
|---|---|---|---|
| SV-FR-01 | Functional behavior of implemented modules | 371 automated tests passed | PASS |
| SV-FR-02 | Application configuration and system checks | Django system check reported no issues | PASS |
| SV-FR-03 | Role-based access control behavior | Automated tests and authorization-denial logs | PASS for tested scenarios |
| SV-FR-04 | Object-level access restrictions | Automated tests and object-scope denial logs | PASS for tested scenarios |

The results demonstrate successful execution of the automated tests. However, the test count alone does not establish that every individual SRS functional requirement has been validated. Requirement-level confirmation is maintained through the Requirements Traceability Matrix.

### 5.2 Non-Functional Requirements

| Requirement | Validation Evidence | Status |
|---|---|---|
| NFR-PERF-1: Concurrent request performance | No complete performance test result available in the reviewed evidence | NOT VERIFIED |
| NFR-PERF-2: Allocation performance | No measured allocation timing evidence available | NOT VERIFIED |
| NFR-PERF-3: Student search performance | No measured search timing evidence available | NOT VERIFIED |
| NFR-PERF-4: Automatic allocation performance | No complete benchmark evidence available | NOT VERIFIED |
| NFR-PERF-5: Report generation performance | No measured report generation/export timing available | NOT VERIFIED |
| NFR-SAFE-1: Backup and restore | Scripts and timers documented; production/CI execution not performed | PARTIALLY VERIFIED |
| NFR-SAFE-2: Gender compatibility during allocation | Requires requirement-specific execution evidence | NOT VERIFIED |
| NFR-SAFE-3: Reversible soft deletion | Requires requirement-specific execution evidence | NOT VERIFIED |
| NFR-SAFE-4: Printable resident list | Requires usability and click-count evidence | NOT VERIFIED |
| NFR-USE-1: Usability | 8 out of 10 participants met the 300-second completion target | PASS |
| NFR-USE-2: Accessibility | No complete WCAG 2.1 AA validation report available | NOT VERIFIED |
| NFR-AVL-1: Availability | No monthly availability measurement available | NOT VERIFIED |
| NFR-REL-1: Data consistency | Consistency check tested in CI; full nightly operational execution not evidenced | PARTIALLY VERIFIED |
| NFR-MNT-1: Maintainability and coverage | Coverage threshold and flake8 results require consolidated evidence | NOT VERIFIED |
| NFR-PORT-1: Browser compatibility | No complete browser and viewport compatibility results available | NOT VERIFIED |
| NFR-SCL-1: Scalability | No complete 5000-student scalability benchmark available | NOT VERIFIED |

### 5.3 Security Requirements

OWASP ZAP Baseline testing reported zero High and Critical findings. Lower-severity findings were reported.

| Security Validation | Evidence | Status |
|---|---|---|
| Role-based access control | Automated authorization tests | PASS for tested scenarios |
| Object-level access restrictions | Automated scope-check tests | PASS for tested scenarios |
| Security event logging | Authorization-denial and object-scope event logs | PASS for tested scenarios |
| OWASP ZAP baseline | 0 High, 0 Critical findings | PASS for severity threshold |
| Password hashing requirements | Requires implementation-specific verification | NOT VERIFIED |
| Password policy enforcement | Requires requirement-specific verification | NOT VERIFIED |
| HTTPS and HSTS configuration | Requires deployed-environment evidence | NOT VERIFIED |
| Session security | Requires requirement-specific verification | NOT VERIFIED |
| CSRF and XSS protections | ZAP baseline findings remain; complete validation required | PARTIALLY VERIFIED |
| Login and password-reset rate limiting | Requires requirement-specific verification | NOT VERIFIED |
| Audit logging completeness and retention | Requires requirement-specific verification | NOT VERIFIED |
| File upload restrictions | Requires requirement-specific verification | NOT VERIFIED |
| Secret management | Requires repository and environment configuration verification | NOT VERIFIED |
| Student data export restrictions | Requires requirement-specific verification | NOT VERIFIED |

The absence of High and Critical ZAP findings does not establish complete compliance with all security requirements.

### 5.4 Usability Validation

NFR-USE-1 requires first-time student users to complete a room application within 300 seconds, with a minimum completion rate of 80%.

| Metric | Result |
|---|---|
| Participants | 10 |
| Participants meeting target | 8 |
| Participants requiring assistance | 2 |
| Completion rate | 80% |
| Required completion rate | 80% |
| Validation result | PASS |

The usability acceptance threshold was met. The test report identifies difficulties involving roommate SRN clarity and locating the room application link.

## 6. Implementation Deviations

The following deviations are documented in `docs/DEVIATIONS.md`:

| Deviation | Description | Validation Impact |
|---|---|---|
| Entity naming | `Payment` and `MasterStudent` are used instead of SAD entity names | Naming deviation; fields are reported as equivalent |
| Failed-login tracking | Failed-login counters are maintained in the User model | Behavior requires validation against FR-1.5 |
| Service-layer implementation | Service layers were introduced incrementally | No direct validation failure established |
| TC-10 concurrency test | Database race condition simulated through pre-check patching | Does not constitute a real concurrent-thread test |
| Backup and restore | Scripts and timers were not executed in CI or production | Operational backup and restoration remain unverified |

## 7. System Test Case (STC) Validation Results

The following system test case mappings are based on the available test plan and RTM references. The overall automated Django test suite completed with 371 passing tests, 0 failures, and 0 errors. Individual STC execution evidence is not separately consolidated for every test case.

| STC ID | Mapped Test Cases | Validation Area | Result |
|---|---|---|---|
| STC-01 | TC-01, TC-02, TC-03 | Account and authentication functionality | Automated suite passed; individual STC result requires confirmation |
| STC-02 | TC-05, TC-06 | Student-related functionality | Automated suite passed; individual STC result requires confirmation |
| STC-03 | TC-07 | Requirement-specific functional workflow | Automated suite passed; individual STC result requires confirmation |
| STC-04 | TC-08, TC-09, TC-10, TC-11, TC-16 | Allocation and related workflows | Automated suite passed; TC-10 concurrency behavior simulated |
| STC-05 | TC-12 | Requirement-specific functional workflow | Automated suite passed; individual STC result requires confirmation |
| STC-06 | TC-13 | Requirement-specific functional workflow | Automated suite passed; individual STC result requires confirmation |
| STC-07 | TC-14, TC-15 | Requirement-specific functional workflow | Automated suite passed; individual STC result requires confirmation |
| STC-08 | TC-04, TC-19, TC-20, TC-21, TC-22 | Security and access control | Automated tests passed for tested scenarios; ZAP findings remain under review |
| STC-09 | TC-17 | Performance validation | NOT VERIFIED |
| STC-10 | TC-18 | Backup and recovery | PARTIALLY VERIFIED |
| STC-11 | TC-23 | Usability validation | PASS; 80% completion rate achieved |

The functional STC results above are associated with the overall automated suite result. They should not be interpreted as independently executed system-level test results until the detailed test execution records are reviewed.

## 8. Open Defects and Outstanding Findings

### 8.1 Application Security Audit Findings

The security audit documented the following issues in `docs/SECURITY_AUDIT.md`. These findings were audited on 30-10-2026 against `main` at commit `17fa075`. The audit states that the identified issues were not fixed within the audited issue.

| Finding ID | Description | Severity | Owner | Status |
|---|---|---|---|---|
| S-1 | Student profile detail and edit views return 403 for another student's profile instead of 404, allowing profile ID existence inference | Medium | Prema | Open per audit |
| A-1 | Account role-change and deactivation routes return 405 for unauthorized GET requests without role-denial logging | Low | Prema | Open per audit |
| R-1 | Room availability API scope denials are not logged as centralized security events | Low | Praakruthi | Open per audit |
| R-2 | Warden room index includes deactivated hostels in its scope | Low | Praakruthi | Open per audit |
| C-1 | Complaint warden scope includes deactivated hostels | Low | Ojas | Open per audit |
| C-2 | Complaint status and reopen routes return 404 for GET instead of 405 | Low | Ojas | Open per audit |
| F-1 | Fee payment and receipt views return 403 instead of 404 for out-of-scope objects, potentially revealing sequential receipt existence | Medium | Ojas | Open per audit |
| N-1 | Administrators are denied announcement posting although BR-1 specifies Warden and Administrator access | Medium | Ojas | Open per audit |
| AL-1 | Allocation active-allocation and check-out functionality is Warden-only, while BR-1 lists Warden and Administrator access | Not specified | Raina | Open per audit |

### 8.2 Security Audit Summary

| Severity | Findings | Status |
|---|---:|---|
| Medium | 3 | Open per audit |
| Low | 5 | Open per audit |
| Not specified | 1 | Open per audit |
| Total | 9 | Requires review and resolution confirmation |

The findings represent authorization behavior, scope enforcement, HTTP status-code consistency, logging, and role-permission gaps. The audit states that the identified issues do not currently expose data outside the user's role or scope, but some findings may disclose object existence or differ from the specified role matrix.

### 8.3 ZAP Baseline Findings

The previously recorded OWASP ZAP Baseline result reported:

| Severity | Findings |
|---|---:|
| Informational | 5 |
| Low | 6 |
| Medium | 1 |
| High | 0 |
| Critical | 0 |

The ZAP baseline findings and the application security audit findings are separate inventories. The ZAP results should not be combined with the nine application audit findings because they represent different assessments.

### 8.4 SEC-REQ-10 Secret Management

The security audit reported the following checks:

- Environment variables are used for application secrets and configuration.
- `.env` is not tracked in Git and is ignored by `.gitignore`.
- No `.env` file was found in Git history.
- `.env.example` contains placeholder values.
- The local development placeholder secret is rejected when DEBUG is disabled.

**Validation Result:** PASS for the checks documented in the security audit.

### 8.5 Outstanding Actions

1. Resolve or formally accept the S-1 and F-1 Medium findings.
2. Review and resolve the N-1 role-permission gap.
3. Review the Low severity findings A-1, R-1, R-2, C-1, and C-2.
4. Confirm the intended Administrator permissions for AL-1.
5. Update the security audit and defect register after remediation.
6. Re-run relevant tests after fixes and attach execution evidence.

The findings remain classified as open per the reviewed audit unless updated remediation evidence is provided.
