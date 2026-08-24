import razorpay
import uuid
from typing import Dict, Any
from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

class RazorpayRecoveryClient:
    def __init__(self):
        self.is_live_test = (
            RAZORPAY_KEY_ID != "rzp_test_placeholder" and 
            RAZORPAY_KEY_SECRET != "rzp_secret_placeholder"
        )
        if self.is_live_test:
            self.client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        else:
            self.client = None

    def create_recovery_payment_link(self, customer_name: str, email: str, phone: str, amount_inr: float, description: str) -> Dict[str, Any]:
        """Creates a Razorpay Payment Link (or deterministic mock if keys aren't set)."""
        amount_paise = int(amount_inr * 100)
        
        if self.is_live_test and self.client:
            try:
                payload = {
                    "amount": amount_paise,
                    "currency": "INR",
                    "accept_partial": False,
                    "description": description,
                    "customer": {
                        "name": customer_name,
                        "email": email,
                        "contact": phone
                    },
                    "notify": {"sms": False, "email": False},
                    "reminder_enable": True
                }
                res = self.client.payment_link.create(payload)
                return {
                    "link_id": res.get("id"),
                    "short_url": res.get("short_url"),
                    "status": res.get("status"),
                    "mode": "LIVE_TEST_API"
                }
            except Exception as e:
                return {
                    "link_id": f"plink_err_{uuid.uuid4().hex[:8]}",
                    "short_url": f"https://rzp.io/i/fallback_{uuid.uuid4().hex[:6]}",
                    "status": "ERROR_FALLBACK",
                    "error": str(e),
                    "mode": "FALLBACK"
                }
        
        # Deterministic simulation mode
        mock_id = f"plink_mock_{uuid.uuid4().hex[:8]}"
        return {
            "link_id": mock_id,
            "short_url": f"https://rzp.io/i/{mock_id[:12]}",
            "status": "created",
            "mode": "MOCK_TEST_MODE"
        }