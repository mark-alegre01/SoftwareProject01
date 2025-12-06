from rest_framework import serializers

from .models import Borrower, Item, BorrowTransaction, RFIDScan


class BorrowerSerializer(serializers.ModelSerializer):
    open_transactions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Borrower
        fields = ["id", "name", "rfid_uid", "email", "created_at", "open_transactions_count"]
    
    def get_open_transactions_count(self, obj):
        """Return count of open (borrowed) transactions for this borrower."""
        return obj.transactions.filter(status=BorrowTransaction.Status.OPEN).count()


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "qr_code", "description", "is_active", "created_at"]


class BorrowTransactionSerializer(serializers.ModelSerializer):
    borrower = BorrowerSerializer(read_only=True)
    item = ItemSerializer(read_only=True)

    class Meta:
        model = BorrowTransaction
        fields = [
            "id",
            "borrower",
            "item",
            "status",
            "borrowed_at",
            "returned_at",
        ]


class BorrowCreateSerializer(serializers.Serializer):
    borrower_rfid = serializers.CharField(max_length=64)
    item_qr = serializers.CharField(max_length=128)


class ReturnSerializer(serializers.Serializer):
    item_qr = serializers.CharField(max_length=128, required=False)
    transaction_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs.get("item_qr") and not attrs.get("transaction_id"):
            raise serializers.ValidationError("Provide either item_qr or transaction_id")
        return attrs


class ScanIdSerializer(serializers.Serializer):
    borrower_rfid = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)


class BorrowerRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    rfid_uid = serializers.CharField(max_length=64)
    email = serializers.EmailField(required=False, allow_blank=True)
    qr_data = serializers.CharField(required=False, allow_blank=True, help_text="QR code data to parse for borrower info")


class ItemRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)


class RFIDScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFIDScan
        fields = ["id", "uid", "name", "email", "created_at"]


class RFIDScanCreateSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

