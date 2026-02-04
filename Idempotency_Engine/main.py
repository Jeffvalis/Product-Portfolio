import random
import uuid
from decimal import Decimal, getcontext

getcontext().prec = 28  # High precision for financial calculations


class PaymentProcessor:
    """
    Business Logic (PM perspective):
    - This class simulates idempotent payment processing for a Nigerian bank.
    - Each payment is keyed by an `idempotency_key` to ensure the same logical
      payment is only charged once, even if there are network failures and retries.
    - A mock in-memory `processed_keys` dictionary represents a payments table.
    """

    def __init__(self):
        """
        Business Logic (PM perspective):
        - Initialize an empty in-memory store of processed payments keyed by
          `idempotency_key`. This allows us to safely handle retries without
          double-charging users.
        """
        self.processed_keys: dict[str, str] = {}

    def process_payment(self, idempotency_key: str, amount: Decimal) -> str:
        """
        Business Logic (PM perspective):
        - First, ensure idempotency: if the `idempotency_key` was seen before,
          immediately return the stored success response (so repeated calls do
          NOT charge the customer again).
        - For a brand‑new key, we simulate a successful debit on the bank, store
          the result under that key, and then simulate a 20% chance that the
          *response to the customer* fails due to Nigerian network issues.
        - This models a realistic scenario where the customer has actually been
          charged, but the app still sees a connection error and is forced to
          retry with the same idempotency key.

        :param idempotency_key: Unique identifier for a single logical payment.
        :param amount: Monetary amount to be charged as a `Decimal`.
        :return: A success message string if processing succeeds. The caller will
                 translate this message into a user-friendly status label.
        :raises ConnectionError: Simulating transient Nigerian bank network failure
                                 after a successful debit.
        """
        # Idempotency path: if we've already processed this payment, just return the result.
        if idempotency_key in self.processed_keys:
            return "Payment already processed."

        # Simulate successful payment processing (the debit itself succeeds)
        print(f"Processing payment of {amount} with key {idempotency_key}...")
        result = f"Success: processed payment of {amount} with key {idempotency_key}"
        self.processed_keys[idempotency_key] = result

        # Now simulate a 20% chance that the network fails AFTER success.
        if random.random() < 0.2:
            # From the product perspective, the bank has taken the money,
            # but the user sees a connection error and will likely retry.
            raise ConnectionError(
                "Payment succeeded but Nigerian bank network failed while responding."
            )

        return result


processor = PaymentProcessor()

"""
Business Logic (PM perspective):
- We now simulate a stream of independent Nigerian payments, each with a randomly
  generated UUID idempotency key.
- For each new payment, we attempt to process it once:
  - If it succeeds, we label it "Successful" and move on to the next transaction.
  - If the network fails after success (simulated ConnectionError), we label that
    transaction as "Failed", remember its key, and then immediately retry that
    same key once more to demonstrate idempotency ("Already processed").
- After we encounter the first failure and perform the retry, we stop the
  simulation and print out the contents of the mock database so we can see
  which transactions ended up being stored as successful.
"""

max_transactions = 8
failed_key = None
failed_amount = None

for tx_number in range(1, max_transactions + 1):
    if failed_key is not None:
        # We already hit a failing transaction; stop creating new ones.
        break

    # Generate a brand-new UUID for this transaction's idempotency key.
    current_key = str(uuid.uuid4())
    current_amount = Decimal("1000.00")

    try:
        outcome_message = processor.process_payment(current_key, current_amount)
        # If we get here, no ConnectionError was raised for this transaction.
        status = "Already processed" if outcome_message == "Payment already processed." else "Successful"
    except ConnectionError:
        # The payment actually succeeded at the bank level but the network failed
        # when responding. From the simulation's perspective we mark it as "Failed"
        # and remember this key for a retry.
        status = "Failed"
        failed_key = current_key
        failed_amount = current_amount

    print(f"Transaction {tx_number}: Key={current_key}, Status={status}")

# If we encountered a failure, retry that exact same idempotency key once.
if failed_key is not None:
    try:
        retry_outcome = processor.process_payment(failed_key, failed_amount)
        retry_status = "Already processed" if retry_outcome == "Payment already processed." else "Successful"
    except ConnectionError:
        retry_status = "Failed"

    print(f"\nRetry Transaction: Key={failed_key}, Status={retry_status}")

# Finally, show what the "database" (processed_keys) contains.
print("\nDatabase snapshot (processed_keys):")
for stored_key in processor.processed_keys:
    print(f"- Stored Key={stored_key}")
