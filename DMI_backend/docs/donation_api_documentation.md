# Donation API Documentation

## Overview

The Donation API allows users to make financial contributions to the DMI Project through Stripe integration. It provides endpoints for creating donation checkouts, verifying payments, and viewing donation statistics.

## Endpoints

### 1. Create Donation Checkout

Creates a Stripe checkout session for processing a donation payment.

**URL**: `/api/donations/checkout/`  
**Method**: `POST`  
**Auth Required**: No (optional authentication for logged-in users)

**Request Body**:

```json
{
  "amount": 25.0,
  "currency": "USD",
  "is_anonymous": false,
  "donor_name": "John Doe",
  "donor_email": "john@example.com",
  "message": "Keep up the great work!"
}
```

**Fields**:

- `amount`: Required. Donation amount (minimum 1.00)
- `currency`: Optional. Default is "USD"
- `is_anonymous`: Optional. Default is false
- `donor_name`: Optional. Required if anonymous and not authenticated
- `donor_email`: Optional. Required if anonymous and not authenticated
- `message`: Optional. A message from the donor

**Success Response**:

```json
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_test_..."
}
```

### 2. Verify Donation

Verifies the status of a donation after payment processing.

**URL**: `/api/donations/verify/{session_id}/`  
**Method**: `GET`  
**Auth Required**: No

**Success Response (Paid)**:

```json
{
  "success": true,
  "verified": true,
  "donation": {
    "id": 12,
    "amount": "25.00",
    "currency": "USD",
    "status": "completed",
    "created_at": "2025-05-15T12:34:56Z",
    "updated_at": "2025-05-15T12:34:56Z",
    "donor_name": "John Doe",
    "donor_email": "john@example.com",
    "is_anonymous": false,
    "message": "Keep up the great work!",
    "donor_username": "johndoe"
  },
  "payment_status": "paid"
}
```

**Success Response (Not Paid)**:

```json
{
  "success": true,
  "verified": false,
  "payment_status": "unpaid"
}
```

### 3. Get Donations List

Retrieves a paginated list of donations.

**URL**: `/api/donations/`  
**Method**: `GET`  
**Auth Required**: Yes  
**Permissions**: Regular users can only see their own non-anonymous donations. Admins/moderators can see all donations.

**Query Parameters**:

- `page`: Page number (default: 1)
- `page_size`: Number of items per page (default: 20)
- `status`: Filter by status (admin/moderator only)

**Success Response**:

```json
{
  "success": true,
  "count": 42,
  "data": [
    {
      "id": 12,
      "amount": "25.00",
      "currency": "USD",
      "status": "completed",
      "created_at": "2025-05-15T12:34:56Z",
      "updated_at": "2025-05-15T12:34:56Z",
      "donor_name": "John Doe",
      "donor_email": "john@example.com",
      "is_anonymous": false,
      "message": "Keep up the great work!",
      "donor_username": "johndoe"
    }
    // More donations...
  ],
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### 4. Get Donation Details

Retrieves details for a specific donation.

**URL**: `/api/donations/{donation_id}/`  
**Method**: `GET`  
**Auth Required**: Yes  
**Permissions**: Regular users can only see their own non-anonymous donations. Admins/moderators can see all donations.

**Success Response**:

```json
{
  "success": true,
  "data": {
    "id": 12,
    "amount": "25.00",
    "currency": "USD",
    "status": "completed",
    "created_at": "2025-05-15T12:34:56Z",
    "updated_at": "2025-05-15T12:34:56Z",
    "donor_name": "John Doe",
    "donor_email": "john@example.com",
    "is_anonymous": false,
    "message": "Keep up the great work!",
    "donor_username": "johndoe"
  }
}
```

### 5. Refund Donation

Issues a refund for a specific donation.

**URL**: `/api/donations/{donation_id}/refund/`  
**Method**: `DELETE`  
**Auth Required**: Yes  
**Permissions**: Admin/moderator only

**Success Response**:

```json
{
  "success": true,
  "data": {
    "id": 12,
    "amount": "25.00",
    "currency": "USD",
    "status": "refunded",
    "created_at": "2025-05-15T12:34:56Z",
    "updated_at": "2025-05-15T12:45:56Z",
    "donor_name": "John Doe",
    "donor_email": "john@example.com",
    "is_anonymous": false,
    "message": "Keep up the great work!",
    "donor_username": "johndoe"
  },
  "refund_id": "re_test_..."
}
```

### 6. Get Donation Statistics

Retrieves donation statistics.

**URL**: `/api/donations/stats/`  
**Method**: `GET`  
**Auth Required**: No

**Success Response**:

```json
{
  "success": true,
  "stats": {
    "total_count": 42,
    "total_amount": 1275.5,
    "recent_donations": [
      {
        "id": 12,
        "amount": "25.00",
        "currency": "USD",
        "status": "completed",
        "created_at": "2025-05-15T12:34:56Z",
        "updated_at": "2025-05-15T12:34:56Z",
        "donor_name": "John Doe",
        "donor_email": "john@example.com",
        "is_anonymous": false,
        "message": "Keep up the great work!",
        "donor_username": "johndoe"
      }
      // More donations (up to 5)...
    ]
  }
}
```

## Webhook Integration

Stripe webhooks are used to asynchronously update donation statuses. Configure your Stripe webhook settings to point to:

**URL**: `/api/donations/webhook/`  
**Events to listen for**: `checkout.session.completed`

Ensure the webhook secret from your Stripe dashboard matches the `STRIPE_WEBHOOK_SECRET` in your environment settings.
