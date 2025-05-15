import json
import os
import uuid
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

# No Stripe integration for demo version


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # Changed from AllowAny to IsAuthenticated
def create_donation_checkout(request):
    """
    Create a dummy checkout session for a donation (demo version without Stripe)
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

        # Get new fields
        donation_type = serializer.validated_data.get("donation_type", Donation.DonationType.ONE_TIME)
        project_allocation = serializer.validated_data.get("project_allocation", "")
        is_gift = serializer.validated_data.get("is_gift", False)
        gift_recipient_name = serializer.validated_data.get("gift_recipient_name", "")
        gift_recipient_email = serializer.validated_data.get("gift_recipient_email", "")
        gift_message = serializer.validated_data.get("gift_message", "")
        donor_address = serializer.validated_data.get("donor_address", "")
        donor_phone = serializer.validated_data.get("donor_phone", "")
        donor_country = serializer.validated_data.get("donor_country", "")
        payment_method_type = serializer.validated_data.get("payment_method_type", "credit_card")

        # Get credit card fields
        card_number_last4 = serializer.validated_data.get("card_number_last4", "")
        card_expiry_month = serializer.validated_data.get("card_expiry_month", "")
        card_expiry_year = serializer.validated_data.get("card_expiry_year", "")
        card_type = serializer.validated_data.get("card_type", "")
        billing_city = serializer.validated_data.get("billing_city", "")
        billing_postal_code = serializer.validated_data.get("billing_postal_code", "")

        # Extract user if authenticated
        user_data = UserData.objects.get(user=request.user)
        if not donor_email:
            donor_email = request.user.email
        if not donor_name and not is_anonymous:
            donor_name = request.user.username

        # Generate a unique session ID for the demo checkout
        session_id = f"demo_{uuid.uuid4().hex}"

        # Create pending donation in database
        donation = Donation.objects.create(
            user=user_data,
            amount=amount,
            currency=currency,
            status=Donation.DonationStatus.PENDING,
            donor_name=donor_name,
            donor_email=donor_email,
            is_anonymous=is_anonymous,
            message=message,
            session_id=session_id,  # Using the session_id field instead of stripe_checkout_id
            donation_type=donation_type,
            project_allocation=project_allocation,
            is_gift=is_gift,
            gift_recipient_name=gift_recipient_name,
            gift_recipient_email=gift_recipient_email,
            gift_message=gift_message,
            donor_address=donor_address,
            donor_phone=donor_phone,
            donor_country=donor_country,
            payment_method_type=payment_method_type,
            card_number_last4=card_number_last4,
            card_expiry_month=card_expiry_month,
            card_expiry_year=card_expiry_year,
            card_type=card_type,
            billing_city=billing_city,
            billing_postal_code=billing_postal_code,
        )

        # For demo, create a simulated checkout URL
        checkout_url = f"{settings.FRONTEND_HOST_URL}/donation/demo-payment?session_id={session_id}"

        # Return the checkout URL and session ID
        return Response(
            {
                "success": True,
                "checkout_url": checkout_url,
                "session_id": session_id,
                "demo_message": "DEMO MODE: This is a demo payment flow. No real payment will be processed.",
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Added IsAuthenticated requirement
def verify_donation(request, session_id):
    """
    Verify a donation session status (demo version)
    """
    try:
        # Check if there's already a donation with this session ID
        try:
            donation = Donation.objects.get(session_id=session_id)

            # In demo mode, just mark it as complete for testing
            if donation.status == Donation.DonationStatus.PENDING:
                donation.status = Donation.DonationStatus.COMPLETED
                # Generate a fake payment ID for reference
                donation.payment_id = f"demo_payment_{uuid.uuid4().hex}"
                donation.save()

            serializer = DonationSerializer(donation)
            return Response(
                {
                    "success": True,
                    "verified": True,
                    "donation": serializer.data,
                    "payment_status": "paid",
                    "demo_message": "DEMO MODE: Payment automatically marked as successful.",
                }
            )
        except Donation.DoesNotExist:
            return Response({"success": False, "verified": False, "error": "Donation not found"}, status=status.HTTP_404_NOT_FOUND)

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
    Refund a donation (admin only) - demo version
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

        # Only completed donations can be refunded
        if donation.status != Donation.DonationStatus.COMPLETED:
            return Response({"success": False, "error": f"Cannot refund donation with status {donation.status}"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the refund reason if provided
        refund_reason = request.data.get("refund_reason", "Administrative refund")

        # Update the donation status (no actual payment processing in demo)
        donation.status = Donation.DonationStatus.REFUNDED
        donation.refund_id = f"demo_refund_{uuid.uuid4().hex}"
        donation.refunded_at = datetime.now()
        donation.refund_reason = refund_reason
        donation.refunded_amount = donation.amount
        donation.save()

        # Log the action
        ModeratorAction.objects.create(
            moderator=user,
            action_type="other",
            content_type="donation",
            content_identifier=f"Donation #{donation.id}",
            notes=f"Refunded donation of {donation.amount} {donation.currency}. Reason: {refund_reason}",
        )

        serializer = DonationSerializer(donation)
        return Response(
            {
                "success": True,
                "data": serializer.data,
                "refund_id": donation.refund_id,
                "demo_message": "DEMO MODE: Refund processed without actual payment processing.",
            }
        )

    except Donation.DoesNotExist:
        return Response({"success": False, "error": "Donation not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Added IsAuthenticated requirement
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
