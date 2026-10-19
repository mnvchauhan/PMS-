import uuid
from decimal import Decimal
from datetime import date, datetime

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse


class RoomType(models.Model):
    name = models.CharField(max_length=60, unique=True, help_text="e.g. Standard Single, Deluxe King, Executive Suite")
    code = models.CharField(max_length=15, unique=True, help_text="e.g. SGL, DLX, STE")
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="Default nightly room rate")
    max_occupancy = models.PositiveIntegerField(default=2, help_text="Maximum guests allowed")
    description = models.TextField(blank=True)
    amenities = models.TextField(blank=True, help_text="e.g. King Bed, Wi-Fi, Balcony, Mini Bar, AC")

    class Meta:
        ordering = ['base_rate']

    def __str__(self):
        return f"{self.name} ({self.code}) - ${self.base_rate}/night"

    @property
    def total_rooms_count(self):
        return self.rooms.count()


class Room(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('OCCUPIED', 'Occupied'),
        ('RESERVED', 'Reserved'),
        ('CLEANING', 'Cleaning'),
        ('OUT_OF_ORDER', 'Out of Order'),
    ]

    CLEAN_CHOICES = [
        ('CLEAN', 'Clean'),
        ('DIRTY', 'Dirty'),
        ('INSPECTING', 'Inspecting'),
    ]

    room_number = models.CharField(max_length=10, unique=True, help_text="e.g. 101, 102, 201")
    floor = models.PositiveIntegerField(default=1)
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name='rooms')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    clean_status = models.CharField(max_length=20, choices=CLEAN_CHOICES, default='CLEAN')
    current_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                      help_text="Optional custom rate. If blank, room type base rate is used.")
    notes = models.TextField(blank=True, help_text="Internal notes e.g. connecting door, corner room")

    class Meta:
        ordering = ['floor', 'room_number']

    def __str__(self):
        return f"Room {self.room_number} ({self.room_type.code})"

    @property
    def effective_rate(self):
        return self.current_rate if self.current_rate is not None else self.room_type.base_rate

    @property
    def is_vacant(self):
        return self.status in ['AVAILABLE', 'CLEANING']

    @property
    def can_check_in(self):
        return self.status == 'AVAILABLE' and self.clean_status == 'CLEAN'

    @property
    def badge_class(self):
        mapping = {
            'AVAILABLE': 'success',
            'OCCUPIED': 'danger',
            'RESERVED': 'primary',
            'CLEANING': 'warning text-dark',
            'OUT_OF_ORDER': 'secondary',
        }
        return mapping.get(self.status, 'secondary')

    @property
    def clean_badge_class(self):
        mapping = {
            'CLEAN': 'success',
            'DIRTY': 'danger',
            'INSPECTING': 'warning text-dark',
        }
        return mapping.get(self.clean_status, 'secondary')


class Guest(models.Model):
    ID_TYPE_CHOICES = [
        ('PASSPORT', 'Passport'),
        ('NATIONAL_ID', 'National ID Card'),
        ('DRIVING_LICENSE', "Driver's License"),
        ('VOTER_ID', 'Voter ID'),
        ('OTHER', 'Other Official ID'),
    ]

    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    phone = models.CharField(max_length=25)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    nationality = models.CharField(max_length=60, default='Domestic / Citizen')
    id_type = models.CharField(max_length=30, choices=ID_TYPE_CHOICES, default='PASSPORT')
    id_number = models.CharField(max_length=60, blank=True, help_text="Identification document number")
    preferences = models.TextField(blank=True, help_text="e.g. High floor, Non-smoking, Extra towels, Late check-in")
    remarks = models.TextField(blank=True, help_text="Internal front desk notes or VIP status")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def masked_id(self):
        if not self.id_number:
            return "Not Provided"
        if len(self.id_number) <= 4:
            return self.id_number
        return f"•••• {self.id_number[-4:]}"

    @property
    def previous_stays_count(self):
        return self.stays.filter(status='CHECKED_OUT').count()

    @property
    def active_stay(self):
        return self.stays.filter(status='ACTIVE').first()


class Reservation(models.Model):
    STATUS_CHOICES = [
        ('CONFIRMED', 'Confirmed'),
        ('CHECKED_IN', 'Checked In'),
        ('CHECKED_OUT', 'Checked Out'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]

    booking_reference = models.CharField(max_length=30, unique=True, editable=False)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='reservations')
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name='reservations')
    assigned_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservations')
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    num_adults = models.PositiveIntegerField(default=1)
    num_children = models.PositiveIntegerField(default=0)
    rate_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    special_requests = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['check_in_date', '-created_at']

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            today_str = date.today().strftime('%Y%m%d')
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_reference = f"RES-{today_str}-{uid}"
        # Calculate estimated total
        nights = max(1, (self.check_out_date - self.check_in_date).days)
        self.estimated_total = Decimal(str(nights)) * self.rate_per_night
        super().save(*args, **kwargs)

    def clean(self):
        if self.check_in_date and self.check_out_date:
            if self.check_out_date <= self.check_in_date:
                raise ValidationError("Check-out date must be strictly after the check-in date.")
        # Check overlapping reservation for assigned room
        if self.assigned_room and self.status in ['CONFIRMED', 'CHECKED_IN']:
            overlap = Reservation.objects.filter(
                assigned_room=self.assigned_room,
                status__in=['CONFIRMED', 'CHECKED_IN']
            ).exclude(pk=self.pk).filter(
                check_in_date__lt=self.check_out_date,
                check_out_date__gt=self.check_in_date
            )
            if overlap.exists():
                raise ValidationError(f"Room {self.assigned_room.room_number} is already booked for overlapping dates ({overlap.first().booking_reference}).")

    def __str__(self):
        return f"{self.booking_reference} - {self.guest.full_name} ({self.check_in_date} to {self.check_out_date})"

    @property
    def nights(self):
        return max(1, (self.check_out_date - self.check_in_date).days)

    @property
    def is_today_arrival(self):
        return self.check_in_date == date.today() and self.status == 'CONFIRMED'

    @property
    def status_badge(self):
        mapping = {
            'CONFIRMED': 'primary',
            'CHECKED_IN': 'success',
            'CHECKED_OUT': 'info',
            'CANCELLED': 'danger',
            'NO_SHOW': 'secondary',
        }
        return mapping.get(self.status, 'secondary')


class Stay(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active (In-House)'),
        ('CHECKED_OUT', 'Checked Out'),
    ]

    reservation = models.OneToOneField(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='stay')
    guest = models.ForeignKey(Guest, on_delete=models.PROTECT, related_name='stays')
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='stays')
    check_in_time = models.DateTimeField(default=timezone.now)
    expected_check_out = models.DateField()
    actual_check_out_time = models.DateTimeField(null=True, blank=True)
    num_occupants = models.PositiveIntegerField(default=1)
    rate_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    checked_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checkins_handled')
    checked_out_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checkouts_handled')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-check_in_time']

    def __str__(self):
        return f"Stay: Room {self.room.room_number} - {self.guest.full_name} ({self.get_status_display()})"

    @property
    def nights_count(self):
        end_date = self.actual_check_out_time.date() if self.actual_check_out_time else self.expected_check_out
        start_date = self.check_in_time.date()
        diff = (end_date - start_date).days
        return max(1, diff)

    @property
    def calculated_room_charges(self):
        return Decimal(str(self.nights_count)) * self.rate_per_night

    @property
    def is_due_today(self):
        return self.status == 'ACTIVE' and self.expected_check_out == date.today()


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid in Full'),
    ]

    invoice_number = models.CharField(max_length=35, unique=True, editable=False)
    stay = models.OneToOneField(Stay, on_delete=models.CASCADE, related_name='invoice')
    guest = models.ForeignKey(Guest, on_delete=models.PROTECT, related_name='invoices')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'), help_text="Taxes (e.g. 10.00%)")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_reason = models.CharField(max_length=150, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNPAID')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            today_str = date.today().strftime('%Y%m%d')
            uid = uuid.uuid4().hex[:6].upper()
            self.invoice_number = f"INV-{today_str}-{uid}"
        super().save(*args, **kwargs)

    def recalculate(self):
        """Recalculate subtotal, taxes, discounts, totals, and payment status."""
        items = self.items.all()
        subtotal = sum(i.amount for i in items)
        self.subtotal = subtotal

        taxable = max(Decimal('0.00'), subtotal - self.discount_amount)
        self.tax_amount = round(taxable * (self.tax_rate_percent / Decimal('100.00')), 2)
        self.total_amount = taxable + self.tax_amount

        total_paid = sum(p.amount for p in self.payments.all())
        if total_paid >= self.total_amount and self.total_amount > 0:
            self.status = 'PAID'
        elif total_paid > 0:
            self.status = 'PARTIAL'
        else:
            self.status = 'UNPAID'
        self.save()

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments.all())

    @property
    def balance_due(self):
        return max(Decimal('0.00'), self.total_amount - self.total_paid)

    @property
    def status_badge(self):
        mapping = {
            'UNPAID': 'danger',
            'PARTIAL': 'warning text-dark',
            'PAID': 'success',
        }
        return mapping.get(self.status, 'secondary')


class InvoiceItem(models.Model):
    CATEGORY_CHOICES = [
        ('ROOM', 'Room Charge'),
        ('FOOD_BEVERAGE', 'Food & Beverage / Dining'),
        ('LAUNDRY', 'Laundry Service'),
        ('MINIBAR', 'Mini Bar'),
        ('TRANSPORT', 'Airport Transfer / Cab'),
        ('SERVICE', 'Extra Service / Amenity'),
        ('DAMAGE', 'Damage Charge'),
        ('OTHER', 'Other Charge'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    category = models.CharField(max_length=25, choices=CATEGORY_CHOICES, default='ROOM')
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_charged = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['date_charged', 'id']

    def save(self, *args, **kwargs):
        self.amount = Decimal(str(self.quantity)) * self.unit_price
        super().save(*args, **kwargs)
        self.invoice.recalculate()

    def delete(self, *args, **kwargs):
        inv = self.invoice
        super().delete(*args, **kwargs)
        inv.recalculate()


class Payment(models.Model):
    METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CREDIT_CARD', 'Credit Card'),
        ('DEBIT_CARD', 'Debit Card'),
        ('UPI_ONLINE', 'UPI / Online Transfer'),
        ('BANK_TRANSFER', 'Bank Wire / Direct Billing'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=25, choices=METHOD_CHOICES, default='CASH')
    payment_date = models.DateTimeField(default=timezone.now)
    transaction_id = models.CharField(max_length=80, blank=True, help_text="Card auth code or UPI transaction reference")
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-payment_date']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.recalculate()

    def delete(self, *args, **kwargs):
        inv = self.invoice
        super().delete(*args, **kwargs)
        inv.recalculate()


class GuestRequest(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    stay = models.ForeignKey(Stay, on_delete=models.CASCADE, null=True, blank=True, related_name='requests')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='guest_requests')
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='requests')
    request_text = models.TextField(help_text="Details of guest request, e.g. Extra pillows, iron, luggage help")
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Req #{self.id} (Room {self.room.room_number}): {self.request_text[:30]}"


class ShiftHandover(models.Model):
    SHIFT_CHOICES = [
        ('MORNING', 'Morning Shift (07:00 - 15:00)'),
        ('EVENING', 'Evening Shift (15:00 - 23:00)'),
        ('NIGHT', 'Night Shift (23:00 - 07:00)'),
    ]

    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES)
    date = models.DateField(default=timezone.now)
    notes = models.TextField(help_text="Events during shift, VIP arrivals, complaints, room repairs")
    pending_matters = models.TextField(help_text="Tasks that must be carried over to the incoming shift")
    cash_in_drawer = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Cash count in front desk drawer")
    handed_over_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='handovers_given')
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handovers_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_shift_display()} - {self.date}"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('GSA', 'Front Desk Staff / GSA'),
        ('MANAGER', 'Front Office Manager'),
        ('ADMIN', 'System Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pms_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='GSA')
    phone = models.CharField(max_length=20, blank=True)
    employee_id = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} | {self.action} | {self.user}"
