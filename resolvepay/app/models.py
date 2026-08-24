from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class FailureReason(str, Enum):
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"
    MANDATE_EXPIRED = "MANDATE_EXPIRED"
    CARD_EXPIRED = "CARD_EXPIRED"
    USER_AUTHENTICATION_FAILED = "USER_AUTHENTICATION_FAILED"
    BANK_TECHNICAL_ERROR = "BANK_TECHNICAL_ERROR"

class RecoveryActionType(str, Enum):
    DYNAMIC_RETRY = "DYNAMIC_RETRY"             # Schedule auto-retry at optimal window
    PAYMENT_LINK_EMAIL = "PAYMENT_LINK_EMAIL"   # Send backup payment link via Email
    WHATSAPP_NUDGE = "WHATSAPP_NUDGE"           # Contextual Hinglish WhatsApp alert
    MANDATE_REAUTHENTICATION = "MANDATE_REAUTH" # Trigger re-auth flow
    HALT = "HALT"                               # Stop retries to prevent customer harassment / compliance breach

class TransactionFailureEvent(BaseModel):
    event_id: str
    merchant_id: str
    customer_id: str
    customer_name: str
    customer_phone: str
    customer_email: str
    amount_inr: float
    currency: str = "INR"
    original_method: str  # upi_mandate, recurring_card, netbanking
    failure_code: FailureReason
    failure_message: str
    timestamp: datetime
    retry_count: int = 0
    max_retries_allowed: int = 3

class RecoveryStepAudit(BaseModel):
    step_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str  # "RULES_ENGINE" | "LLM_DIAGNOSTIC_AGENT" | "GATEWAY_WORKER"
    action_taken: str
    details: Dict[str, Any]
    status: str # "SUCCESS" | "FAILED" | "PENDING"

class RecoveryRecord(BaseModel):
    record_id: str
    failure_event: TransactionFailureEvent
    diagnosed_category: str
    chosen_action: RecoveryActionType
    recovery_status: str # "OPEN" | "RECOVERED" | "EXHAUSTED" | "STOPPED"
    amount_recovered: float = 0.0
    audit_trail: List[RecoveryStepAudit] = []