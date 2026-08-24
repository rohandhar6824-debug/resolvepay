from datetime import datetime, timezone
from typing import Tuple, Set
from app.models import TransactionFailureEvent, FailureReason, RecoveryActionType, RecoveryStepAudit

# Bank-specific optimal retry windows (Simulated Switch Telemetry)
BANK_RETRY_WINDOWS = {
    "HDFC": {"optimal_slot_utc_hour": 4, "success_prob": 0.88},   # 9:30 AM IST
    "SBI":  {"optimal_slot_utc_hour": 5, "success_prob": 0.82},   # 10:30 AM IST
    "ICICI":{"optimal_slot_utc_hour": 3, "success_prob": 0.91},   # 8:30 AM IST
}

class PolicyEngine:
    processed_events: Set[str] = set()

    @classmethod
    def evaluate_policy(cls, event: TransactionFailureEvent) -> Tuple[RecoveryActionType, str, RecoveryStepAudit]:
        # 1. Idempotency Check (Prevent duplicate charges)
        if event.event_id in cls.processed_events:
            audit = RecoveryStepAudit(
                step_id=f"audit_idempotent_{event.event_id}",
                timestamp=datetime.now(timezone.utc),
                actor="IDEMPOTENCY_GUARD",
                action_taken="SUPPRESS_DUPLICATE_WEBHOOK",
                details={"event_id": event.event_id, "risk": "DOUBLE_CHARGE_PREVENTION"},
                status="SUCCESS"
            )
            return RecoveryActionType.HALT, "Duplicate webhook detected; action suppressed", audit

        cls.processed_events.add(event.event_id)

        # 2. Hard RBI Compliance Ceiling
        if event.retry_count >= event.max_retries_allowed:
            audit = RecoveryStepAudit(
                step_id=f"audit_halt_{event.event_id}",
                timestamp=datetime.now(timezone.utc),
                actor="RULES_ENGINE",
                action_taken="ENFORCE_HARD_STOP",
                details={
                    "reason": "RBI Mandate Retry Threshold Exceeded",
                    "retries": event.retry_count,
                    "max_allowed": event.max_retries_allowed
                },
                status="SUCCESS"
            )
            return RecoveryActionType.HALT, "Max retries exhausted; customer communication suppressed", audit

        # 3. Card/Mandate Expiry
        if event.failure_code in [FailureReason.CARD_EXPIRED, FailureReason.MANDATE_EXPIRED]:
            audit = RecoveryStepAudit(
                step_id=f"audit_reauth_{event.event_id}",
                timestamp=datetime.now(timezone.utc),
                actor="RULES_ENGINE",
                action_taken="ROUTE_TO_MANDATE_REAUTH",
                details={"failure_code": event.failure_code.value},
                status="SUCCESS"
            )
            return RecoveryActionType.MANDATE_REAUTHENTICATION, "Authentication artifact expired; trigger new mandate link", audit

        # 4. Smart Transient Failure Window Routing
        if event.failure_code in [FailureReason.GATEWAY_TIMEOUT, FailureReason.BANK_TECHNICAL_ERROR]:
            audit = RecoveryStepAudit(
                step_id=f"audit_retry_{event.event_id}",
                timestamp=datetime.now(timezone.utc),
                actor="RULES_ENGINE",
                action_taken="SCHEDULE_DYNAMIC_RETRY",
                details={
                    "failure_code": event.failure_code.value,
                    "recommended_window": "NEXT_PEAK_SUCCESS_SLOT (09:00-11:00 IST)",
                    "backoff_minutes": 30 * (event.retry_count + 1)
                },
                status="SUCCESS"
            )
            return RecoveryActionType.DYNAMIC_RETRY, "Transient network/switch failure; scheduled smart slot retry", audit

        # 5. Low Balance / Auth Nudge
        if event.failure_code in [FailureReason.INSUFFICIENT_FUNDS, FailureReason.USER_AUTHENTICATION_FAILED]:
            action = RecoveryActionType.WHATSAPP_NUDGE if event.amount_inr <= 2000 else RecoveryActionType.PAYMENT_LINK_EMAIL
            audit = RecoveryStepAudit(
                step_id=f"audit_nudge_{event.event_id}",
                timestamp=datetime.now(timezone.utc),
                actor="RULES_ENGINE",
                action_taken=f"ROUTE_TO_{action.value}",
                details={
                    "failure_code": event.failure_code.value,
                    "amount": event.amount_inr,
                    "channel": "WhatsApp" if action == RecoveryActionType.WHATSAPP_NUDGE else "Email"
                },
                status="SUCCESS"
            )
            return action, "Customer intervention required; route to diagnostic messaging agent", audit

        audit = RecoveryStepAudit(
            step_id=f"audit_fallback_{event.event_id}",
            timestamp=datetime.now(timezone.utc),
            actor="RULES_ENGINE",
            action_taken="UNRECOGNIZED_FAILURE_HALT",
            details={"raw_message": event.failure_message},
            status="FAILED"
        )
        return RecoveryActionType.HALT, "Unrecognized failure code", audit