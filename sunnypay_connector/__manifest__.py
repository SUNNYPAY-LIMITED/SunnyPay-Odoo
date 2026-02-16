# -*- coding: utf-8 -*-
{
    'name': 'SunnyPay Connector',
    'version': '17.0.1.0.1',
    'category': 'Accounting/Payment',
    'summary': 'Integrate SunnyPay payment gateway with Odoo',
    'description': """
        SunnyPay Connector for Odoo
        ===========================
        Connect your Odoo instance to SunnyPay's payment infrastructure.

        Features:
        - Sync transactions, merchants, invoices, and customers
        - Real-time webhook updates for payment status changes
        - Dashboard with payment analytics
        - Automatic data synchronization via cron jobs
        - Support for Mobile Money, Cards, Crypto, and Bank Transfers
    """,
    'author': 'SunnyPay Limited',
    'website': 'https://sunnypay.co.ke',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'contacts',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/menu_views.xml',
        'views/config_views.xml',
        'views/transaction_views.xml',
        'views/merchant_views.xml',
        'views/invoice_views.xml',
        'views/customer_views.xml',
        'views/dashboard_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
