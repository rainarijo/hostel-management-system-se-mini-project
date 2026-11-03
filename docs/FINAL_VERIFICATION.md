# Final Performance and Report Verification



**Documentation update date:** 2 November 2026
**Project:** Hostel Management System
**Branch:** `docs/final-perf-and-reports`



## 1. Issue #16 — Dashboards and Reports



### Test environment



- Application: Local Django development server
- Database: SQLite
- Data: Synthetic sample data generated using `seed_data`
- Tested using Administrator and Warden accounts



### 1.1 Report verification results



| Report | Data/Figures | CSV Export | PDF Export | Result |

|---|---|---|---|---|

| Occupancy Report | Verified | Pass | Pass | Pass |

| Resident List | Verified | Pass | Pass | Pass |

| Fee Dues Report | Verified | Pass | Pass | Pass |

| Complaint Summary | Empty-state verified | Pass | Pass | Pass |



### 1.2 Observations



**Occupancy Report**

- 2 hostels, 12 rooms and 24 beds.
- 2 occupied beds and 22 vacant beds.
- Overall occupancy: approximately 8.33%.
- Room-level occupancy figures were checked.
- Date-range filtering tested for 31 October 2026 to 1 November 2026.



**Resident List**

- 2 allocated residents appeared in the report.
- Student, hostel, room, bed and allocation details were checked.
- CSV and PDF contents matched.



**Fee Dues Report**

- 2 fee records appeared.
- Cauvery Block: annual fee ₹75,000, paid ₹0, balance ₹75,000.
- Kabini Block: annual fee ₹60,000, paid ₹0, balance ₹60,000.
- CSV and PDF contents matched.



**Complaint Summary**

- No complaints existed in the synthetic sample dataset.
- Only the empty state was verified; a populated complaint report was not available to test.
- Empty-state message displayed correctly.
- CSV and PDF exports handled the empty result correctly.



### 1.3 Role-based access verification



| Role | Verified access |

|---|---|

| Administrator | All authorized hostels |

| Boys' Warden | Cauvery Block only |

| Girls' Warden | Kabini Block only |



Both Warden accounts were checked independently, and hostel-level report restrictions behaved as expected.



### 1.4 Export and filter verification



- All four report pages opened successfully.
- All eight CSV/PDF exports downloaded and were opened.
- Exported contents were checked against displayed report data.
- The Occupancy Report date filter was tested for 31 October 2026 to 1 November 2026.



### 1.5 Issue #16 conclusion



All four reports passed the local functional verification using synthetic sample data. CSV/PDF exports and the tested role-based hostel restrictions worked as expected.



**Limitation:** Verification used local SQLite and synthetic data, not a production PostgreSQL deployment.



## 2. Issue #18 — Performance and Scalability

### Benchmark execution

**Execution date:** 1 November 2026

The following 10-user Locust run was executed as an exploratory local test:

| Setting | Value |
|---|---|
| Environment | Windows developer laptop |
| Application server | Django development server (`python manage.py runserver`) |
| Database | SQLite |
| Locust | 2.47.0 |
| Concurrent users | 10 |
| Spawn rate | 2 users/second |
| Duration | 60 seconds |
| Workload | `pages` |
| `HMS_SERVER_TIMING` | `1` |
| `HMS_LOADTEST_MODE` | `pages` |

### Results

| Metric | Target | Actual result | Status |
|---|---|---|---|
| Measured page requests | — | 114 | Recorded |
| Total Locust requests, including setup/login | — | 134 | Recorded |
| Failed requests overall | 0 | 1 (0.75%) | Failed |
| Client p95 response time | ≤ 2,000 ms | 3,100 ms | **Not met** |
| Client maximum response time | ≤ 5,000 ms | 4,842 ms | Below target in this run only |
| Django server p95 response time | — | 3,100 ms | Recorded |
| Django server maximum response time | — | 4,659 ms | Recorded |
| Locust exit code | 0 | 1 | **Failed run** |

The page p95 target of ≤ 2,000 ms was not met. Although the observed maximum was below 5,000 ms, the run failed; this single run does not establish that the maximum target is reliably met.

### Failure investigation

Locust's error report identifies one failed request as `POST Setup login`, returning HTTP 400. Separately, the Django server log records an HTTP 400 on `GET /dashboard/student/`: `sqlite3.OperationalError: database is locked` occurred during database-backed session saving, followed by `SessionInterrupted`. The available evidence does not establish that the server-side dashboard exception is the same request as Locust's failed login request.

Configuration inspection confirmed that the run used SQLite, Django's database-backed session default, and `SESSION_SAVE_EVERY_REQUEST = True`. SQLite session-write contention is confirmed in the server log and explains the logged locking failure. This was not a CSRF failure.

### Test status and limitations

- The 10-user run is a failed exploratory local test, not a successful performance acceptance test.
- The planned 200-user, 5-minute performance test was **not completed**.
- Individual-allocation and 500-application auto-allocation workloads were **not run**; their performance targets were **not verified** in this final run.
- Results from SQLite and Django's development server are indicative only and are not representative of the intended PostgreSQL/Gunicorn deployment environment.

### Issue #18 conclusion

Issue #18 performance targets have not been fully verified or shown to be met. The local 10-user exploratory run failed, and the 200-user benchmark and allocation-specific benchmarks remain not run in this final verification.
