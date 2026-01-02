"""Sample with OCP violation - switch on type instead of polymorphism."""
from typing import Dict


class PaymentProcessor:
    """Payment processor that violates OCP - must modify for new payment types."""

    def process_payment(self, payment: Dict) -> Dict:
        """Process payment - switch on type."""
        payment_type = payment.get("type")

        # OCP violation: Adding new payment type requires modifying this method
        if payment_type == "credit_card":
            return self._process_credit_card(payment)
        elif payment_type == "debit_card":
            return self._process_debit_card(payment)
        elif payment_type == "paypal":
            return self._process_paypal(payment)
        elif payment_type == "bank_transfer":
            return self._process_bank_transfer(payment)
        elif payment_type == "crypto":
            return self._process_crypto(payment)
        else:
            return {"error": f"Unknown payment type: {payment_type}"}

    def _process_credit_card(self, payment: Dict) -> Dict:
        return {"status": "success", "method": "credit_card"}

    def _process_debit_card(self, payment: Dict) -> Dict:
        return {"status": "success", "method": "debit_card"}

    def _process_paypal(self, payment: Dict) -> Dict:
        return {"status": "success", "method": "paypal"}

    def _process_bank_transfer(self, payment: Dict) -> Dict:
        return {"status": "success", "method": "bank_transfer"}

    def _process_crypto(self, payment: Dict) -> Dict:
        return {"status": "success", "method": "crypto"}
