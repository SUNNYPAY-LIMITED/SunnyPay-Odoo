
<div align="center">

| ![SunnyPay Logo](assets/sunny-logo.svg) | ![Odoo Logo](assets/odoo-logo.png) |
|:---:|:---:|
| **SunnyPay** | **Odoo 17** |

# SunnyPay Odoo Connector

**Bringing Seamless Payments to Your Odoo ERP**

[![Odoo Version](https://img.shields.io/badge/Odoo-17.0-purple.svg)](https://www.odoo.com)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

</div>

## Overview

The **SunnyPay Connector** integrates the SunnyPay payment gateway directly into Odoo 17, allowing businesses to accept payments via **Mobile Money (M-Pesa, MTN MoMo, Airtel), Cards, Crypto, and Bank Transfers** without leaving their ERP.

This module provides:
- **Bi-Directional Sync**: Automatically pull transactions, customers, and invoices.
- **Real-Time Updates**: Webhooks for instant payment status changes.
- **Financial Dashboard**: Track revenue and transaction volume directly in Odoo.
- **Accounting Integration**: Create native Odoo invoices from SunnyPay records.

## Features

- **Transactions**: View and manage all payments with status tracking.
- **Merchants**: Sync business accounts and link them to Odoo partners.
- **Invoices**: Import invoices and generate accounting entries.
- **Customers**: Maintain a unified customer database with SunnyTags.
- **Configuration**: Easy setup with API Key/Secret management.

## Installation

1.  Clone this repository into your Odoo addons path:
    ```bash
    git clone https://github.com/SUNNYPAY-LIMITED/SunnyPay-Odoo.git
    ```
2.  Restart your Odoo server.
3.  Go to **Apps**, click **"Update Apps List"**, and search for **"SunnyPay"**.
4.  Click **Activate**.

## Configuration

1.  Navigate to **Settings > SunnyPay**.
2.  Enter your **API URL** (e.g., `https://api.sunnypay.com`).
3.  Enter your **API Key** and **Secret**.
    - *Get these from your SunnyPay Dashboard > Developers > API Keys.*
4.  Click **Test Connection**.
5.  Click **Sync All Data** to pull historical records.

## Requirements

- Odoo 17.0
- Python `requests` library

## License

LGPL-3
