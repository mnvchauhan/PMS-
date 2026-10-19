import csv
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.db.models import Q, Sum, Count
from django.db import transaction
from django.utils import timezone

from .models import (
    RoomType, Room, Guest, Reservation, Stay,
    Invoice, InvoiceItem, Payment, GuestRequest, ShiftHandover,
    UserProfile, ActivityLog
)
from .forms import (
    GuestForm, ReservationForm, CheckInReservationForm, WalkInCheckInForm,
    CheckOutForm, InvoiceItemForm, PaymentForm, RoomForm, RoomTypeForm,
    GuestRequestForm, ShiftHandoverForm
)


def log_activity(user, action, details):
    try:
        ActivityLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            details=details
        )
    except Exception:
        pass


# ==========================================
# AUTHENTICATION
# ==========================================

def pms_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            log_activity(user, 'LOGIN', f"User {user.username} logged in at front desk.")
            messages.success(request, f"Welcome to Front Desk, {user.get_full_name() or user.username}!")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {'form': form})


def pms_logout(request):
    if request.user.is_authenticated:
        log_activity(request.user, 'LOGOUT', f"User {request.user.username} logged out.")
        logout(request)
        messages.info(request, "You have been logged out safely.")
    return redirect('login')


# ==========================================
# 1. FRONT OFFICE DASHBOARD
# ==========================================

@login_required
def dashboard(request):
    today = date.today()

    # Room stats
    total_rooms = Room.objects.count()
    available_rooms = Room.objects.filter(status='AVAILABLE').count()
    occupied_rooms = Room.objects.filter(status='OCCUPIED').count()
    reserved_rooms = Room.objects.filter(status='RESERVED').count()
    cleaning_rooms = Room.objects.filter(status='CLEANING').count()
    out_of_order_rooms = Room.objects.filter(status='OUT_OF_ORDER').count()

    occupancy_rate = round((occupied_rooms / total_rooms) * 100, 1) if total_rooms > 0 else 0.0

    # Operational figures for today
    today_arrivals = Reservation.objects.filter(check_in_date=today, status='CONFIRMED').select_related('guest', 'room_type')
    today_departures = Stay.objects.filter(expected_check_out=today, status='ACTIVE').select_related('guest', 'room')
    in_house_stays = Stay.objects.filter(status='ACTIVE').select_related('guest', 'room', 'invoice')

    # Financial / Pending Payments
    unpaid_invoices = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']).select_related('guest', 'stay', 'stay__room')
    pending_balance_sum = sum(inv.balance_due for inv in unpaid_invoices)

    # Active requests and handovers
    urgent_requests = GuestRequest.objects.filter(status__in=['PENDING', 'IN_PROGRESS']).select_related('guest', 'room')[:5]
    latest_handover = ShiftHandover.objects.select_related('handed_over_by').first()

    # Room rack snapshot by floor
    floors = Room.objects.values_list('floor', flat=True).distinct().order_by('floor')
    rooms_by_floor = []
    for f in floors:
        rooms_by_floor.append({
            'floor': f,
            'rooms': Room.objects.filter(floor=f).select_related('room_type').order_by('room_number')
        })

    context = {
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied_rooms': occupied_rooms,
        'reserved_rooms': reserved_rooms,
        'cleaning_rooms': cleaning_rooms,
        'out_of_order_rooms': out_of_order_rooms,
        'occupancy_rate': occupancy_rate,
        'today_arrivals': today_arrivals,
        'today_departures': today_departures,
        'in_house_stays': in_house_stays,
        'pending_balance_sum': pending_balance_sum,
        'urgent_requests': urgent_requests,
        'latest_handover': latest_handover,
        'rooms_by_floor': rooms_by_floor,
        'today': today,
    }
    return render(request, 'pms/dashboard.html', context)


# ==========================================
# 2. ROOM MANAGEMENT & ROOM RACK
# ==========================================

@login_required
def room_list(request):
    rooms = Room.objects.select_related('room_type').all()

    # Filters
    room_type_id = request.GET.get('room_type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    clean_filter = request.GET.get('clean_status', '').strip()
    floor_filter = request.GET.get('floor', '').strip()

    if room_type_id:
        rooms = rooms.filter(room_type_id=room_type_id)
    if status_filter:
        rooms = rooms.filter(status=status_filter)
    if clean_filter:
        rooms = rooms.filter(clean_status=clean_filter)
    if floor_filter:
        rooms = rooms.filter(floor=floor_filter)

    room_types = RoomType.objects.all()
    floors = Room.objects.values_list('floor', flat=True).distinct().order_by('floor')

    context = {
        'rooms': rooms,
        'room_types': room_types,
        'floors': floors,
        'selected_room_type': room_type_id,
        'selected_status': status_filter,
        'selected_clean': clean_filter,
        'selected_floor': floor_filter,
    }
    return render(request, 'pms/room_list.html', context)


@login_required
def room_matrix(request):
    """Front Desk visual Room Rack grouped by floor with 1-click status actions."""
    floors = Room.objects.values_list('floor', flat=True).distinct().order_by('floor')
    room_types = RoomType.objects.all()

    type_filter = request.GET.get('room_type')
    status_filter = request.GET.get('status')

    rack_data = []
    for f in floors:
        f_rooms = Room.objects.filter(floor=f).select_related('room_type')
        if type_filter:
            f_rooms = f_rooms.filter(room_type_id=type_filter)
        if status_filter:
            f_rooms = f_rooms.filter(status=status_filter)

        # Attach active stay if occupied
        room_items = []
        for r in f_rooms:
            stay = r.stays.filter(status='ACTIVE').select_related('guest').first()
            room_items.append({'room': r, 'stay': stay})

        rack_data.append({'floor': f, 'items': room_items})

    context = {
        'rack_data': rack_data,
        'room_types': room_types,
        'selected_type': type_filter,
        'selected_status': status_filter,
    }
    return render(request, 'pms/room_matrix.html', context)


@login_required
def room_create(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            log_activity(request.user, 'ROOM_CREATE', f"Added Room {room.room_number} ({room.room_type.code}).")
            messages.success(request, f"Room {room.room_number} created successfully.")
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'pms/room_form.html', {'form': form, 'title': 'Add New Room'})


@login_required
def room_update(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            room = form.save()
            log_activity(request.user, 'ROOM_UPDATE', f"Updated Room {room.room_number}.")
            messages.success(request, f"Room {room.room_number} details updated.")
            return redirect('room_list')
    else:
        form = RoomForm(instance=room)
    return render(request, 'pms/room_form.html', {'form': form, 'room': room, 'title': f"Edit Room {room.room_number}"})


@login_required
def room_clean_toggle(request, pk):
    """1-click Housekeeping update: from CLEANING / DIRTY -> AVAILABLE / CLEAN."""
    room = get_object_or_404(Room, pk=pk)
    if room.status == 'OCCUPIED':
        messages.error(request, f"Room {room.room_number} is currently occupied by an active guest.")
    else:
        room.status = 'AVAILABLE'
        room.clean_status = 'CLEAN'
        room.save()
        log_activity(request.user, 'ROOM_CLEAN', f"Room {room.room_number} marked Clean & Available.")
        messages.success(request, f"Room {room.room_number} is now marked Clean and Available for check-in.")

    next_url = request.GET.get('next', 'room_list')
    return redirect(next_url)


# Room Types
@login_required
def room_type_list(request):
    types = RoomType.objects.annotate(room_count=Count('rooms')).all()
    if request.method == 'POST':
        form = RoomTypeForm(request.POST)
        if form.is_valid():
            rt = form.save()
            log_activity(request.user, 'ROOM_TYPE_CREATE', f"Created room type {rt.name}.")
            messages.success(request, f"Room type '{rt.name}' created.")
            return redirect('room_type_list')
    else:
        form = RoomTypeForm()
    return render(request, 'pms/room_type_list.html', {'room_types': types, 'form': form})


@login_required
def room_type_update(request, pk):
    rt = get_object_or_404(RoomType, pk=pk)
    if request.method == 'POST':
        form = RoomTypeForm(request.POST, instance=rt)
        if form.is_valid():
            form.save()
            messages.success(request, f"Room type '{rt.name}' updated.")
            return redirect('room_type_list')
    else:
        form = RoomTypeForm(instance=rt)
    return render(request, 'pms/room_type_form.html', {'form': form, 'room_type': rt})


# ==========================================
# 3. GUEST MANAGEMENT
# ==========================================

@login_required
def guest_list(request):
    guests = Guest.objects.all()

    query = request.GET.get('q', '').strip()
    if query:
        guests = guests.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(id_number__icontains=query)
        )

    context = {
        'guests': guests,
        'search_query': query,
        'total_count': guests.count(),
    }
    return render(request, 'pms/guest_list.html', context)


@login_required
def guest_create(request):
    if request.method == 'POST':
        form = GuestForm(request.POST)
        if form.is_valid():
            guest = form.save()
            log_activity(request.user, 'GUEST_CREATE', f"Registered guest {guest.full_name} ({guest.phone}).")
            messages.success(request, f"Guest '{guest.full_name}' registered successfully.")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('guest_detail', pk=guest.pk)
    else:
        form = GuestForm()
    return render(request, 'pms/guest_form.html', {'form': form, 'title': 'Register New Guest'})


@login_required
def guest_detail(request, pk):
    guest = get_object_or_404(Guest, pk=pk)
    stays = guest.stays.select_related('room', 'invoice').all()
    reservations = guest.reservations.select_related('room_type', 'assigned_room').all()

    total_spent = sum(s.invoice.total_amount for s in stays if hasattr(s, 'invoice'))

    context = {
        'guest': guest,
        'stays': stays,
        'reservations': reservations,
        'total_spent': total_spent,
    }
    return render(request, 'pms/guest_detail.html', context)


@login_required
def guest_update(request, pk):
    guest = get_object_or_404(Guest, pk=pk)
    if request.method == 'POST':
        form = GuestForm(request.POST, instance=guest)
        if form.is_valid():
            guest = form.save()
            messages.success(request, f"Guest '{guest.full_name}' details updated.")
            return redirect('guest_detail', pk=guest.pk)
    else:
        form = GuestForm(instance=guest)
    return render(request, 'pms/guest_form.html', {'form': form, 'guest': guest, 'title': f"Edit Guest: {guest.full_name}"})


# ==========================================
# 4. RESERVATION MANAGEMENT
# ==========================================

@login_required
def reservation_list(request):
    reservations = Reservation.objects.select_related('guest', 'room_type', 'assigned_room').all()

    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_filter = request.GET.get('date', '').strip()

    if query:
        reservations = reservations.filter(
            Q(booking_reference__icontains=query) |
            Q(guest__first_name__icontains=query) |
            Q(guest__last_name__icontains=query) |
            Q(guest__phone__icontains=query)
        )
    if status_filter:
        reservations = reservations.filter(status=status_filter)
    if date_filter:
        reservations = reservations.filter(check_in_date=date_filter)

    context = {
        'reservations': reservations,
        'search_query': query,
        'selected_status': status_filter,
        'selected_date': date_filter,
        'total_count': reservations.count(),
    }
    return render(request, 'pms/reservation_list.html', context)


@login_required
def reservation_create(request):
    initial = {
        'check_in_date': date.today(),
        'check_out_date': date.today() + timedelta(days=1),
    }
    pre_guest = request.GET.get('guest')
    if pre_guest:
        initial['guest'] = pre_guest

    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            res = form.save(commit=False)
            res.created_by = request.user
            res.save()
            # If a room was assigned right away, mark room as RESERVED if check-in is today
            if res.assigned_room and res.check_in_date == date.today():
                res.assigned_room.status = 'RESERVED'
                res.assigned_room.save()

            log_activity(request.user, 'RESERVATION_CREATE', f"Created reservation {res.booking_reference} for {res.guest.full_name}.")
            messages.success(request, f"Reservation confirmed! Booking Reference: {res.booking_reference}")
            return redirect('reservation_detail', pk=res.pk)
        else:
            messages.error(request, "Please check the reservation details and date availability.")
    else:
        form = ReservationForm(initial=initial)

    return render(request, 'pms/reservation_form.html', {'form': form, 'title': 'Create New Reservation'})


@login_required
def reservation_detail(request, pk):
    res = get_object_or_404(
        Reservation.objects.select_related('guest', 'room_type', 'assigned_room', 'created_by'),
        pk=pk
    )
    context = {'reservation': res}
    return render(request, 'pms/reservation_detail.html', context)


@login_required
def reservation_cancel(request, pk):
    res = get_object_or_404(Reservation, pk=pk)
    if request.method == 'POST':
        res.status = 'CANCELLED'
        res.save()
        if res.assigned_room and res.assigned_room.status == 'RESERVED':
            res.assigned_room.status = 'AVAILABLE'
            res.assigned_room.save()
        log_activity(request.user, 'RESERVATION_CANCEL', f"Cancelled reservation {res.booking_reference}.")
        messages.success(request, f"Reservation {res.booking_reference} has been cancelled.")
        return redirect('reservation_list')

    return render(request, 'pms/reservation_confirm_cancel.html', {'reservation': res})


# ==========================================
# 5. FRONT DESK CHECK-IN WORKFLOWS
# ==========================================

@login_required
def arrivals_list(request):
    """Today's arrivals list for front office GSAs."""
    target_date = request.GET.get('date', date.today().isoformat())
    arrivals = Reservation.objects.filter(
        check_in_date=target_date,
        status='CONFIRMED'
    ).select_related('guest', 'room_type', 'assigned_room')

    context = {
        'arrivals': arrivals,
        'target_date': target_date,
        'today': date.today(),
    }
    return render(request, 'pms/arrivals_list.html', context)


@login_required
@transaction.atomic
def check_in_reservation(request, pk):
    """Check-in an existing confirmed reservation."""
    reservation = get_object_or_404(
        Reservation.objects.select_related('guest', 'room_type', 'assigned_room'),
        pk=pk
    )

    if reservation.status != 'CONFIRMED':
        messages.warning(request, f"This reservation is already {reservation.get_status_display()}.")
        return redirect('reservation_detail', pk=reservation.pk)

    if request.method == 'POST':
        form = CheckInReservationForm(reservation, request.POST)
        if form.is_valid():
            selected_room = form.cleaned_data['room']
            num_occupants = form.cleaned_data['num_occupants']
            notes = form.cleaned_data['notes']

            # Double check room availability
            if selected_room.status == 'OCCUPIED':
                messages.error(request, f"Room {selected_room.room_number} is currently occupied by another guest.")
                return render(request, 'pms/check_in_reservation.html', {'reservation': reservation, 'form': form})

            # 1. Update reservation
            reservation.status = 'CHECKED_IN'
            reservation.assigned_room = selected_room
            reservation.save()

            # 2. Update room status to OCCUPIED and DIRTY
            selected_room.status = 'OCCUPIED'
            selected_room.clean_status = 'DIRTY'
            selected_room.save()

            # 3. Create Stay record
            stay = Stay.objects.create(
                reservation=reservation,
                guest=reservation.guest,
                room=selected_room,
                expected_check_out=reservation.check_out_date,
                num_occupants=num_occupants,
                rate_per_night=reservation.rate_per_night,
                status='ACTIVE',
                checked_in_by=request.user,
                notes=notes
            )

            # 4. Generate initial Invoice with estimated room charges
            invoice = Invoice.objects.create(
                stay=stay,
                guest=reservation.guest,
                tax_rate_percent=Decimal('10.00'), # 10% standard hotel tax
            )

            # Add room charges item
            nights = max(1, (reservation.check_out_date - reservation.check_in_date).days)
            InvoiceItem.objects.create(
                invoice=invoice,
                category='ROOM',
                description=f"Room Charge ({nights} night{'s' if nights>1 else ''} @ ${reservation.rate_per_night}/night)",
                quantity=nights,
                unit_price=reservation.rate_per_night,
                amount=Decimal(str(nights)) * reservation.rate_per_night,
                date_charged=reservation.check_in_date
            )

            log_activity(request.user, 'CHECK_IN', f"Checked in {reservation.guest.full_name} to Room {selected_room.room_number} (Ref: {reservation.booking_reference}).")
            messages.success(request, f"Check-in complete! {reservation.guest.full_name} is now in Room {selected_room.room_number}.")
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        form = CheckInReservationForm(reservation)

    return render(request, 'pms/check_in_reservation.html', {
        'reservation': reservation,
        'form': form
    })


@login_required
@transaction.atomic
def walk_in_check_in(request):
    """Fast walk-in check-in without advance reservation."""
    if request.method == 'POST':
        form = WalkInCheckInForm(request.POST)
        if form.is_valid():
            # 1. Register or find guest by phone
            phone = form.cleaned_data['phone']
            guest, _ = Guest.objects.get_or_create(
                phone=phone,
                defaults={
                    'first_name': form.cleaned_data['first_name'],
                    'last_name': form.cleaned_data['last_name'],
                    'email': form.cleaned_data.get('email', ''),
                    'id_type': form.cleaned_data['id_type'],
                    'id_number': form.cleaned_data.get('id_number', ''),
                    'nationality': form.cleaned_data['nationality'],
                }
            )

            selected_room = form.cleaned_data['room']
            check_out_date = form.cleaned_data['check_out_date']
            num_occupants = form.cleaned_data['num_occupants']
            custom_rate = form.cleaned_data.get('custom_rate')
            rate_per_night = custom_rate if custom_rate else selected_room.effective_rate
            notes = form.cleaned_data.get('notes', '')

            # Check room availability
            if selected_room.status != 'AVAILABLE':
                messages.error(request, f"Room {selected_room.room_number} is no longer available.")
                return render(request, 'pms/walk_in_check_in.html', {'form': form})

            # 2. Create walk-in reservation record
            nights = max(1, (check_out_date - date.today()).days)
            reservation = Reservation.objects.create(
                guest=guest,
                room_type=selected_room.room_type,
                assigned_room=selected_room,
                check_in_date=date.today(),
                check_out_date=check_out_date,
                num_adults=num_occupants,
                rate_per_night=rate_per_night,
                status='CHECKED_IN',
                special_requests=notes,
                created_by=request.user
            )

            # 3. Mark room occupied
            selected_room.status = 'OCCUPIED'
            selected_room.clean_status = 'DIRTY'
            selected_room.save()

            # 4. Create Stay
            stay = Stay.objects.create(
                reservation=reservation,
                guest=guest,
                room=selected_room,
                expected_check_out=check_out_date,
                num_occupants=num_occupants,
                rate_per_night=rate_per_night,
                status='ACTIVE',
                checked_in_by=request.user,
                notes=f"Walk-in Guest. {notes}"
            )

            # 5. Create Invoice
            invoice = Invoice.objects.create(
                stay=stay,
                guest=guest,
                tax_rate_percent=Decimal('10.00'),
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                category='ROOM',
                description=f"Room Charge ({nights} night{'s' if nights>1 else ''} @ ${rate_per_night}/night)",
                quantity=nights,
                unit_price=rate_per_night,
                amount=Decimal(str(nights)) * rate_per_night,
                date_charged=date.today()
            )

            log_activity(request.user, 'WALK_IN', f"Walk-in check-in for {guest.full_name} into Room {selected_room.room_number}.")
            messages.success(request, f"Walk-in check-in successful! Assigned Room {selected_room.room_number}.")
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        initial = {'check_out_date': date.today() + timedelta(days=1)}
        form = WalkInCheckInForm(initial=initial)

    return render(request, 'pms/walk_in_check_in.html', {'form': form})


# ==========================================
# 6. IN-HOUSE GUESTS & CHECK-OUT WORKFLOW
# ==========================================

@login_required
def in_house_list(request):
    """All active guests currently staying in the hotel."""
    stays = Stay.objects.filter(status='ACTIVE').select_related('guest', 'room', 'room__room_type', 'invoice')

    query = request.GET.get('q', '').strip()
    if query:
        stays = stays.filter(
            Q(guest__first_name__icontains=query) |
            Q(guest__last_name__icontains=query) |
            Q(room__room_number__icontains=query) |
            Q(guest__phone__icontains=query)
        )

    context = {
        'stays': stays,
        'search_query': query,
        'total_in_house': stays.count(),
        'today': date.today(),
    }
    return render(request, 'pms/in_house_list.html', context)


@login_required
def departures_list(request):
    """Departures due today or specific date."""
    target_date = request.GET.get('date', date.today().isoformat())
    departures = Stay.objects.filter(
        expected_check_out=target_date,
        status='ACTIVE'
    ).select_related('guest', 'room', 'invoice')

    context = {
        'departures': departures,
        'target_date': target_date,
        'today': date.today(),
    }
    return render(request, 'pms/departures_list.html', context)


@login_required
@transaction.atomic
def check_out(request, pk):
    """
    Check-out workflow:
    1. Calculate stay length & room charges.
    2. Display additional charges, taxes, discounts.
    3. Take payment.
    4. Mark Stay as CHECKED_OUT.
    5. Set Room status to CLEANING and DIRTY.
    6. Redirect to printable folio.
    """
    stay = get_object_or_404(
        Stay.objects.select_related('guest', 'room', 'invoice', 'reservation'),
        pk=pk
    )

    if stay.status != 'ACTIVE':
        messages.warning(request, f"Stay for Room {stay.room.room_number} is already checked out.")
        return redirect('invoice_detail', pk=stay.invoice.pk)

    invoice = stay.invoice

    if request.method == 'POST':
        form = CheckOutForm(request.POST)
        if form.is_valid():
            amount_paid = form.cleaned_data['amount_paid']
            payment_method = form.cleaned_data['payment_method']
            transaction_id = form.cleaned_data.get('transaction_id', '')
            discount_amount = form.cleaned_data.get('discount_amount') or Decimal('0.00')
            discount_reason = form.cleaned_data.get('discount_reason', '')
            notes = form.cleaned_data.get('notes', '')

            # Apply authorized discount if any
            if discount_amount > 0:
                invoice.discount_amount = discount_amount
                invoice.discount_reason = discount_reason
                invoice.save()
                invoice.recalculate()

            # Record final payment if amount entered > 0
            if amount_paid > 0:
                Payment.objects.create(
                    invoice=invoice,
                    amount=amount_paid,
                    payment_method=payment_method,
                    transaction_id=transaction_id,
                    notes=f"Check-out payment. {notes}",
                    recorded_by=request.user
                )

            # Mark Stay as CHECKED_OUT
            stay.status = 'CHECKED_OUT'
            stay.actual_check_out_time = timezone.now()
            stay.checked_out_by = request.user
            stay.notes = f"{stay.notes}\nCheck-out note: {notes}".strip()
            stay.save()

            # Update Reservation status
            if stay.reservation:
                stay.reservation.status = 'CHECKED_OUT'
                stay.reservation.save()

            # CRITICAL RULE: Room status becomes CLEANING and DIRTY, NOT immediately available!
            room = stay.room
            room.status = 'CLEANING'
            room.clean_status = 'DIRTY'
            room.save()

            log_activity(request.user, 'CHECK_OUT', f"Checked out {stay.guest.full_name} from Room {room.room_number}. Room released to Housekeeping.")
            messages.success(request, f"Guest {stay.guest.full_name} successfully checked out! Room {room.room_number} sent to Cleaning.")
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        # Pre-fill amount paid with remaining balance
        initial = {
            'amount_paid': invoice.balance_due,
            'payment_method': 'CREDIT_CARD',
        }
        form = CheckOutForm(initial=initial)

    context = {
        'stay': stay,
        'invoice': invoice,
        'form': form,
    }
    return render(request, 'pms/check_out.html', context)


# ==========================================
# 7. BILLING, PAYMENTS & PRINTABLE FOLIO
# ==========================================

@login_required
def invoice_detail(request, pk):
    """Detailed Guest Folio with line items, payments, and quick charge entry."""
    invoice = get_object_or_404(
        Invoice.objects.select_related('guest', 'stay', 'stay__room', 'stay__room__room_type'),
        pk=pk
    )
    items = invoice.items.all()
    payments = invoice.payments.select_related('recorded_by').all()

    item_form = InvoiceItemForm()
    payment_form = PaymentForm(initial={'amount': invoice.balance_due})

    context = {
        'invoice': invoice,
        'items': items,
        'payments': payments,
        'item_form': item_form,
        'payment_form': payment_form,
    }
    return render(request, 'pms/invoice_detail.html', context)


@login_required
def add_invoice_item(request, pk):
    """Add extra charge (Room Service, Laundry, etc.) to an active invoice."""
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = InvoiceItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.invoice = invoice
            item.save()
            log_activity(request.user, 'ADD_CHARGE', f"Added {item.description} (${item.amount}) to Invoice {invoice.invoice_number}.")
            messages.success(request, f"Added charge: {item.description} (${item.amount}).")
        else:
            messages.error(request, "Failed to add charge. Please check form inputs.")
    return redirect('invoice_detail', pk=invoice.pk)


@login_required
def add_payment(request, pk):
    """Record payment against invoice."""
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.recorded_by = request.user
            payment.save()
            log_activity(request.user, 'PAYMENT', f"Recorded payment ${payment.amount} ({payment.get_payment_method_display()}) on Invoice {invoice.invoice_number}.")
            messages.success(request, f"Payment of ${payment.amount} recorded successfully.")
        else:
            messages.error(request, "Please enter a valid payment amount.")
    return redirect('invoice_detail', pk=invoice.pk)


# ==========================================
# 8. GUEST REQUESTS & SHIFT HANDOVER
# ==========================================

@login_required
def guest_request_list(request):
    requests_qs = GuestRequest.objects.select_related('room', 'guest').all()
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    if request.method == 'POST':
        form = GuestRequestForm(request.POST)
        if form.is_valid():
            req = form.save()
            messages.success(request, f"Guest request logged for Room {req.room.room_number}.")
            return redirect('guest_request_list')
    else:
        form = GuestRequestForm()

    context = {
        'requests': requests_qs,
        'form': form,
        'selected_status': status_filter,
    }
    return render(request, 'pms/guest_request_list.html', context)


@login_required
def guest_request_update_status(request, pk):
    req = get_object_or_404(GuestRequest, pk=pk)
    new_status = request.POST.get('status')
    if new_status in ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED']:
        req.status = new_status
        if new_status == 'COMPLETED':
            req.completed_at = timezone.now()
        req.save()
        messages.success(request, f"Request #{req.id} updated to {req.get_status_display()}.")
    return redirect('guest_request_list')


@login_required
def shift_handover_list(request):
    handovers = ShiftHandover.objects.select_related('handed_over_by', 'acknowledged_by').all()

    if request.method == 'POST':
        form = ShiftHandoverForm(request.POST)
        if form.is_valid():
            ho = form.save(commit=False)
            ho.handed_over_by = request.user
            ho.save()
            log_activity(request.user, 'SHIFT_HANDOVER', f"Recorded handover for {ho.get_shift_display()}.")
            messages.success(request, f"Shift handover note recorded successfully.")
            return redirect('shift_handover_list')
    else:
        form = ShiftHandoverForm(initial={'date': date.today(), 'shift': 'MORNING'})

    context = {
        'handovers': handovers,
        'form': form,
    }
    return render(request, 'pms/shift_handover_list.html', context)


# ==========================================
# 9. REPORTS & CSV EXPORTS
# ==========================================

@login_required
def reports_hub(request):
    today = date.today()
    start_date = request.GET.get('start_date', (today - timedelta(days=7)).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())

    # Occupancy figures
    total_rooms = Room.objects.count()
    occupied_rooms = Room.objects.filter(status='OCCUPIED').count()
    available_rooms = Room.objects.filter(status='AVAILABLE').count()
    cleaning_rooms = Room.objects.filter(status='CLEANING').count()

    # Revenue in date range
    payments_qs = Payment.objects.filter(
        payment_date__date__gte=start_date,
        payment_date__date__lte=end_date
    )
    total_revenue = payments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Breakdown by payment method
    revenue_by_method = payments_qs.values('payment_method').annotate(total=Sum('amount'))

    # Recent reservations in date range
    recent_reservations = Reservation.objects.filter(
        check_in_date__gte=start_date,
        check_in_date__lte=end_date
    ).select_related('guest', 'room_type')

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'available_rooms': available_rooms,
        'cleaning_rooms': cleaning_rooms,
        'total_revenue': total_revenue,
        'revenue_by_method': revenue_by_method,
        'recent_reservations': recent_reservations,
    }
    return render(request, 'pms/reports_hub.html', context)


@login_required
def export_arrivals_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="arrivals_report_{date.today()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Booking Ref', 'Guest Name', 'Phone', 'Room Type',
        'Assigned Room', 'Check-In Date', 'Check-Out Date',
        'Nights', 'Rate / Night', 'Status'
    ])

    arrivals = Reservation.objects.filter(status='CONFIRMED').select_related('guest', 'room_type', 'assigned_room')
    for a in arrivals:
        writer.writerow([
            a.booking_reference,
            a.guest.full_name,
            a.guest.phone,
            a.room_type.name,
            a.assigned_room.room_number if a.assigned_room else 'Unassigned',
            a.check_in_date.strftime('%Y-%m-%d'),
            a.check_out_date.strftime('%Y-%m-%d'),
            a.nights,
            a.rate_per_night,
            a.get_status_display()
        ])
    return response


@login_required
def export_departures_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="departures_report_{date.today()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Room Number', 'Guest Name', 'Phone', 'Check-In Time',
        'Expected Departure', 'Rate / Night', 'Balance Due ($)', 'Status'
    ])

    stays = Stay.objects.filter(status='ACTIVE').select_related('guest', 'room', 'invoice')
    for s in stays:
        writer.writerow([
            s.room.room_number,
            s.guest.full_name,
            s.guest.phone,
            s.check_in_time.strftime('%Y-%m-%d %H:%M'),
            s.expected_check_out.strftime('%Y-%m-%d'),
            s.rate_per_night,
            s.invoice.balance_due,
            s.get_status_display()
        ])
    return response


@login_required
def export_revenue_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="revenue_report_{date.today()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Date & Time', 'Invoice #', 'Guest Name', 'Payment Method',
        'Amount ($)', 'Transaction ID', 'Cashier / User'
    ])

    payments = Payment.objects.select_related('invoice', 'invoice__guest', 'recorded_by').all()
    for p in payments:
        writer.writerow([
            p.payment_date.strftime('%Y-%m-%d %H:%M'),
            p.invoice.invoice_number,
            p.invoice.guest.full_name,
            p.get_payment_method_display(),
            p.amount,
            p.transaction_id,
            p.recorded_by.username if p.recorded_by else 'System'
        ])
    return response
