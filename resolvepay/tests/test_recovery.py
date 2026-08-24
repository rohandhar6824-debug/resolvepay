from datetime import datetime, timezone
from app.models import TransactionFailureEvent, FailureReason, RecoveryActionType
from app.rules_engine import PolicyEngine
from app.razorpay_client import RazorpayRecoveryClient

def test_hard_stop_policy_enforcement():
    event = TransactionFailureEvent(
        event_id="evt_test_unique_01",
        merchant_id="rzp_test_001",
        customer_id="cust_test_01",
        customer_name="Test User",
        customer_phone="+919876543210",
        customer_email="test@example.com",
        amount_inr=999.0,
        original_method="upi_mandate",
        failure_code=FailureReason.INSUFFICIENT_FUNDS,
        failure_message="Low balance",
        timestamp=datetime.now(timezone.utc),
        retry_count=3,
        max_retries_allowed=3
    )
    action, reason, audit = PolicyEngine.evaluate_policy(event)
    assert action == RecoveryActionType.HALT
    assert audit.status == "SUCCESS"

def test_idempotency_duplicate_webhook_prevention():
    event = TransactionFailureEvent(
        event_id="evt_duplicate_idempotent_test",
        merchant_id="rzp_test_001",
        customer_id="cust_test_02",
        customer_name="Test User",
        customer_phone="+919876543210",
        customer_email="test@example.com",
        amount_inr=1499.0,
        original_method="upi_mandate",
        failure_code=FailureReason.GATEWAY_TIMEOUT,
        failure_message="Timeout",
        timestamp=datetime.now(timezone.utc),
        retry_count=0
    )
    # First ingestion -> normal processing
    action1, _, _ = PolicyEngine.evaluate_policy(event)
    assert action1 == RecoveryActionType.DYNAMIC_RETRY

    # Second duplicate webhook with same ID -> suppressed immediately
    action2, reason2, audit2 = PolicyEngine.evaluate_policy(event)
    assert action2 == RecoveryActionType.HALT
    assert "Duplicate webhook" in reason2

def test_razorpay_mock_payment_link_generation():
    client = RazorpayRecoveryClient()
    res = client.create_recovery_payment_link("Test User", "test@example.com", "+919876543210", 499.0, "Test Recovery")
    assert "short_url" in res
    assert res["status"] in ["created", "LIVE_TEST_API"]