# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SunnyPayInvoice(models.Model):
    """SunnyPay Invoice."""
    _name = 'sunnypay.invoice'
    _description = 'SunnyPay Invoice'
    _order = 'due_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Invoice Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    sunnypay_id = fields.Char(
        string='SunnyPay Invoice ID',
        readonly=True,
        copy=False,
        index=True,
    )

    # Amounts
    amount = fields.Monetary(
        string='Total Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    amount_paid = fields.Monetary(
        string='Amount Paid',
        currency_field='currency_id',
    )
    amount_due = fields.Monetary(
        string='Amount Due',
        currency_field='currency_id',
        compute='_compute_amount_due',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    # Status
    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('viewed', 'Viewed'),
            ('partially_paid', 'Partially Paid'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # Dates
    issue_date = fields.Date(
        string='Issue Date',
        default=fields.Date.today,
    )
    due_date = fields.Date(
        string='Due Date',
        tracking=True,
    )

    # Relations
    merchant_id = fields.Many2one(
        'sunnypay.merchant',
        string='Merchant',
        ondelete='set null',
    )
    transaction_ids = fields.One2many(
        'sunnypay.transaction',
        'invoice_id',
        string='Payments',
    )
    odoo_invoice_id = fields.Many2one(
        'account.move',
        string='Odoo Invoice',
        help='Linked native Odoo invoice for accounting',
    )

    # Customer Details
    customer_name = fields.Char(string='Customer Name')
    customer_email = fields.Char(string='Customer Email')
    customer_phone = fields.Char(string='Customer Phone')
    customer_address = fields.Text(string='Customer Address')

    # Invoice Content
    description = fields.Text(string='Description')
    notes = fields.Text(string='Notes')
    item_lines = fields.Text(
        string='Line Items (JSON)',
        help='Invoice line items stored as JSON from SunnyPay',
    )
    payment_link = fields.Char(string='Payment Link')

    @api.depends('amount', 'amount_paid')
    def _compute_amount_due(self):
        for record in self:
            record.amount_due = record.amount - (record.amount_paid or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sunnypay.invoice'
                ) or 'New'
        return super().create(vals_list)

    def action_sync_from_sunnypay(self):
        """Sync invoices from SunnyPay API."""
        try:
            from ..services.sunnypay_api import SunnyPayAPI
            api = SunnyPayAPI(self.env)
            invoices = api.get_invoices()

            for inv_data in invoices:
                existing = self.search([
                    ('sunnypay_id', '=', inv_data.get('id'))
                ], limit=1)

                vals = self._prepare_invoice_vals(inv_data)
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)

            _logger.info('Synced %d invoices from SunnyPay', len(invoices))
        except Exception as e:
            _logger.error('Invoice sync failed: %s', str(e))
            raise UserError(f'Invoice sync failed: {str(e)}')

    def _prepare_invoice_vals(self, data):
        """Map SunnyPay API response to Odoo field values."""
        import json
        currency = self.env['res.currency'].search([
            ('name', '=', data.get('currency', 'USD'))
        ], limit=1)

        return {
            'sunnypay_id': data.get('id'),
            'amount': float(data.get('amount', 0)),
            'amount_paid': float(data.get('amountPaid', 0)),
            'currency_id': currency.id if currency else self.env.company.currency_id.id,
            'status': data.get('status', 'draft'),
            'issue_date': data.get('issueDate'),
            'due_date': data.get('dueDate'),
            'customer_name': data.get('customerName', ''),
            'customer_email': data.get('customerEmail', ''),
            'customer_phone': data.get('customerPhone', ''),
            'customer_address': data.get('customerAddress', ''),
            'description': data.get('description', ''),
            'notes': data.get('notes', ''),
            'item_lines': json.dumps(data.get('items', [])),
            'payment_link': data.get('paymentLink', ''),
        }

    def action_create_odoo_invoice(self):
        """Create a native Odoo invoice (account.move) from this SunnyPay invoice."""
        self.ensure_one()
        if self.odoo_invoice_id:
            raise UserError('This invoice is already linked to an Odoo invoice.')

        import json
        items = []
        if self.item_lines:
            try:
                items = json.loads(self.item_lines)
            except json.JSONDecodeError:
                items = []

        # Find or create partner
        partner = False
        if self.customer_email:
            partner = self.env['res.partner'].search([
                ('email', '=', self.customer_email)
            ], limit=1)
        if not partner and self.customer_name:
            partner = self.env['res.partner'].create({
                'name': self.customer_name,
                'email': self.customer_email,
                'phone': self.customer_phone,
            })

        # Build invoice lines
        invoice_lines = []
        if items:
            for item in items:
                invoice_lines.append((0, 0, {
                    'name': item.get('description', 'SunnyPay Item'),
                    'quantity': float(item.get('quantity', 1)),
                    'price_unit': float(item.get('unitPrice', item.get('amount', 0))),
                }))
        else:
            invoice_lines.append((0, 0, {
                'name': self.description or 'SunnyPay Invoice',
                'quantity': 1,
                'price_unit': self.amount,
            }))

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id if partner else False,
            'currency_id': self.currency_id.id,
            'invoice_date': self.issue_date,
            'invoice_date_due': self.due_date,
            'invoice_line_ids': invoice_lines,
            'ref': f'SunnyPay: {self.name}',
        })

        self.odoo_invoice_id = move.id
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Invoice Created',
                'message': f'Odoo invoice {move.name} created.',
                'type': 'success',
                'sticky': False,
            },
        }
