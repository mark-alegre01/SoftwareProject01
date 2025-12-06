from __future__ import annotations

from django.db import models


class Borrower(models.Model):
    name = models.CharField(max_length=120)
    rfid_uid = models.CharField(max_length=64, unique=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.rfid_uid})"


class Item(models.Model):
    name = models.CharField(max_length=200)
    qr_code = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.qr_code})"


class BorrowTransaction(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RETURNED = "RETURNED", "Returned"

    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, related_name="transactions")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="transactions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    borrowed_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "item"]),
            models.Index(fields=["borrower", "status"]),
        ]
        ordering = ["-borrowed_at"]

    def __str__(self) -> str:
        return f"{self.item} -> {self.borrower} [{self.status}]"


class RFIDScan(models.Model):
    uid = models.CharField(max_length=64)
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.uid} @ {self.created_at}"


