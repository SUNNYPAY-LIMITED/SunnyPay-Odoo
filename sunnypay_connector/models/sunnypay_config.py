# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SunnyPayConfig(models.TransientModel):
    """SunnyPay API Configuration Settings."""
    _inherit = 'res.config.settings'
    _description = 'SunnyPay Configuration'

    sunnypay_api_url = fields.Char(
        string='API URL',
        config_parameter='sunnypay_connector.api_url',
        default='http://localhost:4500',
        help='Base URL for the SunnyPay API (e.g., https://api.sunnypay.co.ke)',
    )
    sunnypay_api_key = fields.Char(
        string='API Key',
        config_parameter='sunnypay_connector.api_key',
        help='Your SunnyPay API key for authentication',
    )
    sunnypay_api_secret = fields.Char(
        string='API Secret',
        config_parameter='sunnypay_connector.api_secret',
        help='Your SunnyPay API secret',
    )
    sunnypay_webhook_secret = fields.Char(
        string='Webhook Secret',
        config_parameter='sunnypay_connector.webhook_secret',
        help='Secret key used to verify incoming webhooks from SunnyPay',
    )
    sunnypay_environment = fields.Selection(
        [
            ('sandbox', 'Sandbox'),
            ('production', 'Production'),
        ],
        string='Environment',
        config_parameter='sunnypay_connector.environment',
        default='sandbox',
        help='Select sandbox for testing or production for live transactions',
    )
    sunnypay_auto_sync = fields.Boolean(
        string='Enable Auto Sync',
        config_parameter='sunnypay_connector.auto_sync',
        default=True,
        help='Automatically sync data from SunnyPay via cron jobs',
    )
    sunnypay_sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        config_parameter='sunnypay_connector.sync_interval',
        default=15,
        help='How often to sync transactions from SunnyPay (in minutes)',
    )

    def action_test_connection(self):
        """Test the connection to SunnyPay API."""
        self.ensure_one()
        try:
            from ..services.sunnypay_api import SunnyPayAPI
            api = SunnyPayAPI(self.env)
            result = api.test_connection()
            if result.get('status') == 'ok' or result.get('status') == 'healthy':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection Successful',
                        'message': f"Connected to SunnyPay ({result.get('service', 'API')})",
                        'type': 'success',
                        'sticky': False,
                    },
                }
            else:
                raise UserError(f"Unexpected response: {result}")
        except Exception as e:
            _logger.error('SunnyPay connection test failed: %s', str(e))
            raise UserError(f'Connection failed: {str(e)}')

    def action_sync_all(self):
        """Manually trigger a full sync from SunnyPay."""
        self.ensure_one()
        try:
            self.env['sunnypay.transaction'].action_sync_from_sunnypay()
            self.env['sunnypay.merchant'].action_sync_from_sunnypay()
            self.env['sunnypay.invoice'].action_sync_from_sunnypay()
            self.env['sunnypay.customer'].action_sync_from_sunnypay()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Complete',
                    'message': 'All data has been synced from SunnyPay.',
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            _logger.error('SunnyPay full sync failed: %s', str(e))
            raise UserError(f'Sync failed: {str(e)}')
