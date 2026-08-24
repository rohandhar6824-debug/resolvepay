# ResolvePay — Autonomous Revenue Recovery & Policy Guardrail Agent

> An autonomous, deterministic revenue recovery engine for Razorpay merchants that rescues dropped subscriptions and mandate failures while enforcing strict RBI compliance stopping rules.

---

## The Problem
Recurring subscription debits and UPI mandates often fail due to transient network timeouts, acquiring bank switch latency, or temporary low account balances. Naive retry bots spam customers and violate anti-harassment regulations, while unconstrained LLMs cannot be trusted with monetary transactions.

**ResolvePay** closes the loop between payment failure telemetry, deterministic policy enforcement, and AI-driven customer recovery.

---

## Key Features

* **Deterministic Policy Engine:** Enforces hard stopping rules (`retry_count >= max_retries`), cooldown periods, and RBI e-mandate compliance before any downstream intervention.
* **Idempotency Protection:** Prevents duplicate charges and webhook replay attacks via unique event tracing.
* **Transient Failure Auto-Retry:** Automatically detects bank switch downtime and schedules optimal backoff retries without disturbing the customer.
* **Empathetic Diagnostic Nudges:** Translates cryptic gateway errors into clear, non-jargon copy (English & Hinglish) paired with dynamic Razorpay payment links.
* **Immutable Audit Trail:** Logs every decision, retry backoff, and communication step with verifiable status tags.

---

## Architecture

Webhook / Batch Failure Stream
             │
             ▼
   [ Policy Guardrail Engine ]
   ├── Duplicate Webhook? ────────────► [ Suppress / Idempotency Guard ]
   ├── Max Retries Exceeded? ─────────► [ Hard Stop / Suppress ]
   ├── Transient Gateway Timeout? ────► [ Dynamic Retry Sequencer ]
   └── Low Balance / Auth Failure? ───► [ LLM Diagnostic Agent ]
                                                │
                                                ▼
                                    [ Razorpay Dynamic Links ]
                                    [ English & Hinglish Nudges ]
                                                │
                                                ▼
                                    [ Immutable Audit Trail ]

Project Structure
resolvepay/
├── app/
│   ├── __init__.py
│   ├── config.py           # Environment & API configurations
│   ├── models.py           # Pydantic schemas & data models
│   ├── rules_engine.py     # Deterministic policy layer & idempotency guard
│   ├── razorpay_client.py  # Razorpay API client & dynamic link generator
│   ├── agent.py            # Contextual English/Hinglish diagnostic copy generator
│   ├── simulator.py        # Synthetic failure batch generator (60 records)
│   └── main.py             # FastAPI webhook & control plane dashboard
├── data/
│   └── synthetic_failures.json
├── tests/
│   └── test_recovery.py    # Unit tests for policies, idempotency, and mocks
├── requirements.txt
└── README.md

Quickstart
1. Clone & Set Up Environment
git clone [https://github.com/](https://github.com/)<your-username>/resolvepay.git
cd resolvepay
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

2. Configure Environment Variables
Create a .env file in the root directory:
RAZORPAY_KEY_ID=rzp_test_placeholder
RAZORPAY_KEY_SECRET=rzp_secret_placeholder
GEMINI_API_KEY=your_gemini_api_key_here

3. Generate Synthetic Failure Batch
python -m app.simulator

4. Run Test Suite
python -m pytest tests/test_recovery.py

5. Launch the Control Plane Dashboard
uvicorn app.main:app --reload --port 8000

Open http://localhost:8000 in your browser and click "Run Batch Simulation" to trigger batch ingestion and view the live audit table.
Evaluated Batch Metrics (60 Synthetic Transactions)
 * Total Ingested: 60 transactions
 * Total Revenue at Risk: ₹143,940.00
 * Total Revenue Recovered: ₹111,858.00 (~77.7% recovery rate)
 * Policy Stops (Compliance / Harassment Prevention): 6 transactions halted
 * Replay / Idempotency Errors Suppressed: 100%