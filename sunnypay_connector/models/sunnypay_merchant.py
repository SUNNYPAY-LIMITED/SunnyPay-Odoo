# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SunnyPayMerchant(models.Model):
    """SunnyPay Merchant / Business Account."""
    _name = 'sunnypay.merchant'
    _description = 'SunnyPay Merchant'
    _order = 'name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Business Name',
        required=True,
        tracking=True,
    )
    sunnypay_id = fields.Char(
        string='SunnyPay Merchant ID',
        readonly=True,
        copy=False,
        index=True,
    )

    # Business Info
    email = fields.Char(string='Email', tracking=True)
    phone = fields.Char(string='Phone')
    website = fields.Char(string='Website')
    business_type = fields.Selection(
        [
            ('individual', 'Individual'),
            ('business', 'Business'),
            ('enterprise', 'Enterprise'),
            ('institution', 'Financial Institution'),
        ],
        string='Business Type',
        default='business',
        tracking=True,
    )
    industry = fields.Char(string='Industry')
    country_id = fields.Many2one(
        'res.country',
        string='Country',
    )
    registration_number = fields.Char(string='Registration Number')
    tax_id = fields.Char(string='Tax ID')

    # Verification
    verification_status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('under_review', 'Under Review'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
            ('suspended', 'Suspended'),
        ],
        string='Verification Status',
        default='pending',
        tracking=True,
    )

    # API Access
    api_key_tier = fields.Selection(
        [
            ('sandbox', 'Sandbox'),
            ('development', 'Development'),
            ('production', 'Production'),
        ],
        string='API Key Tier',
        default='sandbox',
    )

    # Financial
    total_volume = fields.Monetary(
        string='Total Volume',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    settlement_currency = fields.Char(string='Settlement Currency')

    # Relations
    transaction_ids = fields.One2many(
        'sunnypay.transaction',
        'merchant_id',
        string='Transactions',
    )
    transaction_count = fields.Integer(
        string='Transaction Count',
        compute='_compute_transaction_count',
    )
    invoice_ids = fields.One2many(
        'sunnypay.invoice',
        'merchant_id',
        string='Invoices',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Odoo Contact',
        help='Linked Odoo contact for this merchant',
    )

    # Metadata
    created_at = fields.Datetime(string='Created At', readonly=True)
    active = fields.Boolean(string='Active', default=True)

    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)

    def action_view_transactions(self):
        """Open list of transactions for this merchant."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Transactions - {self.name}',
            'res_model': 'sunnypay.transaction',
            'view_mode': 'tree,form',
            'domain': [('merchant_id', '=', self.id)],
            'context': {'default_merchant_id': self.id},
        }

    def action_sync_from_sunnypay(self):
        """Sync merchants from SunnyPay API."""
        try:
            from ..services.sunnypay_api import SunnyPayAPI
            api = SunnyPayAPI(self.env)
            merchants = api.get_merchants()

            for merchant_data in merchants:
                existing = self.search([
                    ('sunnypay_id', '=', merchant_data.get('id'))
                ], limit=1)

                vals = self._prepare_merchant_vals(merchant_data)
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)

            _logger.info('Synced %d merchants from SunnyPay', len(merchants))
        except Exception as e:
            _logger.error('Merchant sync failed: %s', str(e))
            raise UserError(f'Merchant sync failed: {str(e)}')

    def _prepare_merchant_vals(self, data):
        """Map SunnyPay API response to Odoo field values."""
        country = False
        if data.get('country'):
            country = self.env['res.country'].search([
                ('code', '=', data['country'].upper())
            ], limit=1)

        type_map = {
            'individual': 'individual',
            'personal': 'individual',
            'business': 'business',
            'enterprise': 'enterprise',
            'institution': 'institution',
            'financial_institution': 'institution',
        }

        return {
            'sunnypay_id': data.get('id'),
            'name': data.get('businessName') or data.get('name', 'Unknown'),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'website': data.get('website', ''),
            'business_type': type_map.get(data.get('accountType', ''), 'business'),
            'industry': data.get('industry', ''),
            'country_id': country.id if country else False,
            'registration_number': data.get('registrationNumber', ''),
            'tax_id': data.get('taxId', ''),
            'verification_status': data.get('verificationStatus', 'pending'),
            'api_key_tier': data.get('apiKeyTier', 'sandbox'),
            'created_at': data.get('createdAt'),
        }

    def action_create_partner(self):
        """Create an Odoo contact (res.partner) from this merchant."""
        self.ensure_one()
        if self.partner_id:
            raise UserError('This merchant is already linked to an Odoo contact.')

        partner = self.env['res.partner'].create({
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'company_type': 'company' if self.business_type != 'individual' else 'person',
            'country_id': self.country_id.id if self.country_id else False,
            'vat': self.tax_id,
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
