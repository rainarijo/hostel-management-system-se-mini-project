from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.core.middleware import ServerTimingMiddleware


class ServerTimingMiddlewareTests(SimpleTestCase):
    def test_records_django_request_processing_time(self):
        middleware = ServerTimingMiddleware(lambda request: HttpResponse("ok"))
        response = middleware(RequestFactory().get("/"))

        self.assertRegex(response["Server-Timing"], r"^app;dur=\d+\.\d{3}$")
