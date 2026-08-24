import json
from google import genai
from typing import Dict, Any
from app.config import GEMINI_API_KEY
from app.models import TransactionFailureEvent, RecoveryActionType

class RecoveryAgent:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

    def generate_contextual_nudge(self, event: TransactionFailureEvent, action: RecoveryActionType, payment_link: str) -> Dict[str, str]:
        """
        Generates structured, empathetic payment recovery copy (English & Hinglish)
        without exposing technical error strings to end-users.
        """
        if not self.client or not GEMINI_API_KEY:
            return self._fallback_nudge(event, payment_link)

        prompt = f"""
You are an empathetic, professional fintech recovery specialist for a merchant on Razorpay.
Draft a clear, courteous payment failure notification for a customer.

Customer Details:
- Name: {event.customer_name}
- Amount: ₹{event.amount_inr}
- Failure Category: {event.failure_code.value}
- Raw Message: {event.failure_message}
- Recovery Action: {action.value}
- Payment Link: {payment_link}

Requirements:
1. Explain the problem simply without using technical jargon (e.g. explain insufficient funds as low balance, gateway timeout as temporary bank server delay).
2. Provide a clear call to action using the link provided.
3. Return STRICTLY a JSON object with two fields:
   "english_message": "...",
   "hinglish_message": "..."
"""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=dict(response_mime_type="application/json")
            )
            return json.loads(response.text)
        except Exception:
            return self._fallback_nudge(event, payment_link)

    def _fallback_nudge(self, event: TransactionFailureEvent, payment_link: str) -> Dict[str, str]:
        reasons = {
            "INSUFFICIENT_FUNDS": (
                f"Hi {event.customer_name}, your auto-payment of ₹{event.amount_inr} couldn't go through due to low account balance. Please use this secure link to complete the payment: {payment_link}",
                f"Namaste {event.customer_name}, aapka ₹{event.amount_inr} ka auto-debit low balance ki wajah se complete nahi ho paya. Please is link se payment pura karein: {payment_link}"
            ),
            "GATEWAY_TIMEOUT": (
                f"Hi {event.customer_name}, your bank took longer than expected to process your payment of ₹{event.amount_inr}. We will automatically retry shortly, or you can pay here: {payment_link}",
                f"Namaste {event.customer_name}, bank servers slow hone ke karan ₹{event.amount_inr} ka payment atka hai. Hum thodi der me auto-retry karenge, ya direct yahan pay karein: {payment_link}"
            )
        }
        eng, hin = reasons.get(
            event.failure_code.value,
            (
                f"Hi {event.customer_name}, your payment of ₹{event.amount_inr} was not completed. Click here to securely retry: {payment_link}",
                f"Namaste {event.customer_name}, aapka ₹{event.amount_inr} ka payment complete nahi hua. Dobara try karne ke liye yahan click karein: {payment_link}"
            )
        )
        return {"english_message": eng, "hinglish_message": hin}