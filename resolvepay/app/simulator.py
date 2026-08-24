import json
import random
from datetime import datetime, timedelta, timezone
from typing import List
from app.models import TransactionFailureEvent, FailureReason

NAMES = [
    "Aarav Sharma", "Priya Patel", "Rohan Verma", "Sneha Iyer",
    "Vikram Malhotra", "Ananya Reddy", "Kabir Sen", "Pooja Deshmukh"
]

FAILURE_DISTRIBUTION = [
    (FailureReason.INSUFFICIENT_FUNDS, "Account balance insufficient for standing instruction", 0.40),
    (FailureReason.GATEWAY_TIMEOUT, "Acquiring bank timeout during 2FA/Mandate execution", 0.25),
    (FailureReason.BANK_TECHNICAL_ERROR, "Downtime reported on Issuer NPCI switch", 0.15),
    (FailureReason.CARD_EXPIRED, "Card validity expired before mandate debit", 0.10),
    (FailureReason.MANDATE_EXPIRED, "Mandate validity period completed", 0.05),
    (FailureReason.USER_AUTHENTICATION_FAILED, "Incorrect MPIN / OTP entered during fallback", 0.05)
]

def generate_synthetic_batch(size: int = 60) -> List[TransactionFailureEvent]:
    batch = []
    reasons, descriptions, weights = zip(*[(r, d, w) for r, d, w in FAILURE_DISTRIBUTION])

    for i in range(1, size + 1):
        chosen_idx = random.choices(range(len(reasons)), weights=weights)[0]
        failure_code = reasons[chosen_idx]
        failure_desc = descriptions[chosen_idx]
        
        name = random.choice(NAMES)
        phone = f"+9198{random.randint(10000000, 99999999)}"
        email = f"{name.lower().replace(' ', '.')}@example.com"
        
        amount = random.choice([299.0, 499.0, 999.0, 1499.0, 4999.0, 12500.0])
        method = "upi_mandate" if amount < 5000 else "recurring_card"
        
        event = TransactionFailureEvent(
            event_id=f"evt_fail_{1000 + i}",
            merchant_id="rzp_merch_001",
            customer_id=f"cust_{2000 + i}",
            customer_name=name,
            customer_phone=phone,
            customer_email=email,
            amount_inr=amount,
            original_method=method,
            failure_code=failure_code,
            failure_message=failure_desc,
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 720)),
            retry_count=random.choice([0, 0, 0, 1, 2, 3])
        )
        batch.append(event)
    
    return batch

if __name__ == "__main__":
    records = generate_synthetic_batch(60)
    with open("data/synthetic_failures.json", "w") as f:
        json.dump([r.model_dump(mode="json") for r in records], f, indent=2)
    print(f"Generated {len(records)} failure records in data/synthetic_failures.json")