# Requirements Traceability Matrix (RTM)

## 1. Document Information

| Field | Details |
|---|---|
| Project | Hostel Management System |
| Document | Requirements Traceability Matrix |
| Version | 1.0 |
| Reference | Software Requirements Specification (SRS) |
| Supporting Documents | Software Test Plan, System Test Execution Report, System Validation Report |
| Status | In Progress |

## 2. Purpose

The Requirements Traceability Matrix establishes traceability between the requirements specified in the SRS, corresponding test cases, system test cases, and available execution evidence.

The RTM is maintained to ensure that requirements are covered by testing and that their verification status is recorded accurately.

## 3. Functional Requirements Traceability

| SRS Requirement | Test Case ID | System Test Case ID | Execution Evidence | Status |
|---|---|---|---|---|
| FR-1.1 / FR-1.2 | TC-01 | STC-01 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-1.3 / FR-1.5 | TC-02, TC-03 | STC-01 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-1.4 | TC-04 | STC-08 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-2.1 – FR-2.3 | TC-05 | STC-02 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-2.5 / FR-2.6 | TC-06 | STC-02 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-3.2 – FR-3.4 | TC-07 | STC-03 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-4.2 / FR-4.3 | TC-08 | STC-04 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-4.5 / FR-4.6 | TC-09, TC-10 | STC-04 | Django automated test suite; TC-10 concurrency simulation | Executed; TC-10 simulated |
| FR-4.7 | TC-11 | STC-04 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-5.2 | TC-12 | STC-05 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-6.1 – FR-6.3 | TC-13 | STC-06 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-7.2 – FR-7.4 | TC-14 | STC-07 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-8.2 / FR-8.3 | TC-15 | STC-07 | Django automated test suite | Executed; requirement-level result to confirm |
| FR-9.1 / FR-9.2 | TC-16 | STC-04 | Django automated test suite | Executed; requirement-level result to confirm |

## 4. Non-Functional Requirements Traceability

| Requirement ID | Test Case ID | System Test Case ID | Evidence | Status |
|---|---|---|---|---|
| NFR-PERF-1 | TC-17 | STC-09 | Performance benchmark pending | NOT VERIFIED |
| NFR-SAFE-1 | TC-18 | STC-10 | Backup/restore scripts and consistency check; production restore not executed | PARTIALLY VERIFIED |
| SEC-REQ-1 / SEC-REQ-2 | TC-19 | STC-08 | Automated tests; detailed requirement-level evidence pending review | TO CONFIRM |
| SEC-REQ-4 | TC-20 | STC-08 | Authorization and scope-check test output | PASS FOR TESTED SCENARIOS |
| SEC-REQ-6 | TC-21 | STC-08 | ZAP baseline and automated test evidence | PARTIALLY VERIFIED |
| SEC-REQ-8 | TC-22 | STC-08 | Audit-related test evidence; retention/completeness review pending | TO CONFIRM |
| NFR-USE-1 | TC-23 | STC-11 | Usability Test Report: 8/10 participants met target | PASS |

## 5. Test Execution Summary

| Metric | Result |
|---|---|
| Automated Django Tests | 371 |
| Passed | 371 |
| Failed | 0 |
| Errors | 0 |
| Execution Duration | 7.281 seconds |
| Django System Check | No issues |
| Usability Acceptance Threshold | Met |
| ZAP High/Critical Findings | 0 |

## 6. Traceability Limitations

1. The test case identifiers and mappings are based on the available test plan and previously identified RTM mapping references.
2. The complete test case inventory and requirement-specific assertions must be reviewed before marking every functional requirement as PASS.
3. Several non-functional requirements have no measured execution evidence.
4. TC-10 concurrency testing uses a simulated race condition rather than real concurrent threads.
5. Backup and restore execution in a production environment remains pending.

## 7. Conclusion

The RTM establishes an initial mapping between the SRS requirements and available test case references. The automated Django test suite has passed all 371 tests. However, the RTM remains in progress until requirement-specific test results are reviewed and the pending non-functional requirements are verified.

## 8. Security Audit Finding Traceability

| Finding ID | Related Requirement | Test Reference | Severity | Current Status |
|---|---|---|---|---|
| S-1 | SEC-REQ-4 | TC-20 / IDOR tests | Medium | Open per audit |
| A-1 | SEC-REQ-4 | TC-20 / Role Matrix tests | Low | Open per audit |
| R-1 | SEC-REQ-4 / Accountability | TC-20 / Security Logging tests | Low | Open per audit |
| R-2 | SEC-REQ-4 | TC-20 / Scope validation | Low | Open per audit |
| C-1 | SEC-REQ-4 | TC-20 / Scope validation | Low | Open per audit |
| C-2 | SEC-REQ-4 | TC-20 / HTTP method validation | Low | Open per audit |
| F-1 | SEC-REQ-4 | TC-20 / IDOR tests | Medium | Open per audit |
| N-1 | BR-1 | Role Matrix tests | Medium | Open per audit |
| AL-1 | BR-1 | Allocation access-control tests | Not specified | Open per audit |

The audit findings are recorded separately from automated test pass/fail results. The presence of passing automated tests does not imply that these audit findings have been remediated.
