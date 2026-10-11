# Hostel Management System (HMS)

A Software Engineering mini-project by Group 3, Department of Computer Science and Engineering, PES University, Bengaluru.

## Overview

The Hostel Management System (HMS) is a proposed web-based application designed to simplify hostel administration by centralizing student information, room inventory, room applications, bed allocation, fee records, complaints, and reporting.

The system aims to replace manual processes involving paper forms, registers, and spreadsheets with a centralized application that provides students, wardens, and administrators with role-specific functionality and access to relevant information.

## Objectives

- Simplify student registration and profile management.
- Manage hostels, rooms, room applications, and bed allocation.
- Prevent duplicate bed allocations through database constraints and transaction management.
- Support room changes, student check-out, and allocation history.
- Track hostel fees, payment records, and receipts.
- Manage complaints and maintenance requests.
- Provide dashboards, reports, and data exports.
- Support notifications and hostel announcements.
- Protect student information through role-based access control, validation, and auditing.

## Functional Modules

The system is organized into eight primary modules and shared services.

| Module | Description |
|---|---|
| Authentication and Access Control | Registration, email verification, login, password reset, session management, and role-based permissions. |
| Student Profile Management | Student profiles, personal and academic information, master-list import, and student search. |
| Hostel and Room Management | Hostel configuration, room inventory, capacity, room status, and vacancy information. |
| Room Application and Allocation | Application windows, room preferences, manual and automatic allocation, and allocation history. |
| Complaints and Maintenance | Complaint submission, status tracking, remarks, and maintenance follow-up. |
| Fee Management | Fee records, payment recording, outstanding dues, and PDF receipts. |
| Reports and Dashboard | Occupancy, resident lists, fee dues, complaint summaries, and CSV/PDF exports. |
| Notifications and Announcements | Email notifications, delivery retries, and hostel announcements. |

Shared services provide common functionality such as permission checks, hostel-level access restrictions, audit logging, validation, error handling, and document numbering.

## User Roles

- **Student:** Manage profiles, apply for rooms, view application and allocation status, check dues, request room changes, raise complaints, and view announcements.
- **Warden:** Manage applications and allocations for assigned hostels, access resident information, handle complaints, and perform relevant hostel operations.
- **Administrator:** Manage users, hostels, rooms, application windows, student master-list imports, and administrative records and reports.

## System Architecture

The proposed system follows a **three-tier architecture implemented as a modular Django monolith**.

1. **Presentation Layer:** Browser-based, responsive user interface built using Django Templates and Bootstrap.
2. **Application Layer:** A Django application organized into eight functional modules and shared Core services.
3. **Data Layer:** PostgreSQL database accessed through the Django ORM.

The architecture emphasizes modularity, data integrity, security, maintainability, and reliable room allocation. Components communicate through service interfaces, and each component is responsible for its own data.

## Technology Stack

The Software Architecture and Design specification identifies the following technologies for the planned implementation.

| Area | Technology |
|---|---|
| Programming Language | Python 3.12 |
| Backend Framework | Django 5.x |
| Frontend | Django Templates, Bootstrap 5.3 |
| Database | PostgreSQL 16 |
| Database Access | Django ORM, psycopg 3 |
| Application Server | Gunicorn |
| Web Server / Reverse Proxy | Nginx |
| Operating System | Ubuntu Server 24.04 LTS |
| PDF Generation | ReportLab |
| Email | University SMTP relay |
| Version Control | Git and GitHub |

The implementation is intended to use free and open-source libraries and follow the constraints documented in the SRS and SAD.

## Security and Quality Considerations

The system design addresses:

- Role-based access control and hostel-scoped authorization.
- Secure authentication, password storage, session management, and request validation.
- Prevention of duplicate or conflicting room allocations.
- Protection of student data and appropriate audit logging.
- Secure file uploads and restricted access to stored documents.
- Performance, availability, reliability, backup, and recovery requirements.
- Responsive usability and browser compatibility.
- Traceability between requirements, design decisions, and testing.

## Project Documentation

This repository contains the primary documentation for the Hostel Management System.

### 1. Software Requirements Specification (SRS)

**File:** [`SRS_Hostel_Management_System.pdf`](SRS_Hostel_Management_System.pdf)

Defines the system's scope, functional and non-functional requirements, user roles, external interfaces, business rules, security requirements, and requirement traceability.

### 2. Software Architecture and Design (SAD)

**File:** [`SAD_Architecture_and_Design.pdf`](SAD_Architecture_and_Design.pdf)

Describes the system architecture, component interactions, deployment view, technology stack, data design, state models, UML sequence diagrams, API design, error handling, logging, monitoring, and user-interface design.

### 3. Software Test Plan (STP)

**File:** [`STP_Hostel_Management_System.pdf`](STP_Hostel_Management_System.pdf)

Defines the testing scope, test strategy, test environment, test schedule, roles and responsibilities, risks, acceptance criteria, and requirements-based testing approach.

## Scope Limitations

The following features are outside the scope of Release 1.0:

- Online fee collection through payment gateways.
- Mess and menu management.
- Visitor and leave/out-pass management.
- Biometric attendance.
- A native mobile application.

The system records payments made through existing university channels; it does not directly collect payments.

## Development Status

This repository currently contains the project's requirements, architecture and design, and testing documentation. These documents establish the baseline for the planned implementation and verification of the Hostel Management System.

## Contributors

**Group 3 — PES University, Department of Computer Science and Engineering**

- Raina Kareem
- Prema P Kotur
- Praakruthi PS
- Ojas Taori


