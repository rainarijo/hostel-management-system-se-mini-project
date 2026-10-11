from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    STUDENT = "STUDENT", "Student"
    WARDEN = "WARDEN", "Warden"
    ADMIN = "ADMIN", "Administrator"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    """HMS user. Logs in with e-mail; exactly one role per account (FR-1.4)."""
    username = None
    email = models.EmailField("e-mail address", unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    # FR-1.5 lock-out bookkeeping
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    first_failed_login_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.get_role_display()})"

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self):
        now = timezone.now()
        window = timezone.timedelta(minutes=settings.LOGIN_FAILURE_WINDOW_MINUTES)
        if not self.first_failed_login_at or now - self.first_failed_login_at > window:
            self.first_failed_login_at = now
            self.failed_login_count = 0
        self.failed_login_count += 1
        if self.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
            self.locked_until = now + timezone.timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            self.failed_login_count = 0
            self.first_failed_login_at = None
        self.save(update_fields=["failed_login_count", "first_failed_login_at", "locked_until"])

    def reset_failed_logins(self):
        self.failed_login_count = 0
        self.first_failed_login_at = None
        self.locked_until = None
        self.save(update_fields=["failed_login_count", "first_failed_login_at", "locked_until"])
