import os
import re

from locust import HttpUser, between, constant, events, task, tag

MODE = os.environ.get("HMS_LOADTEST_MODE", "pages")
PASSWORD = os.environ.get("HMS_LOADTEST_PASSWORD", "Hostel2026pass")
MAX_PAGE_MS = 5000
P95_PAGE_MS = 2000
MAX_SINGLE_ALLOCATION_MS = 1000
MAX_AUTO_ALLOCATE_MS = 60000


@events.init.add_listener
def register_performance_thresholds(environment, **kwargs):
    missing_server_timing = {"count": 0}
    request_stats = environment.stats

    def record_timing(request_type, name, response_time, response, exception, **request_kwargs):
        if str(name).lower().startswith("setup "):
            return
        if MODE == "auto_allocate":
            if request_type != "POST" or name != "Auto-Allocate 500 applications":
                return
        elif MODE == "allocation":
            if request_type != "POST" or name != "Single allocation":
                return
        elif request_type != "GET":
            return

        request_stats.get("All measured requests", method="CLIENT").log(response_time, 0)
        if exception or response is None:
            missing_server_timing["count"] += 1
            return

        match = re.search(r"(?:^|,)\s*app;dur=([\d.]+)", response.headers.get("Server-Timing", ""))
        if not match:
            missing_server_timing["count"] += 1
            return
        request_stats.get("All measured requests", method="SERVER").log(float(match.group(1)), 0)

    environment.events.request.add_listener(record_timing)

    @environment.events.quitting.add_listener
    def enforce_performance_thresholds(**quit_kwargs):
        client_stats = request_stats.get("All measured requests", method="CLIENT")
        server_stats = request_stats.get("All measured requests", method="SERVER")
        if missing_server_timing["count"] or not server_stats.num_requests:
            print(f"Missing server timings: {missing_server_timing['count']}")
            environment.process_exit_code = 1
            return

        client_p95 = client_stats.get_response_time_percentile(0.95)
        client_max = client_stats.max_response_time
        server_p95 = server_stats.get_response_time_percentile(0.95)
        server_max = server_stats.max_response_time
        print(
            f"Measured requests: {client_stats.num_requests}; "
            f"client p95/max={client_p95:.0f}/{client_max:.0f} ms; "
            f"Django p95/max={server_p95:.0f}/{server_max:.0f} ms"
        )
        if MODE == "auto_allocate":
            if server_max > MAX_AUTO_ALLOCATE_MS or client_max > MAX_AUTO_ALLOCATE_MS:
                environment.process_exit_code = 1
        elif MODE == "allocation":
            if server_max > MAX_SINGLE_ALLOCATION_MS or client_max > MAX_SINGLE_ALLOCATION_MS:
                environment.process_exit_code = 1
        elif (
            client_p95 > P95_PAGE_MS
            or server_p95 > P95_PAGE_MS
            or client_max > MAX_PAGE_MS
            or server_max > MAX_PAGE_MS
        ):
            environment.process_exit_code = 1
        if request_stats.total.num_failures:
            environment.process_exit_code = 1


class HMSUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)

    def login(self, email):
        login_page = self.client.get("/accounts/login/", name="Setup login form")
        csrf_token = self.client.cookies.get("csrftoken")
        if not csrf_token:
            raise RuntimeError("The login page did not set a CSRF cookie.")
        response = self.client.post(
            "/accounts/login/",
            {"email": email, "password": PASSWORD},
            headers={"X-CSRFToken": csrf_token, "Referer": login_page.url},
            name="Setup login",
            allow_redirects=True,
        )
        if response.status_code >= 400 or 'id_password' in response.text:
            raise RuntimeError(f"Unable to log in as {email} (HTTP {response.status_code}).")

    def get_page(self, path, name):
        with self.client.get(path, name=name, catch_response=True) as response:
            if response.status_code >= 400:
                response.failure(f"HTTP {response.status_code}")
            return response.text


@tag("pages")
class StudentUser(HMSUser):
    weight = 6 if MODE == "pages" else 0

    def on_start(self):
        self.login(os.environ.get("HMS_STUDENT_EMAIL", "student1@hms.local"))

    @task(5)
    def dashboard(self):
        self.get_page("/dashboard/student/", "Student dashboard")

    @task(2)
    def allocation_history(self):
        self.get_page("/allocation/history/", "Student allocation history")

    @task(2)
    def fee_dues(self):
        self.get_page("/fees/my/", "Student fee dues")


@tag("pages")
class WardenUser(HMSUser):
    weight = 2 if MODE == "pages" else 0

    def on_start(self):
        self.login(os.environ.get("HMS_WARDEN_EMAIL", "warden.boys@hms.local"))

    @task(5)
    def dashboard(self):
        self.get_page("/dashboard/warden/", "Warden dashboard")

    @task(4)
    def allocation_queue(self):
        body = self.get_page("/applications/queue/", "Application queue")
        match = re.search(r'href="(/applications/\d+/allocate/)"', body)
        if match:
            self.get_page(match.group(1), "Allocation options")

    @task(3)
    def active_allocations(self):
        self.get_page("/manage/allocations/", "Active allocations")

    @task(2)
    def student_search(self):
        self.get_page("/students/search/?q=LT", "Student search")

    @task(2)
    def reports(self):
        self.get_page("/reports/occupancy/", "Occupancy report")
        self.get_page("/reports/residents/", "Resident report")


@tag("pages")
class AdministratorUser(HMSUser):
    weight = 1 if MODE == "pages" else 0

    def on_start(self):
        self.login(os.environ.get("HMS_ADMIN_EMAIL", "admin@hms.local"))

    @task(4)
    def dashboard(self):
        self.get_page("/dashboard/admin/", "Administrator dashboard")

    @task(3)
    def student_profiles(self):
        self.get_page("/students/", "Student profile list")

    @task(3)
    def student_search(self):
        self.get_page("/students/search/?q=LT", "Student search")

    @task(2)
    def application_queue(self):
        self.get_page("/applications/queue/", "Application queue")

    @task(3)
    def reports(self):
        for report in ("occupancy", "residents", "fee-dues", "complaints"):
            self.get_page(f"/reports/{report}/", f"{report.title()} report")


@tag("auto_allocate")
class AutoAllocateUser(HMSUser):
    weight = 1 if MODE == "auto_allocate" else 0
    wait_time = constant(0)

    def on_start(self):
        self.login(os.environ.get("HMS_ADMIN_EMAIL", "admin@hms.local"))

    @task
    def allocate_once(self):
        queue = self.client.get("/applications/queue/", name="Setup allocation queue", timeout=120)
        match = re.search(r'<select[^>]*name="hostel_id"[^>]*>(.*?)</select>', queue.text, re.DOTALL)
        hostel = re.search(
            r'<option value="(\d+)">HMS Load Test Hostel',
            match.group(1),
        ) if match else None
        if not hostel:
            raise RuntimeError("Run seed_performance_data before measuring auto-allocation.")
        with self.client.post(
            "/applications/auto-allocate/",
            {"hostel_id": hostel.group(1)},
            headers={
                "X-CSRFToken": self.client.cookies.get("csrftoken"),
                "Referer": f"{self.host.rstrip('/')}/applications/queue/",
            },
            name="Auto-Allocate 500 applications",
            timeout=120,
            catch_response=True,
        ) as response:
            if response.status_code >= 400:
                response.failure(f"HTTP {response.status_code}")
        self.environment.runner.quit()


@tag("allocation")
class AllocationUser(HMSUser):
    weight = 1 if MODE == "allocation" else 0
    wait_time = constant(0)

    def on_start(self):
        self.login(os.environ.get("HMS_ADMIN_EMAIL", "admin@hms.local"))

    @task
    def allocate_once(self):
        queue = self.client.get("/applications/queue/", name="Setup allocation queue")
        application = re.search(r'href="(/applications/\d+/allocate/)"', queue.text)
        if not application:
            raise RuntimeError("The application queue has no pending application.")
        allocation_url = application.group(1)
        form = self.client.get(allocation_url, name="Setup allocation form", timeout=30)
        bed_select = re.search(r'<select[^>]*name="bed"[^>]*>(.*?)</select>', form.text, re.DOTALL)
        bed = re.search(r'<option value="(\d+:\d+)"', bed_select.group(1)) if bed_select else None
        if not bed:
            raise RuntimeError("The pending application has no available bed.")
        with self.client.post(
            allocation_url,
            {"bed": bed.group(1)},
            headers={
                "X-CSRFToken": self.client.cookies.get("csrftoken"),
                "Referer": f"{self.host.rstrip('/')}{allocation_url}",
            },
            name="Single allocation",
            timeout=30,
            allow_redirects=True,
            catch_response=True,
        ) as response:
            if response.status_code >= 400 or response.url.rstrip("/") == allocation_url.rstrip("/"):
                response.failure(f"Allocation failed (HTTP {response.status_code}).")
        self.environment.runner.quit()
