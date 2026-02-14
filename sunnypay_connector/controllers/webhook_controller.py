# -*- coding: utf-8 -*-
"""
SunnyPay Webhook Controller.

Receives real-time payment notifications from SunnyPay and
creates/updates transaction records in Odoo.
"""
import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SunnyPayWebhookController(http.Controller):
    """Handle incoming webhooks from SunnyPay."""

    @http.route(
        '/sunnypay/webhook',
        type='json',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def handle_webhook(self):
        """
        Main webhook endpoint.

        Expected payload:
        {
            "event": "payment.completed",
            "data": {
                "id": "txn_123...",
                "amount": 1000,
                "currency": "KES",
                "status": "completed",
                ...
            },
            "timestamp": "2026-01-01T00:00:00Z"
        }
        """
        try:
            # Parse the request body
            data = request.jsonrequest
            if not data:
                _logger.warning('SunnyPay webhook: empty payload')
                return {'status': 'error', 'message': 'Empty payload'}

            # Verify webhook signature
            if not self._verify_signature(request):
                _logger.warning('SunnyPay webhook: invalid signature')
                return {'status': 'error', 'message': 'Invalid signature'}

            event = data.get('event', '')
            event_data = data.get('data', {})

            _logger.info('SunnyPay webhook received: %s', event)

            # Route to appropriate handler
            if event.startswith('payment.'):
                return self._handle_payment_event(event, event_data)
            elif event.startswith('merchant.'):
                return self._handle_merchant_event(event, event_data)
            elif event.startswith('invoice.'):
                return self._handle_invoice_event(event, event_data)
            else:
                _logger.info('SunnyPay webhook: unhandled event type: %s', event)
                return {'status': 'ok', 'message': f'Event {event} acknowledged'}

        except Exception as e:
            _logger.error('SunnyPay webhook error: %s', str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route(
        '/sunnypay/webhook/test',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def webhook_health(self):
        """Health check endpoint for webhook verification."""
        return request.make_json_response({
            'status': 'ok',
            'service': 'sunnypay-odoo-connector',
            'endpoint': '/sunnypay/webhook',
        })

    def _verify_signature(self, req):
        """
        Verify the webhook signature from SunnyPay.

        SunnyPay sends a signature in the X-SunnyPay-Signature header,
        computed as HMAC-SHA256 of the request body using the webhook secret.
        """
        signature = req.httprequest.headers.get('X-SunnyPay-Signature', '')
        if not signature:
            # If no webhook secret is configured, skip verification
            webhook_secret = request.env['ir.config_parameter'].sudo().get_param(
                'sunnypay_connector.webhook_secret', ''
            )
            if not webhook_secret:
                return True  # No secret configured, allow all
            return False  # Secret configured but no signature provided

        webhook_secret = request.env['ir.config_parameter'].sudo().get_param(
            'sunnypay_connector.webhook_secret', ''
        )
        if not webhook_secret:
            return True  # No secret to verify against

        # Compute expected signature
        body = req.httprequest.get_data(as_text=True)
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def _handle_payment_event(self, event, data):
        """Handle payment-related webhook events."""
        Transaction = request.env['sunnypay.transaction'].sudo()

        sunnypay_id = data.get('id', '')
        if not sunnypay_id:
            return {'status': 'error', 'message': 'Missing transaction ID'}

        existing = Transaction.search([
            ('sunnypay_id', '=', sunnypay_id)
        ], limit=1)

        vals = Transaction._prepare_transaction_vals(data)

        if event == 'payment.created':
            if not existing:
                Transaction.create(vals)
                _logger.info('Created transaction from webhook: %s', sunnypay_id)
        elif event in ('payment.completed', 'payment.failed',
                       'payment.refunded', 'payment.cancelled'):
            if existing:
                existing.write(vals)
                _logger.info('Updated transaction from webhook: %s → %s',
                             sunnypay_id, data.get('status'))
            else:
                Transaction.create(vals)
                _logger.info('Created transaction from webhook (late): %s', sunnypay_id)

        return {'status': 'ok', 'transaction_id': sunnypay_id}

    def _handle_merchant_event(self, event, data):
        """Handle merchant-related webhook events."""
        Merchant = request.env['sunnypay.merchant'].sudo()

        sunnypay_id = data.get('id', '')
        if not sunnypay_id:
            return {'status': 'error', 'message': 'Missing merchant ID'}

        existing = Merchant.search([
            ('sunnypay_id', '=', sunnypay_id)
        ], limit=1)

        vals = Merchant._prepare_merchant_vals(data)

        if existing:
            existing.write(vals)
        else:
            Merchant.create(vals)

        _logger.info('Merchant webhook processed: %s (%s)', sunnypay_id, event)
        return {'status': 'ok', 'merchant_id': sunnypay_id}

    def _handle_invoice_event(self, event, data):
        """Handle invoice-related webhook events."""
        Invoice = request.env['sunnypay.invoice'].sudo()

        sunnypay_id = data.get('id', '')
        if not sunnypay_id:
            return {'status': 'error', 'message': 'Missing invoice ID'}

        existing = Invoice.search([
            ('sunnypay_id', '=', sunnypay_id)
        ], limit=1)

        vals = Invoice._prepare_invoice_vals(data)

        if existing:
            existing.write(vals)
        else:
            Invoice.create(vals)

        _logger.info('Invoice webhook processed: %s (%s)', sunnypay_id, event)
        return {'status': 'ok', 'invoice_id': sunnypay_id}
