from django.urls import path

from .views import (
    BorrowCreateView,
    ReturnView,
    BorrowerView,
    BorrowerDetailView,
    ItemView,
    ItemDetailView,
    BorrowTransactionDetailView,
    ScanIdView,
    BorrowerRegistrationView,
    ItemRegistrationView,
    ItemQRCodeView,
    RFIDScanView,
)


urlpatterns = [
    path("borrow", BorrowCreateView.as_view(), name="api-borrow"),
    path("borrow/", BorrowCreateView.as_view(), name="api-borrow-slash"),
    path("return", ReturnView.as_view(), name="api-return"),
    path("return/", ReturnView.as_view(), name="api-return-slash"),
    path("borrowers", BorrowerView.as_view(), name="api-borrowers"),
    path("borrowers/", BorrowerView.as_view(), name="api-borrowers-slash"),
    path("borrowers/<int:borrower_id>", BorrowerDetailView.as_view(), name="api-borrowers-detail"),
    path("borrowers/<int:borrower_id>/", BorrowerDetailView.as_view(), name="api-borrowers-detail-slash"),
    path("items", ItemView.as_view(), name="api-items"),
    path("items/", ItemView.as_view(), name="api-items-slash"),
    path("items/<int:item_id>", ItemDetailView.as_view(), name="api-items-detail"),
    path("items/<int:item_id>/", ItemDetailView.as_view(), name="api-items-detail-slash"),
    path("transactions/<int:transaction_id>", BorrowTransactionDetailView.as_view(), name="api-transactions-detail"),
    path("transactions/<int:transaction_id>/", BorrowTransactionDetailView.as_view(), name="api-transactions-detail-slash"),
    path("scan-id", ScanIdView.as_view(), name="api-scan-id"),
    path("scan-id/", ScanIdView.as_view(), name="api-scan-id-slash"),
    path("register-borrower", BorrowerRegistrationView.as_view(), name="api-register-borrower"),
    path("register-borrower/", BorrowerRegistrationView.as_view(), name="api-register-borrower-slash"),
    path("register-item", ItemRegistrationView.as_view(), name="api-register-item"),
    path("register-item/", ItemRegistrationView.as_view(), name="api-register-item-slash"),
    path("items/<int:item_id>/qr", ItemQRCodeView.as_view(), name="api-item-qr"),
    path("items/<int:item_id>/qr/", ItemQRCodeView.as_view(), name="api-item-qr-slash"),
    path("rfid-scans", RFIDScanView.as_view(), name="api-rfid-scans"),
    path("rfid-scans/", RFIDScanView.as_view(), name="api-rfid-scans-slash"),
]


