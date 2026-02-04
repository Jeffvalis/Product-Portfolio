# Idempotency_Engine

## Overview

## Idempotent Disbursement Engine – Product Requirements Document (PRD)

### 1. Problem Statement

**Context**

- **Nigerian banking rails are prone to intermittent failures**, especially:
  - Network timeouts between businesses/fintechs and partner banks/switches
  - Slow or dropped responses from  NIBSS Instant Payments/transfer APIs
  - Occasional partner-side retries without clear traceability

- In this environment, **payment/disbursement requests can be left in an unknown state**:
  - We send a disbursement (e.g., withdrawal to bank account).
  - The network times out before we receive a definitive success/failure response.
  - Frontend or backend retries the same transaction.
  - The partner may:
    - Process the first and ignore the second, or
    - Process both, **causing duplicate payouts** to the same user.

**Core Problem**

An **idempotent disbursement engine** is needed that guarantees:

- A **single logical disbursement request** is **processed at most once**, regardless of:
  - Network timeouts
  - Client or service retries
  - Message duplication between internal services
- **Consistent system of record** even when external bank APIs are unreliable.

Without this:

- Users can receive **duplicate payouts** or experience **stuck/unknown status** withdrawals.
- Finance and Operations spend time doing **manual reconciliations**.
- Trust in the Company’s withdrawals and reliability is eroded.

---

### 2. User Story

**Primary User Story**

- **As a customer,**  
  **I want** my withdrawal to my bank account to either go through once or not at all,  
  **so that** I’m never overpaid due to system errors and I can trust that my transaction history and wallet balance are always correct, even when “the network is bad”.

**Supporting Stories**

- **As a Customer Support agent,** I want to see a clear, single disbursement record and its final status (e.g., `PENDING → SUCCESS` or `PENDING → FAILED`) for each withdrawal request, so I can confidently explain outcomes to users without worrying about hidden duplicates.
- **As a Finance/Operations analyst,** I want transaction logs and reconciliation reports that show a **one-to-one mapping** between internal disbursement requests and successful bank transfers, so I can quickly detect and prevent payout leakages from duplicate sends.
- **As a Backend Engineer,** I want a standard, reusable idempotent disbursement interface, so that any service initiating payouts can safely retry without writing custom deduplication logic.

---

### 3. Technical Requirements

#### 3.1 Idempotency Model

- **Idempotency Key**
  - Every disbursement request must carry a **unique idempotency key**.
  - The engine must use a **cryptographically strong UUID (e.g., UUIDv4)** as the primary format for idempotency keys.
  - The key must be:
    - **Stable** across retries for the same logical disbursement.
    - **Unique** across different logical disbursements.
- **Key Generation**
  - Keys are generated **by the initiating client/service** (e.g., Withdrawal Service) at the point the user confirms the withdrawal.
  - The same key must be passed through:
    - Internal services
    - Any queue/message broker
    - The final call to the disbursement engine.

#### 3.2 Idempotent Processing Semantics

- **At-most-once guarantee**
  - For a given idempotency key:
    - The **first request** should execute the disbursement logic (create disbursement record, call bank, etc.).
    - Subsequent requests with the **same key** must **not trigger a new disbursement**.
- **Consistent response for duplicates**
  - The engine must respond to a **duplicate request with the same key** by:
    - Returning the **same final result** (status, reference IDs, timestamps) as the original request once it is known.
- **Persistence**
  - Each idempotency key must be persisted with:
    - Request metadata (user, account, amount, bank, etc.).
    - Current state: `RECEIVED`, `IN_PROGRESS`, `SUCCESS`, `FAILED`, `UNKNOWN`.
    - External references: partner bank reference, NIP reference, etc.
    - Timestamps: created, last updated, expiration (if applicable).

#### 3.3 Concurrency & Race Conditions

- The engine must protect against **concurrent requests using the same idempotency key**, e.g.:
  - Two services retry simultaneously.
  - A UI double-submit scenario.
- Implementation must:
  - Use a **transactional lock / unique constraint** on the idempotency key in persistent storage.
  - Ensure that only one request transitions from `RECEIVED` to `IN_PROGRESS` for a given key.
  - Subsequent concurrent attempts:
    - Wait for the first to complete **or**
    - Immediately return the current known state for that key.

#### 3.4 Network Timeout Handling

- **Unknown response handling**
  - When calling external bank APIs:
    - If the call returns success → mark as `SUCCESS` and store external refs.
    - If the call definitively fails (e.g., validation error) → mark as `FAILED` with reason.
    - If there is a **network timeout or ambiguous error**:
      - Mark as `PENDING` or `UNKNOWN`.
      - Schedule **asynchronous reconciliation** (polling/status query or file-based recon).
- **Retry logic**
  - Internal callers may freely retry the same idempotency key; the engine ensures:
    - **No second disbursement** is sent out if the first already succeeded.
    - Status is updated and returned consistently after reconciliation.

#### 3.5 API & Interface Requirements

- **Create/Execute Disbursement**
  - Request:
    - `idempotency_key` (UUID, required)
    - `user_id`, `wallet_id`
    - Destination details: bank code, account number, account name (if needed)
    - `amount` (stored using a precise decimal representation at the system level)
  - Response:
    - `disbursement_id`
    - `idempotency_key`
    - `status` (`RECEIVED`, `IN_PROGRESS`, `SUCCESS`, `FAILED`, `PENDING`, `UNKNOWN`)
    - `external_reference` (if available)
    - `message` / `reason` for failures.
- **Get Disbursement by Idempotency Key**
  - Endpoint to fetch the **current state** and full metadata for a given `idempotency_key`.
- **Idempotent behavior**
  - If `Create/Execute` is called again with the **same `idempotency_key` and identical business parameters**:
    - Return the **same disbursement record**.
  - If `Create/Execute` is called with **same key but different parameters**:
    - Reject with a clear error indicating a conflict on the idempotency key.

#### 3.6 Observability & Audit

- **Logging**
  - Log all state transitions for each idempotency key.
  - Log all external calls (request/response or error/timeout) with correlation to the key.
- **Monitoring & Alerts**
  - Metrics for:
    - Number of disbursements by status.
    - Count of `PENDING/UNKNOWN` states beyond expected SLA.
    - Duplicate request rate per `idempotency_key`.
- **Audit trail**
  - Full history of:
    - Who initiated the disbursement.
    - All retries and who/what triggered them.
    - Final resolution path (manual vs automatic reconciliation).

---

### 4. Success Metrics

- **Reliability & Correctness**
  - **0 confirmed duplicate disbursements** caused by internal retries or network timeouts (post-launch, after a defined stabilization period).
  - **> 99.9% correctness** in mapping internal disbursement requests to external bank transfers over a rolling 30-day window.
- **User Experience**
  - **Reduction in user complaints about withdrawals** related to:
    - “I was debited twice.”
    - “My withdrawal is in limbo/unknown.”
  - Target: **≥ 50% reduction** in such tickets within 3 months of rollout.
- **Operational Efficiency**
  - **≥ 50% reduction** in manual reconciliation time for disbursement-related issues (as reported by Finance/Operations).
  - **Near-zero ad-hoc engineering interventions** to manually fix duplicate payouts in production.
- **System Health**
  - **Successful handling of retries**:
    - At least **95% of retry traffic** is handled without creating additional disbursement records.
  - **Visibility**:
    - 100% of disbursement requests associated with a **traceable idempotency key** in logs and dashboards.

---




