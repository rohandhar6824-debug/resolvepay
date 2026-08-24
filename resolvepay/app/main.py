import json
import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse

from app.models import (
    TransactionFailureEvent,
    RecoveryRecord,
    RecoveryActionType,
    RecoveryStepAudit
)
from app.rules_engine import PolicyEngine
from app.razorpay_client import RazorpayRecoveryClient
from app.agent import RecoveryAgent

app = FastAPI(
    title="ResolvePay: AI Revenue Recovery Agent",
    description="Deterministic Guardrails & Contextual Recovery Orchestrator for Razorpay",
    version="1.0.0"
)

rzp_client = RazorpayRecoveryClient()
recovery_agent = RecoveryAgent()

# In-memory storage for evaluated recovery records
recovery_db: Dict[str, RecoveryRecord] = {}

def process_single_failure(event: TransactionFailureEvent) -> RecoveryRecord:
    record_id = f"rec_{uuid.uuid4().hex[:10]}"
    audit_trail: List[RecoveryStepAudit] = []

    # 1. Deterministic Rule & Policy Evaluation
    action, policy_reason, rule_audit = PolicyEngine.evaluate_policy(event)
    audit_trail.append(rule_audit)

    status = "OPEN"
    amount_recovered = 0.0

    # 2. Execution based on policy
    if action == RecoveryActionType.HALT:
        status = "STOPPED"
    elif action == RecoveryActionType.DYNAMIC_RETRY:
        status = "RECOVERED"  # Simulated transient recovery success
        amount_recovered = event.amount_inr
        audit_trail.append(RecoveryStepAudit(
            step_id=f"audit_exec_{uuid.uuid4().hex[:6]}",
            timestamp=datetime.now(timezone.utc),
            actor="GATEWAY_WORKER",
            action_taken="DISPATCH_BACKOFF_RETRY",
            details={"retry_slot": "T+30m", "channel": "NPCI_STANDBY_GATEWAY"},
            status="SUCCESS"
        ))
    elif action in [RecoveryActionType.WHATSAPP_NUDGE, RecoveryActionType.PAYMENT_LINK_EMAIL, RecoveryActionType.MANDATE_REAUTHENTICATION]:
        # Generate dynamic recovery link
        link_res = rzp_client.create_recovery_payment_link(
            customer_name=event.customer_name,
            email=event.customer_email,
            phone=event.customer_phone,
            amount_inr=event.amount_inr,
            description=f"Recovery for {event.event_id}"
        )
        
        # Generate diagnostic copy
        nudge = recovery_agent.generate_contextual_nudge(event, action, link_res.get("short_url", ""))
        
        audit_trail.append(RecoveryStepAudit(
            step_id=f"audit_nudge_{uuid.uuid4().hex[:6]}",
            timestamp=datetime.now(timezone.utc),
            actor="LLM_DIAGNOSTIC_AGENT",
            action_taken=f"DISPATCH_{action.value}",
            details={
                "payment_link": link_res.get("short_url"),
                "english_copy": nudge.get("english_message"),
                "hinglish_copy": nudge.get("hinglish_message")
            },
            status="SUCCESS"
        ))
        
        # Probabilistic simulation: 65% of customer nudges convert to recovered revenue
        status = "RECOVERED" if hash(event.event_id) % 100 < 65 else "EXHAUSTED"
        amount_recovered = event.amount_inr if status == "RECOVERED" else 0.0

    record = RecoveryRecord(
        record_id=record_id,
        failure_event=event,
        diagnosed_category=policy_reason,
        chosen_action=action,
        recovery_status=status,
        amount_recovered=amount_recovered,
        audit_trail=audit_trail
    )
    recovery_db[record_id] = record
    return record

@app.post("/webhook/transaction-failure")
def handle_failure_webhook(event: TransactionFailureEvent):
    record = process_single_failure(event)
    return {"status": "processed", "record": record}

@app.post("/batch/run-simulation")
def run_batch_simulation():
    with open("data/synthetic_failures.json", "r") as f:
        data = json.load(f)
    
    events = [TransactionFailureEvent(**item) for item in data]
    recovery_db.clear()
    
    for evt in events:
        process_single_failure(evt)
        
    total_at_risk = sum(e.amount_inr for e in events)
    total_recovered = sum(r.amount_recovered for r in recovery_db.values())
    recovered_count = sum(1 for r in recovery_db.values() if r.recovery_status == "RECOVERED")
    stopped_count = sum(1 for r in recovery_db.values() if r.recovery_status == "STOPPED")
    
    return {
        "batch_size": len(events),
        "total_revenue_at_risk_inr": round(total_at_risk, 2),
        "total_revenue_recovered_inr": round(total_recovered, 2),
        "recovery_rate_percentage": round((total_recovered / total_at_risk) * 100, 2) if total_at_risk > 0 else 0,
        "recovered_transactions": recovered_count,
        "stopped_by_policy_compliance": stopped_count
    }

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    total_count = len(recovery_db)
    recovered = sum(1 for r in recovery_db.values() if r.recovery_status == "RECOVERED")
    stopped = sum(1 for r in recovery_db.values() if r.recovery_status == "STOPPED")
    recovered_amt = sum(r.amount_recovered for r in recovery_db.values())
    
    rows = ""
    for r in list(recovery_db.values())[:15]:
        status_color = "text-green-400" if r.recovery_status == "RECOVERED" else ("text-red-400" if r.recovery_status == "STOPPED" else "text-yellow-400")
        rows += f"""
        <tr class="border-b border-zinc-800 text-sm hover:bg-zinc-800/50">
            <td class="py-3 px-4 font-mono text-xs text-zinc-400">{r.failure_event.event_id}</td>
            <td class="py-3 px-4 font-medium text-zinc-200">{r.failure_event.customer_name}</td>
            <td class="py-3 px-4 font-mono text-zinc-300">₹{r.failure_event.amount_inr}</td>
            <td class="py-3 px-4 text-xs font-mono text-amber-400">{r.failure_event.failure_code.value}</td>
            <td class="py-3 px-4 text-xs font-mono text-blue-400">{r.chosen_action.value}</td>
            <td class="py-3 px-4 text-xs font-bold {status_color}">{r.recovery_status}</td>
        </tr>
        """
        
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ResolvePay | Revenue Recovery Control Plane</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-zinc-950 text-zinc-100 min-h-screen p-8 font-sans">
        <div class="max-w-6xl mx-auto space-y-6">
            <div class="flex justify-between items-center border-b border-zinc-800 pb-5">
                <div>
                    <h1 class="text-2xl font-bold tracking-tight text-white">ResolvePay // Control Plane</h1>
                    <p class="text-sm text-zinc-400 mt-1">Autonomous Revenue Recovery & Policy Guardrail Agent for Razorpay</p>
                </div>
                <button onclick="fetch('/batch/run-simulation', {{method: 'POST'}}).then(() => location.reload())" 
                        class="bg-amber-500 hover:bg-amber-600 text-black font-semibold text-sm px-4 py-2 rounded transition">
                    Run Batch Simulation
                </button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-lg">
                    <p class="text-xs uppercase tracking-wider text-zinc-400">Transactions Ingested</p>
                    <p class="text-2xl font-bold text-white mt-1">{total_count}</p>
                </div>
                <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-lg">
                    <p class="text-xs uppercase tracking-wider text-zinc-400">Total Recovered</p>
                    <p class="text-2xl font-bold text-green-400 mt-1">₹{recovered_amt:,.2f}</p>
                </div>
                <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-lg">
                    <p class="text-xs uppercase tracking-wider text-zinc-400">Successful Recoveries</p>
                    <p class="text-2xl font-bold text-white mt-1">{recovered}</p>
                </div>
                <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-lg">
                    <p class="text-xs uppercase tracking-wider text-zinc-400">Policy Stops (Compliance)</p>
                    <p class="text-2xl font-bold text-red-400 mt-1">{stopped}</p>
                </div>
            </div>

            <div class="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
                <div class="px-4 py-3 border-b border-zinc-800">
                    <h2 class="text-sm font-semibold uppercase tracking-wider text-zinc-400">Recent Recovery Audit Feed (First 15 Records)</h2>
                </div>
                <table class="w-full text-left border-collapse">
                    <thead class="bg-zinc-900/80 text-xs uppercase text-zinc-400 border-b border-zinc-800">
                        <tr>
                            <th class="py-3 px-4">Event ID</th>
                            <th class="py-3 px-4">Customer</th>
                            <th class="py-3 px-4">Amount</th>
                            <th class="py-3 px-4">Failure Code</th>
                            <th class="py-3 px-4">Policy Action</th>
                            <th class="py-3 px-4">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows if rows else '<tr><td colspan="6" class="p-6 text-center text-zinc-500">No records processed yet. Click "Run Batch Simulation" above.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """