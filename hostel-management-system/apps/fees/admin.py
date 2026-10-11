from django.contrib import admin

from .models import FeeRecord, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = ("allocation", "total_amount", "amount_paid", "balance")
    inlines = [PaymentInline]
