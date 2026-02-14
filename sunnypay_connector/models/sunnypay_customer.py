# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SunnyPayCustomer(models.Model):
    """SunnyPay Customer."""
    _name = 'sunnypay.customer'
    _description = 'SunnyPay Customer'
    _order = 'name asc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name', required=True, tracking=True)
    sunnypay_id = fields.Char(
        string='SunnyPay Customer ID',
        readonly=True,
        copy=False,
        index=True,
    )

    # Contact
    email = fields.Char(string='Email', tracking=True)
    phone = fields.Char(string='Phone')
    sunny_tag = fields.Char(string='SunnyTag', help='Unique SunnyPay identifier')

    # Location
    country_id = fields.Many2one('res.country', string='Country')
    timezone = fields.Char(string='Timezone')
    locale = fields.Char(string='Locale')

    # Account
    account_type = fields.Selection(
        [
            ('personal', 'Personal'),
            ('business', 'Business'),
            ('developer', 'Developer'),
        ],
        string='Account Type',
        default='personal',
    )
    preferred_currency = fields.Char(string='Preferred Currency', default='USD')

    # Relations
    transaction_ids = fields.One2many(
        'sunnypay.transaction',
        'customer_id',
        string='Transactions',
    )
    transaction_count = fields.Integer(
        string='Transactions',
        compute='_compute_transaction_count',
    )
    total_spent = fields.Monetary(
        string='Total Spent',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Odoo Contact',
        help='Linked Odoo contact',
    )

    # Metadata
    created_at = fields.Datetime(string='Joined', readonly=True)
    last_transaction_at = fields.Datetime(string='Last Transaction', readonly=True)
    active = fields.Boolean(default=True)

    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)

    @api.depends('transaction_ids.amount', 'transaction_ids.status')
    def _compute_totals(self):
        for record in self:
            completed = record.transaction_ids.filtered(
                lambda t: t.status == 'completed'
            )
            record.total_spent = sum(completed.mapped('amount'))

    def action_view_transactions(self):
        """Open list of transactions for this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Transactions - {self.name}',
            'res_model': 'sunnypay.transaction',
            'view_mode': 'tree,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
        }

    def action_sync_from_sunnypay(self):
        """Sync customers from SunnyPay API."""
        try:
            from ..services.sunnypay_api import SunnyPayAPI
            api = SunnyPayAPI(self.env)
            customers = api.get_customers()

            for cust_data in customers:
                existing = self.search([
                    ('sunnypay_id', '=', cust_data.get('id'))
                ], limit=1)

                vals = self._prepare_customer_vals(cust_data)
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)

            _logger.info('Synced %d customers from SunnyPay', len(customers))
        except Exception as e:
            _logger.error('Customer sync failed: %s', str(e))
            raise UserError(f'Customer sync failed: {str(e)}')

    def _prepare_customer_vals(self, data):
        """Map SunnyPay API response to Odoo field values."""
        country = False
        if data.get('country'):
            country = self.env['res.country'].search([
                ('code', '=', data['country'].upper())
            ], limit=1)

        type_map = {
            'personal': 'personal',
            'business': 'business',
            'developer': 'developer',
        }

        return {
            'sunnypay_id': data.get('id'),
            'name': f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()
                    or data.get('name', 'Unknown'),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'sunny_tag': data.get('sunnyTag', ''),
            'country_id': country.id if country else False,
            'timezone': data.get('timezone', ''),
            'locale': data.get('locale', ''),
            'account_type': type_map.get(data.get('accountType', ''), 'personal'),
            'preferred_currency': data.get('currency', 'USD'),
            'created_at': data.get('createdAt'),
            'last_transaction_at': data.get('lastLoginAt'),
        }

    def action_create_partner(self):
        """Create an Odoo contact (res.partner) from this customer."""
        self.ensure_one()
        if self.partner_id:
            raise UserError('This customer is already linked to an Odoo contact.')

        partner = self.env['res.partner'].create({
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'company_type': 'person',
            'country_id': self.country_id.id if self.country_id else False,
        })
        self.partner_id = partner.id
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Contact Created',
                'message': f'Odoo contact "{partner.name}" created and linked.',
                'type': 'success',
                'sticky': False,
            },
        }
