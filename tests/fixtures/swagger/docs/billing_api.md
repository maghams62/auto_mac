# Billing API Documentation

> **Note**: This documentation is IN SYNC with the v1.3.0 spec.

## Overview

The Billing API provides endpoints for managing invoices and subscriptions.

## Authentication

All API requests require a valid API key in the `Authorization` header:

```
Authorization: Bearer sk_live_xxxxx
```

## Endpoints

### Create an Invoice

`POST /v1/billing/invoice`

Creates a new invoice for a customer.

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `customer_id` | string | Yes | Customer identifier |
| `subscription_id` | string | No | Optional subscription to associate |
| `line_items` | array | Yes | Array of line items (at least one required) |
| `due_date` | string | No | Invoice due date (ISO 8601 date) |
| `memo` | string | No | Optional memo (max 1000 characters) |

#### Line Item Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | Yes | Item description (max 500 characters) |
| `amount` | integer | Yes | Amount in cents |
| `quantity` | integer | No | Quantity (default: 1) |

#### Example Request

```json
{
  "customer_id": "cus_1234567890",
  "line_items": [
    {
      "description": "Pro Plan - Monthly",
      "amount": 2999,
      "quantity": 1
    }
  ],
  "due_date": "2024-02-15"
}
```

#### Response

```json
{
  "id": "inv_1234567890",
  "customer_id": "cus_1234567890",
  "status": "open",
  "total": 2999,
  "line_items": [...],
  "due_date": "2024-02-15",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### List Invoices

`GET /v1/billing/invoice`

Retrieves a paginated list of invoices.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `customer_id` | string | No | Filter by customer |
| `status` | string | No | Filter by status (draft, open, paid, void) |
| `limit` | integer | No | Results per page (default: 20, max: 100) |
| `offset` | integer | No | Pagination offset (default: 0) |

### Create a Subscription

`POST /v1/billing/subscribe`

Creates a new subscription for a customer.

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `customer_id` | string | Yes | Customer identifier |
| `plan_id` | string | Yes | Subscription plan identifier |
| `payment_method_id` | string | Yes | Payment method for recurring charges |
| `trial_days` | integer | No | Number of trial days (0-365, default: 0) |
| `promo_code` | string | No | Optional promotional code |

#### Example Request

```json
{
  "customer_id": "cus_1234567890",
  "plan_id": "plan_pro_monthly",
  "payment_method_id": "pm_1234567890",
  "trial_days": 14
}
```

#### Response

```json
{
  "id": "sub_1234567890",
  "customer_id": "cus_1234567890",
  "plan_id": "plan_pro_monthly",
  "status": "trialing",
  "trial_end": "2024-01-29T10:30:00Z",
  "current_period_start": "2024-01-15T10:30:00Z",
  "current_period_end": "2024-02-15T10:30:00Z",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Subscription Statuses

| Status | Description |
|--------|-------------|
| `trialing` | Subscription is in trial period |
| `active` | Subscription is active and billing |
| `past_due` | Payment failed, grace period active |
| `canceled` | Subscription was canceled |
| `unpaid` | Multiple payment failures |

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid request parameters |
| 402 | Payment method validation failed |
| 404 | Resource not found |

---

*Last updated: 2024-01-20 (v1.3.0)*

