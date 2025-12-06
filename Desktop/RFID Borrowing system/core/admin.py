from django.contrib import admin

from .models import Borrower, Item, BorrowTransaction


@admin.register(Borrower)
class BorrowerAdmin(admin.ModelAdmin):
    list_display = ("name", "rfid_uid", "email", "created_at")
    search_fields = ("name", "rfid_uid", "email")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "qr_code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "qr_code")


@admin.register(BorrowTransaction)
class BorrowTransactionAdmin(admin.ModelAdmin):
    list_display = ("item", "borrower", "status", "borrowed_at", "returned_at")
    list_filter = ("status",)
    search_fields = ("item__name", "item__qr_code", "borrower__name", "borrower__rfid_uid")


