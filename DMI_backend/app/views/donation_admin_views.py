import csv
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta

from app.models import Donation, ModeratorAction
from app.views.custom_admin_views import custom_admin_required
import stripe
from django.conf import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@custom_admin_required
def admin_donations_list(request):
    """Admin view for donations list"""

    # Get filter params
    status_filter = request.GET.get("status", "")
    date_filter = request.GET.get("date", "")
    search_query = request.GET.get("search", "")

    # Base queryset
    donations = Donation.objects.all()

    # Apply filters
    if status_filter:
        donations = donations.filter(status=status_filter)

    if date_filter:
        if date_filter == "today":
            today = timezone.now().date()
            donations = donations.filter(created_at__date=today)
        elif date_filter == "week":
            week_ago = timezone.now() - timedelta(days=7)
            donations = donations.filter(created_at__gte=week_ago)
        elif date_filter == "month":
            month_ago = timezone.now() - timedelta(days=30)
            donations = donations.filter(created_at__gte=month_ago)

    # Search by donor name, email, or message
    if search_query:
        donations = (
            donations.filter(donor_name__icontains=search_query)
            | donations.filter(donor_email__icontains=search_query)
            | donations.filter(message__icontains=search_query)
        )

    # Export as CSV if requested
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="donations.csv"'

        writer = csv.writer(response)
        writer.writerow(["ID", "Date", "Amount", "Currency", "Status", "Donor Name", "Donor Email", "Anonymous", "Message"])

        for donation in donations:
            writer.writerow(
                [
                    donation.id,
                    donation.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    donation.amount,
                    donation.currency,
                    donation.status,
                    donation.donor_name or "N/A",
                    donation.donor_email or "N/A",
                    "Yes" if donation.is_anonymous else "No",
                    donation.message or "N/A",
                ]
            )

        return response

    # Get statistics
    total_donations_count = donations.count()
    total_amount = donations.filter(status=Donation.DonationStatus.COMPLETED).aggregate(total=Sum("amount"))["total"] or 0

    pending_count = donations.filter(status=Donation.DonationStatus.PENDING).count()
    completed_count = donations.filter(status=Donation.DonationStatus.COMPLETED).count()
    failed_count = donations.filter(status=Donation.DonationStatus.FAILED).count()
    refunded_count = donations.filter(status=Donation.DonationStatus.REFUNDED).count()

    # Pagination
    page_size = 20
    page = int(request.GET.get("page", 1))
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    paginated_donations = donations.order_by("-created_at")[start_idx:end_idx]

    total_pages = (total_donations_count + page_size - 1) // page_size

    context = {
        "active_page": "donations",
        "donations": paginated_donations,
        "total_donations": total_donations_count,
        "total_amount": total_amount,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "refunded_count": refunded_count,
        "current_page": page,
        "total_pages": total_pages,
        "status_filter": status_filter,
        "date_filter": date_filter,
        "search_query": search_query,
    }

    return render(request, "custom_admin/donations_list.html", context)


@custom_admin_required
def admin_donation_detail(request, donation_id):
    """Admin view for donation details"""
    donation = get_object_or_404(Donation, id=donation_id)

    # Get Stripe payment details if available
    payment_details = None
    if donation.stripe_payment_id:
        try:
            payment_details = stripe.PaymentIntent.retrieve(donation.stripe_payment_id)
        except stripe.error.StripeError:
            payment_details = None

    context = {
        "active_page": "donations",
        "donation": donation,
        "payment_details": payment_details,
    }

    return render(request, "custom_admin/donation_detail.html", context)


@custom_admin_required
@require_POST
def admin_donation_refund(request, donation_id):
    """Admin view to refund a donation"""
    donation = get_object_or_404(Donation, id=donation_id)

    # Check if donation can be refunded
    if donation.status != Donation.DonationStatus.COMPLETED:
        messages.error(request, f"Cannot refund donation #{donation.id} because its status is {donation.get_status_display()}.")
        return redirect("admin_donation_detail", donation_id=donation_id)

    # Process refund through Stripe
    try:
        refund = stripe.Refund.create(payment_intent=donation.stripe_payment_id)

        # Update the donation status
        donation.status = Donation.DonationStatus.REFUNDED
        donation.save()

        # Log the action
        ModeratorAction.objects.create(
            moderator=request.user,
            action_type="other",
            content_type="donation",
            content_identifier=f"Donation #{donation.id}",
            notes=f"Refunded donation of {donation.amount} {donation.currency}",
        )

        messages.success(request, f"Donation #{donation.id} has been refunded successfully.")
    except stripe.error.StripeError as e:
        messages.error(request, f"Error refunding donation: {str(e)}")

    return redirect("admin_donation_detail", donation_id=donation_id)
