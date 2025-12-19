# Payments API Documentation

> **Note**: This documentation is INTENTIONALLY OUT OF DATE to demonstrate drift detection.
> It references v2.0 parameters while the spec is at v2.1.

## Overview

The Payments API allows you to process charges and refunds programmatically.

## Authentication

All API requests require a valid API key in the `Authorization` header:

```
Authorization: Bearer sk_live_xxxxx
```

## Endpoints

### Create a Charge

`POST /v1/payments/charge`

Creates a new charge against a customer's payment method.

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `amount` | integer | Yes | Amount in **dollars** (NOTE: This is WRONG - v2.1 uses cents) |
| `currency` | string | Yes | ISO 4217 currency code (e.g., "USD") |
| `payment_method_id` | string | Yes | ID of the stored payment method |
| `description` | string | No | Optional charge description |

> **DRIFT**: Missing `metadata` field (added in v2.1)
> **DRIFT**: Missing `capture` field (added in v2.1)
> **DRIFT**: `amount` description is wrong (should be "cents" not "dollars")

#### Example Request

```json
{
  "amount": 25,
  "currency": "USD",
  "payment_method_id": "pm_1234567890",
  "description": "Order #12345"
}
```

#### Response

```json
{
  "id": "ch_1234567890",
  "amount": 2500,
  "currency": "USD",
  "status": "succeeded",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Create a Refund

`POST /v1/payments/refund`

Refunds a previously successful charge.

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `charge_id` | string | Yes | ID of the charge to refund |
| `amount` | integer | No | Amount to refund in cents (defaults to full refund) |
| `reason` | string | No | Reason for the refund |

#### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Idempotency-Key` | No | Unique key for idempotent requests |

> **DRIFT**: `X-Idempotency-Key` should be marked as REQUIRED per v2.1 spec

#### Example Request

```json
{
  "charge_id": "ch_1234567890",
  "amount": 1000,
  "reason": "requested_by_customer"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid request parameters |
| 402 | Payment failed |
| 404 | Resource not found |
| 429 | Rate limit exceeded |

## Rate Limits

- 100 requests per minute per API key
- Burst limit of 20 requests per second

---

*Last updated: 2024-01-01 (v2.0)*

