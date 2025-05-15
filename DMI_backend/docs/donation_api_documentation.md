# Donation API Documentation

## Overview

The Donation API allows users to make financial contributions to the DMI Project through a simplified demo payment system. This implementation uses a dummy payment process without actual payment processing for demonstration purposes only.

## Endpoints

### 1. Create Donation Checkout

Creates a dummy checkout session for processing a donation (no actual payment is processed).

**URL**: `/api/donations/checkout/`  
**Method**: `POST`  
**Auth Required**: Yes (Authentication required)

**Request Body**:

```json
{
  "amount": 25.0,
  "currency": "USD",
  "is_anonymous": false,
  "donor_name": "John Doe",
  "donor_email": "john@example.com",
  "message": "Keep up the great work!",
  "donation_type": "one_time",
  "project_allocation": "Research Fund",
  "is_gift": false,
  "gift_recipient_name": "",
  "gift_recipient_email": "",
  "gift_message": "",
  "donor_address": "123 Main St, City, Country",
  "donor_phone": "+1234567890",
  "donor_country": "United States",
  "payment_method_type": "credit_card",
  "card_number": "4111111111111111",
  "card_expiry_month": "12",
  "card_expiry_year": "2025",
  "card_cvc": "123",
  "billing_city": "San Francisco",
  "billing_postal_code": "94105"
}
```

**Fields**:

- `amount`: Required. Donation amount (minimum 1.00)
- `currency`: Optional. Default is "USD"
- `is_anonymous`: Optional. Default is false
- `donor_name`: Optional. Will use authenticated user's username if not provided and not anonymous
- `donor_email`: Optional. Will use authenticated user's email if not provided
- `message`: Optional. A message from the donor
- `donation_type`: Optional. Options: "one_time", "monthly", "annually". Default is "one_time"
- `project_allocation`: Optional. Specific project the donation is allocated to
- `is_gift`: Optional. Whether this donation is a gift for someone. Default is false
- `gift_recipient_name`: Required if is_gift=true. Name of the gift recipient
- `gift_recipient_email`: Required if is_gift=true. Email of the gift recipient
- `gift_message`: Optional. Message for the gift recipient
- `donor_address`: Optional. Physical address of the donor
- `donor_phone`: Optional. Phone number of the donor
- `donor_country`: Optional. Country of the donor
- `payment_method_type`: Optional. Default is "credit_card"
- `card_number`: Optional. Full card number (only last 4 digits stored)
- `card_expiry_month`: Optional. Card expiry month
- `card_expiry_year`: Optional. Card expiry year
- `card_cvc`: Optional. Card security code (not stored)
- `card_type`: Optional. Type of card (e.g., "Visa")
- `billing_city`: Optional. City for billing address
- `billing_postal_code`: Optional. Postal/ZIP code for billing address

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
**Auth Required**: Yes

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
    "donor_username": "johndoe",
    "donation_type": "one_time",
    "project_allocation": "Research Fund",
    "is_gift": false,
    "gift_recipient_name": null,
    "gift_recipient_email": null,
    "gift_message": null,
    "donor_address": "123 Main St, City, Country",
    "donor_phone": "+1234567890",
    "donor_country": "United States",
    "payment_method_type": "credit_card",
    "card_number_last4": "1111",
    "card_expiry_month": "12",
    "card_expiry_year": "2025",
    "card_type": "Visa",
    "billing_city": "San Francisco",
    "billing_postal_code": "94105"
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
      "donor_username": "johndoe",
      "donation_type": "one_time",
      "project_allocation": "Research Fund",
      "is_gift": false,
      "gift_recipient_name": null,
      "gift_recipient_email": null,
      "gift_message": null,
      "donor_address": "123 Main St, City, Country",
      "donor_phone": "+1234567890",
      "donor_country": "United States",
      "payment_method_type": "credit_card",
      "card_number_last4": "1111",
      "card_expiry_month": "12",
      "card_expiry_year": "2025",
      "card_type": "Visa",
      "billing_city": "San Francisco",
      "billing_postal_code": "94105",
      "notes": null,
      "refund_id": null,
      "refunded_at": null,
      "refund_reason": null,
      "refunded_amount": null
    }
    // More donations...
  ],
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### 4. Get Donation Detail

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
    "donor_username": "johndoe",
    "donation_type": "one_time",
    "project_allocation": "Research Fund",
    "is_gift": false,
    "gift_recipient_name": null,
    "gift_recipient_email": null,
    "gift_message": null,
    "donor_address": "123 Main St, City, Country",
    "donor_phone": "+1234567890",
    "donor_country": "United States",
    "payment_method_type": "credit_card",
    "card_number_last4": "1111",
    "card_expiry_month": "12",
    "card_expiry_year": "2025",
    "card_type": "Visa",
    "billing_city": "San Francisco",
    "billing_postal_code": "94105",
    "notes": null,
    "refund_id": null,
    "refunded_at": null,
    "refund_reason": null,
    "refunded_amount": null
  }
}
```

### 5. Refund Donation

Simulates a refund for a donation (admin only) - demo version.

**URL**: `/api/donations/{donation_id}/refund/`  
**Method**: `DELETE`  
**Auth Required**: Yes  
**Permissions**: Admin/moderator only

**Request Body**:

```json
{
  "refund_reason": "Customer requested refund" // Optional
}
```

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
    "donor_username": "johndoe",
    "donation_type": "one_time",
    "project_allocation": "Research Fund",
    "refund_id": "demo_refund_abc123...",
    "refunded_at": "2025-05-15T12:45:56Z",
    "refund_reason": "Customer requested refund",
    "refunded_amount": "25.00"
  },
  "refund_id": "demo_refund_abc123...",
  "demo_message": "DEMO MODE: Refund processed without actual payment processing."
}
```

### 6. Get Donation Statistics

Get donation statistics (public endpoint).

**URL**: `/api/donations/stats/`  
**Method**: `GET`  
**Auth Required**: Yes

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
        "donor_username": "johndoe",
        "donation_type": "one_time",
        "project_allocation": "Research Fund",
        "is_gift": false,
        "gift_recipient_name": null,
        "gift_recipient_email": null,
        "gift_message": null,
        "donor_address": "123 Main St, City, Country",
        "donor_phone": "+1234567890",
        "donor_country": "United States",
        "payment_method_type": "credit_card",
        "card_number_last4": "1111",
        "card_expiry_month": "12",
        "card_expiry_year": "2025",
        "card_type": "Visa",
        "billing_city": "San Francisco",
        "billing_postal_code": "94105",
        "notes": null,
        "refund_id": null,
        "refunded_at": null,
        "refund_reason": null,
        "refunded_amount": null
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
