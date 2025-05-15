# filepath: /home/b450-plus/DMI_FYP_dj_primary-backend/DMI_FYP_dj_primary-backend/DMI_backend/api/views/donations_views.py

import stripe
import json
import os
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from app.models import Donation, UserData, ModeratorAction
from app.controllers.ResponseCodesController import get_response_code
from api.serializers import DonationSerializer, DonationCreateSerializer

# Initialize Stripe with the secret key from settings
stripe.api_key = settings.STRIPE_SECRET_KEY
webhook_secret = settings.STRIPE_WEBHOOK_SECRET


@api_view(["POST"])
@permission_classes([AllowAny])
def create_donation_checkout(request):
    """
    Create a Stripe checkout session for a donation
    """
    try:
        serializer = DonationCreateSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        amount = float(serializer.validated_data["amount"])
        currency = serializer.validated_data.get("currency", "USD")
        is_anonymous = serializer.validated_data.get("is_anonymous", False)
        message = serializer.validated_data.get("message", "")
        donor_name = serializer.validated_data.get("donor_name", "")
        donor_email = serializer.validated_data.get("donor_email", "")

        # Extract user if authenticated
        user_data = None
        if request.user.is_authenticated:
            user_data = UserData.objects.get(user=request.user)
            if not donor_email:
                donor_email = request.user.email
            if not donor_name and not is_anonymous:
                donor_name = request.user.username

        # Create metadata for the session
        metadata = {
            "is_anonymous": "true" if is_anonymous else "false",
            "message": message,
            "donor_name": donor_name,
            "donor_email": donor_email,
        }

        if user_data:
            metadata["user_id"] = str(user_data.id)

        # Convert amount to cents for Stripe
        amount_in_cents = int(amount * 100)

        # Create a Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "product_data": {
                            "name": "Donation to DMI Project",
                            "description": "Thank you for supporting our project!",
                        },
                        "unit_amount": amount_in_cents,
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=f"{settings.FRONTEND_HOST_URL}/donation/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_HOST_URL}/donation/cancel",
            metadata=metadata,
        )

        # Return the checkout URL and session ID
        return Response({"success": True, "checkout_url": checkout_session.url, "session_id": checkout_session.id})

    except stripe.error.StripeError as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle webhook events from Stripe
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        handle_completed_checkout(session)

    # Return a 200 response to acknowledge receipt of the event
    return HttpResponse(status=200)


def handle_completed_checkout(session):
    """
    Process a completed checkout session
    """
    # Extract metadata
    metadata = session.get("metadata", {})
    is_anonymous = metadata.get("is_anonymous", "false") == "true"
    message = metadata.get("message", "")
    donor_name = metadata.get("donor_name", "")
    donor_email = metadata.get("donor_email", "")
    user_id = metadata.get("user_id")

    # Find user if available
    user_data = None
    if user_id:
        try:
            user_data = UserData.objects.get(id=user_id)
        except UserData.DoesNotExist:
            pass

    # Create the donation record
    Donation.objects.create(
        user=user_data,
        amount=session["amount_total"] / 100,  # Convert cents to dollars
        currency=session["currency"].upper(),
        stripe_payment_id=session["payment_intent"],
        stripe_checkout_id=session["id"],
        status=Donation.DonationStatus.COMPLETED,
        donor_name=donor_name,
        donor_email=donor_email,
        is_anonymous=is_anonymous,
        message=message,
    )


@api_view(["GET"])
def verify_donation(request, session_id):
    """
    Verify a donation session status
    """
    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Check if there's already a donation with this checkout ID
        try:
            donation = Donation.objects.get(stripe_checkout_id=session_id)
            serializer = DonationSerializer(donation)
            return Response({"success": True, "verified": True, "donation": serializer.data, "payment_status": session["payment_status"]})
        except Donation.DoesNotExist:
            # Process the session if it's completed but not recorded yet
            if session["payment_status"] == "paid":
                handle_completed_checkout(session)
                donation = Donation.objects.get(stripe_checkout_id=session_id)
                serializer = DonationSerializer(donation)
                return Response({"success": True, "verified": True, "donation": serializer.data, "payment_status": session["payment_status"]})
            else:
                return Response({"success": True, "verified": False, "payment_status": session["payment_status"]})

    except stripe.error.StripeError as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_donations(request):
    """
    Get a list of donations (with filtering options)
    Admin/moderators can see all, users see their own
    """
    user = request.user
    user_data = UserData.objects.get(user=user)

    # Check for query parameters
    is_admin = user.is_staff or user.is_superuser or user.groups.filter(name="Moderators").exists()
    if not is_admin:
        # Regular users can only see their own non-anonymous donations
        donations = Donation.objects.filter(user=user_data, is_anonymous=False)
    else:
        # Admins can filter and see all
        status_filter = request.query_params.get("status")
        if status_filter:
            donations = Donation.objects.filter(status=status_filter)
        else:
            donations = Donation.objects.all()

    # Apply pagination if needed
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 20))
    start = (page - 1) * page_size
    end = start + page_size

    # Serialize and return
    serializer = DonationSerializer(donations[start:end], many=True)
    return Response(
        {
            "success": True,
            "count": donations.count(),
            "data": serializer.data,
            "page": page,
            "page_size": page_size,
            "total_pages": (donations.count() + page_size - 1) // page_size,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_donation_detail(request, donation_id):
    """
    Get details for a specific donation
    """
    user = request.user
    user_data = UserData.objects.get(user=user)
    is_admin = user.is_staff or user.is_superuser or user.groups.filter(name="Moderators").exists()

    try:
        donation = Donation.objects.get(id=donation_id)

        # Check if the user is authorized to view this donation
        if not is_admin and (donation.user != user_data or donation.is_anonymous):
            return Response({"success": False, "error": "You do not have permission to view this donation."}, status=status.HTTP_403_FORBIDDEN)

        serializer = DonationSerializer(donation)
        return Response({"success": True, "data": serializer.data})
    except Donation.DoesNotExist:
        return Response({"success": False, "error": "Donation not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def refund_donation(request, donation_id):
    """
    Refund a donation (admin only)
    """
    user = request.user
    is_admin = user.is_staff or user.is_superuser or user.groups.filter(name="Moderators").exists()

    if not is_admin:
        return Response({"success": False, "error": "You do not have permission to refund donations."}, status=status.HTTP_403_FORBIDDEN)

    try:
        donation = Donation.objects.get(id=donation_id)

        # Don't process if already refunded
        if donation.status == Donation.DonationStatus.REFUNDED:
            return Response({"success": False, "error": "This donation has already been refunded."}, status=status.HTTP_400_BAD_REQUEST)

        # Process refund through Stripe
        try:
            refund = stripe.Refund.create(payment_intent=donation.stripe_payment_id)

            # Update the donation status
            donation.status = Donation.DonationStatus.REFUNDED
            donation.save()

            # Log the action
            ModeratorAction.objects.create(
                moderator=user,
                action_type="other",
                content_type="donation",
                content_identifier=f"Donation #{donation.id}",
                notes=f"Refunded donation of {donation.amount} {donation.currency}",
            )

            serializer = DonationSerializer(donation)
            return Response({"success": True, "data": serializer.data, "refund_id": refund.id})

        except stripe.error.StripeError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    except Donation.DoesNotExist:
        return Response({"success": False, "error": "Donation not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def get_donation_stats(request):
    """
    Get donation statistics (public endpoint)
    """
    try:
        # Get total number of donations
        total_count = Donation.objects.filter(status=Donation.DonationStatus.COMPLETED).count()

        # Get total amount donated
        from django.db.models import Sum

        total_amount = Donation.objects.filter(status=Donation.DonationStatus.COMPLETED).aggregate(total=Sum("amount"))["total"] or 0

        # Recent donations (non-anonymous only) for display purposes
        recent_donations = Donation.objects.filter(status=Donation.DonationStatus.COMPLETED, is_anonymous=False).order_by("-created_at")[:5]

        recent_serializer = DonationSerializer(recent_donations, many=True)

        return Response({"success": True, "stats": {"total_count": total_count, "total_amount": float(total_amount), "recent_donations": recent_serializer.data}})

    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
