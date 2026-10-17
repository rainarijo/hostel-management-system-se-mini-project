"""Exception hierarchy used by all service layers (SAD 4.4.1).

Services raise these; a central handler maps them to HTTP responses.
"""


class HMSError(Exception):
    """Base class for all HMS business exceptions."""
    message = "Something went wrong."

    def __init__(self, message=None):
        super().__init__(message or self.message)
        self.message = message or self.message


class ValidationFailure(HMSError):
    message = "Invalid input."


class AccessDenied(HMSError):
    message = "You do not have permission to do this."


class ObjectNotFound(HMSError):
    message = "Not found."


class BusinessRuleViolation(HMSError):
    message = "This action is not allowed."


class BedUnavailable(BusinessRuleViolation):
    message = "Bed no longer available."


class GenderMismatch(BusinessRuleViolation):
    message = "Student and hostel gender do not match."


class RoomUnderMaintenance(BusinessRuleViolation):
    message = "This room is under maintenance."


class AlreadyAllocated(BusinessRuleViolation):
    message = "Student already has an active allocation."


class WindowClosed(BusinessRuleViolation):
    message = "The application window is closed."


class DuplicateApplication(BusinessRuleViolation):
    message = "You have already applied for this academic year."


class ProfileIncomplete(BusinessRuleViolation):
    message = "Complete your profile before applying."


class RateLimited(HMSError):
    message = "Too many requests."


class TokenExpired(HMSError):
    message = "This link has expired."


class InvalidUpload(ValidationFailure):
    message = "Upload a JPEG or PNG of at most 2 MB."
