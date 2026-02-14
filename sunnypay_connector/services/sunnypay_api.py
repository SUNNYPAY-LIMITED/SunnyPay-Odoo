# -*- coding: utf-8 -*-
"""
SunnyPay API Connector Service.

REST client that communicates with the SunnyPay backend API.
Reads credentials from Odoo system parameters set via Settings.
"""
import json
import logging
import requests
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30


class SunnyPayAPI:
    """REST client for communicating with the SunnyPay backend API."""

    def __init__(self, env):
        """
        Initialize the API client.

        Args:
            env: Odoo environment (self.env from a model)
        """
        self.env = env
        params = env['ir.config_parameter'].sudo()
        self.base_url = (
            params.get_param('sunnypay_connector.api_url', 'http://localhost:4500')
            .rstrip('/')
        )
        self.api_key = params.get_param('sunnypay_connector.api_key', '')
        self.api_secret = params.get_param('sunnypay_connector.api_secret', '')
        self.environment = params.get_param('sunnypay_connector.environment', 'sandbox')

    def _get_headers(self):
        """Build authentication headers."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-Key': self.api_key,
            'X-Environment': self.environment,
        }
        if self.api_secret:
            headers['Authorization'] = f'Bearer {self.api_secret}'
        return headers

    def _request(self, method, endpoint, data=None, params=None):
        """
        Make an HTTP request to the SunnyPay API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., '/payments')
            data: Request body (dict)
            params: Query parameters (dict)

        Returns:
            dict: Parsed JSON response

        Raises:
            UserError: If the request fails
        """
        url = f'{self.base_url}{endpoint}'
        headers = self._get_headers()

        try:
            _logger.info('SunnyPay API %s %s', method, url)
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            _logger.error('Cannot connect to SunnyPay API at %s', url)
            raise UserError(
                f'Cannot connect to SunnyPay API at {self.base_url}. '
                f'Please check the API URL in Settings → SunnyPay.'
            )
        except requests.exceptions.Timeout:
            _logger.error('SunnyPay API request timed out: %s', url)
            raise UserError('SunnyPay API request timed out. Please try again.')
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 'Unknown'
            body = ''
            try:
                body = e.response.json().get('error', e.response.text[:200])
            except Exception:
                body = str(e)
            _logger.error('SunnyPay API error %s: %s', status, body)
            raise UserError(f'SunnyPay API error ({status}): {body}')
        except Exception as e:
            _logger.error('Unexpected SunnyPay API error: %s', str(e))
            raise UserError(f'SunnyPay API error: {str(e)}')

    # ─── Connection Test ──────────────────────────────────────────────

    def test_connection(self):
        """Test the connection to SunnyPay API (hits /health endpoint)."""
        return self._request('GET', '/health')

    # ─── Transactions ─────────────────────────────────────────────────

    def get_transactions(self, page=1, limit=100):
        """Fetch transactions from SunnyPay."""
        result = self._request('GET', '/payments', params={
            'page': page,
            'limit': limit,
        })
        # Handle different response formats
        if isinstance(result, list):
            return result
        return result.get('data', {}).get('payments', result.get('data', []))

    def get_transaction(self, transaction_id):
        """Fetch a single transaction by ID."""
        return self._request('GET', f'/payments/{transaction_id}')

    def create_refund(self, transaction_id, amount):
        """Initiate a refund for a transaction."""
        return self._request('POST', f'/payments/{transaction_id}/refund', data={
            'amount': amount,
        })

    # ─── Merchants ────────────────────────────────────────────────────

    def get_merchants(self, page=1, limit=100):
        """Fetch merchants from SunnyPay."""
        result = self._request('GET', '/merchants', params={
            'page': page,
            'limit': limit,
        })
        if isinstance(result, list):
            return result
        return result.get('data', {}).get('merchants', result.get('data', []))

    def get_merchant(self, merchant_id):
        """Fetch a single merchant by ID."""
        return self._request('GET', f'/merchants/{merchant_id}')

    # ─── Invoices ─────────────────────────────────────────────────────

    def get_invoices(self, page=1, limit=100):
        """Fetch invoices from SunnyPay."""
        result = self._request('GET', '/invoices', params={
            'page': page,
            'limit': limit,
        })
        if isinstance(result, list):
            return result
        return result.get('data', {}).get('invoices', result.get('data', []))

    def get_invoice(self, invoice_id):
        """Fetch a single invoice by ID."""
        return self._request('GET', f'/invoices/{invoice_id}')

    # ─── Customers ────────────────────────────────────────────────────

    def get_customers(self, page=1, limit=100):
        """Fetch customers/users from SunnyPay auth service."""
        # Try the main users endpoint first, then fall back
        try:
            result = self._request('GET', '/users', params={
                'page': page,
                'limit': limit,
            })
        except UserError:
            # Fall back to customers endpoint
            result = self._request('GET', '/customers', params={
                'page': page,
                'limit': limit,
            })

        if isinstance(result, list):
            return result
        return result.get('data', {}).get('users',
               result.get('data', {}).get('customers',
               result.get('data', [])))

    def get_customer(self, customer_id):
        """Fetch a single customer by ID."""
        return self._request('GET', f'/users/{customer_id}')

    # ─── Analytics ────────────────────────────────────────────────────

    def get_dashboard_analytics(self):
        """Fetch dashboard analytics data."""
        return self._request('GET', '/analytics/dashboard')

    # ─── Reports ──────────────────────────────────────────────────────

    def get_reports(self, report_type='transactions', start_date=None, end_date=None):
        """Fetch reports from SunnyPay."""
        params = {'type': report_type}
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date
        return self._request('GET', '/reports', params=params)
