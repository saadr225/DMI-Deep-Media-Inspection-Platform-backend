# Donation API Documentation

## Overview

The Donation API allows users to make financial contributions to the DMI Project through a simplified demo payment system. This implementation uses a dummy payment process without actual payment processing for demonstration purposes only.

## Endpoints

### 1. Create Donation Checkout

Creates a dummy checkout session for processing a donation (no actual payment is processed).

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
  "checkout_url": "http://localhost:3000/donation/demo-payment?session_id=demo_123abc...",
  "session_id": "demo_123abc...",
  "demo_message": "DEMO MODE: This is a demo payment flow. No real payment will be processed."
}
```

### 2. Verify Donation

Verifies the status of a donation and marks it as completed (demo version).

**URL**: `/api/donations/verify/{session_id}/`  
**Method**: `GET`  
**Auth Required**: No

**Success Response**:

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
  "payment_status": "paid",
  "demo_message": "DEMO MODE: Payment automatically marked as successful."
}
```

**Error Response (Not Found)**:

```json
{
  "success": false,
  "verified": false,
  "error": "Donation not found"
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

Simulates a refund for a donation (demo version, no actual refund is processed).

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
  "refund_id": "demo_refund_abc123...",
  "demo_message": "DEMO MODE: Refund processed without actual payment processing."
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

## Payment Verification

This implementation uses a simplified demo flow:

1. After clicking the checkout link, users are redirected to a demo payment page
2. Upon completing the demo payment, users are redirected back to the success page
3. The success page calls the verification endpoint (`/api/donations/verify/{session_id}/`)
4. In demo mode, the verification endpoint automatically marks the payment as successful

This is a demonstration-only implementation with no actual payment processing.
