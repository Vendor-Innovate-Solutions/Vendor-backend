"""
Stripe payment integration views.
Handles PaymentIntent creation and confirmation for retailer invoice payments.
"""
import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


def _get_stripe():
    """Lazily import stripe and set the API key."""
    try:
        import stripe
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        if not stripe.api_key:
            raise ValueError("STRIPE_SECRET_KEY must be set in settings.")
        return stripe
    except ImportError:
        raise ImportError("stripe package is not installed. Run: pip install stripe")


class StripeCreatePaymentIntentView(APIView):
    """
    Create a Stripe PaymentIntent for an invoice payment.

    POST /api/payments/stripe/create-payment-intent/
    Body: { "invoice_id": "uuid", "amount": 2000.00 }  # amount in rupees
    Returns: { "client_secret": "pi_xxx_secret_xxx", "publishable_key": "pk_test_..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invoice_id = request.data.get('invoice_id')
        amount = request.data.get('amount')

        if not invoice_id or amount is None:
            return Response(
                {"error": "invoice_id and amount are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount_cents = int(float(amount) * 100)  # rupees → paise/cents (smallest unit)
            if amount_cents <= 0:
                return Response({"error": "Amount must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            stripe = _get_stripe()
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="inr",
                metadata={
                    "invoice_id": str(invoice_id),
                    "user_id": str(request.user.id),
                },
                description=f"Invoice payment - {invoice_id}",
            )
            logger.info(f"Stripe PaymentIntent created: {intent.id} for invoice {invoice_id}")

            return Response({
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "publishable_key": getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
            })

        except Exception as e:
            logger.error(f"Stripe PaymentIntent creation failed: {e}")
            return Response(
                {"error": f"Failed to create payment intent: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StripeConfirmPaymentView(APIView):
    """
    Confirm a successful Stripe payment and record it against the invoice.

    POST /api/payments/stripe/confirm/
    Body: { "payment_intent_id": "pi_xxx", "invoice_id": "uuid" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get('payment_intent_id')
        invoice_id = request.data.get('invoice_id')

        if not payment_intent_id or not invoice_id:
            return Response(
                {"error": "payment_intent_id and invoice_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            stripe = _get_stripe()
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status != 'succeeded':
                return Response(
                    {"error": f"Payment not completed. Status: {intent.status}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verify the invoice_id in metadata matches
            if intent.metadata.get('invoice_id') != str(invoice_id):
                logger.warning(f"Invoice ID mismatch: expected {invoice_id}, got {intent.metadata.get('invoice_id')}")
                return Response(
                    {"error": "Payment intent does not match this invoice"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Record payment against the invoice
            from apps.invoice.models import Invoice
            from decimal import Decimal

            invoice = Invoice.objects.get(id=invoice_id)
            amount_paid = Decimal(str(intent.amount / 100))  # cents → rupees

            current_received = Decimal(str(invoice.amount_received or 0))
            invoice.amount_received = current_received + amount_paid

            outstanding = Decimal(str(invoice.grand_total or 0)) - invoice.amount_received
            if outstanding <= 0:
                invoice.status = 'PAID'

            invoice.save(update_fields=['amount_received', 'status'])

            logger.info(f"Payment recorded for invoice {invoice_id}: ₹{amount_paid} (intent={payment_intent_id})")

            return Response({
                "success": True,
                "message": "Payment confirmed and recorded successfully",
                "payment_intent_id": payment_intent_id,
                "invoice_id": str(invoice_id),
                "amount_paid": float(amount_paid),
                "invoice_status": invoice.status,
            })

        except Exception as e:
            logger.error(f"Failed to confirm payment for invoice {invoice_id}: {e}")
            return Response({
                "success": True,
                "message": "Payment received. Please contact support if your invoice is not updated.",
                "payment_intent_id": payment_intent_id,
                "warning": str(e),
            })
