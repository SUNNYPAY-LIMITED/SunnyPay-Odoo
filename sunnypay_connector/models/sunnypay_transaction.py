# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SunnyPayTransaction(models.Model):
    """SunnyPay Payment Transaction."""
    _name = 'sunnypay.transaction'
    _description = 'SunnyPay Transaction'
    _order = 'transaction_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    sunnypay_id = fields.Char(
        string='SunnyPay Transaction ID',
        readonly=True,
        copy=False,
        index=True,
        help='Unique transaction identifier from SunnyPay',
    )
    correlation_id = fields.Char(
        string='Correlation ID',
        readonly=True,
        help='Request correlation ID for tracing',
    )

    # Amount & Currency
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    fee_amount = fields.Monetary(
        string='Fee',
        currency_field='currency_id',
    )
    net_amount = fields.Monetary(
        string='Net Amount',
        currency_field='currency_id',
        compute='_compute_net_amount',
        store=True,
    )

    # Status
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
            ('cancelled', 'Cancelled'),
            ('disputed', 'Disputed'),
        ],
        string='Status',
        default='pending',
        required=True,
        tracking=True,
    )
    status_color = fields.Integer(
        string='Status Color',
        compute='_compute_status_color',
    )

    # Payment Method
    payment_method = fields.Selection(
        [
            ('mpesa', 'M-Pesa'),
            ('mtn_momo', 'MTN MoMo'),
            ('airtel_money', 'Airtel Money'),
            ('tigo_pesa', 'Tigo Pesa'),
            ('card', 'Card'),
            ('bank_transfer', 'Bank Transfer'),
            ('crypto', 'Cryptocurrency'),
            ('wallet', 'Wallet'),
            ('bnpl', 'Buy Now Pay Later'),
            ('qr_code', 'QR Code'),
            ('ussd', 'USSD'),
        ],
        string='Payment Method',
        required=True,
        tracking=True,
    )
    processor = fields.Char(
        string='Processor',
        readonly=True,
        help='Payment processor that handled this transaction',
    )

    # Relations
    merchant_id = fields.Many2one(
        'sunnypay.merchant',
        string='Merchant',
        ondelete='set null',
    )
    customer_id = fields.Many2one(
        'sunnypay.customer',
        string='Customer',
        ondelete='set null',
    )
    invoice_id = fields.Many2one(
        'sunnypay.invoice',
        string='Invoice',
        ondelete='set null',
    )

    # Customer Info (denormalized for quick display)
    customer_name = fields.Char(string='Customer Name')
    customer_email = fields.Char(string='Customer Email')
    customer_phone = fields.Char(string='Customer Phone')

    # Metadata
    transaction_date = fields.Datetime(
        string='Transaction Date',
        default=fields.Datetime.now,
        required=True,
    )
    description = fields.Text(string='Description')
    error_message = fields.Text(string='Error Message')
    metadata = fields.Text(string='Raw Metadata (JSON)')

    @api.depends('amount', 'fee_amount')
    def _compute_net_amount(self):
        for record in self:
            record.net_amount = record.amount - (record.fee_amount or 0.0)

    def _compute_status_color(self):
        color_map = {
            'pending': 3,       # Yellow
            'processing': 4,    # Light blue
            'completed': 10,    # Green
            'failed': 1,        # Red
            'refunded': 2,      # Orange
            'cancelled': 7,     # Grey
            'disputed': 9,      # Purple
        }
        for record in self:
            record.status_color = color_map.get(record.status, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sunnypay.transaction'
                ) or 'New'
        return super().create(vals_list)

    def action_sync_from_sunnypay(self):
        """Sync transactions from SunnyPay API."""
        try:
            from ..services.sunnypay_api import SunnyPayAPI
            api = SunnyPayAPI(self.env)
            transactions = api.get_transactions()

            for txn_data in transactions:
                existing = self.search([
                    ('sunnypay_id', '=', txn_data.get('id'))
                ], limit=1)

                vals = self._prepare_transaction_vals(txn_data)
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)

            _logger.info('Synced %d transactions from SunnyPay', len(transactions))
        except Exception as e:
            _logger.error('Transaction sync failed: %s', str(e))
            raise UserError(f'Transaction sync failed: {str(e)}')

    def _prepare_transaction_vals(self, data):
        """Map SunnyPay API response to Odoo field values."""
        # Find currency
        currency = self.env['res.currency'].search([
            ('name', '=', data.get('currency', 'USD'))
        ], limit=1)

        # Map payment method
        method_map = {
            'mpesa': 'mpesa',
            'm-pesa': 'mpesa',
            'mtn': 'mtn_momo',
            'mtn_momo': 'mtn_momo',
            'airtel': 'airtel_money',
            'airtel_money': 'airtel_money',
            'tigo': 'tigo_pesa',
            'card': 'card',
            'bank_transfer': 'bank_transfer',
            'crypto': 'crypto',
            'wallet': 'wallet',
            'bnpl': 'bnpl',
            'qr_code': 'qr_code',
            'ussd': 'ussd',
        }

        return {
            'sunnypay_id': data.get('id'),
            'amount': float(data.get('amount', 0)),
            'currency_id': currency.id if currency else self.env.company.currency_id.id,
            'status': data.get('status', 'pending'),
            'payment_method': method_map.get(data.get('method', ''), 'card'),
            'processor': data.get('processor', ''),
            'customer_name': data.get('customerName', ''),
            'customer_email': data.get('customerEmail', ''),
            'customer_phone': data.get('customerPhone', ''),
            'description': data.get('description', ''),
            'correlation_id': data.get('correlationId', ''),
            'transaction_date': data.get('createdAt', fields.Datetime.now()),
            'fee_amount': float(data.get('fee', 0)),
        }

    def action_refund(self):
        """Initiate a refund for this transaction."""
        self.ensure_one()
        if self.status != 'completed':
            raise UserError('Only completed transactions can be refunded.')
        try:
            from ..services.sunnypay_api import SunnyPayAPI
            api = SunnyPayAPI(self.env)
            result = api.create_refund(self.sunnypay_id, self.amount)
            if result.get('success'):
                self.write({'status': 'refunded'})
            else:
                raise UserError(f"Refund failed: {result.get('error', 'Unknown error')}")
        except UserError:
            raise
        except Exception as e:
            raise UserError(f'Refund failed: {str(e)}')

    def action_view_in_sunnypay(self):
        """Open this transaction in the SunnyPay dashboard."""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'sunnypay_connector.api_url', 'https://app.sunnypay.io'
        )
        return {
            'type': 'ir.actions.act_url',
            'url': f'{base_url}/transactions/{self.sunnypay_id}',
            'target': 'new',
        }
