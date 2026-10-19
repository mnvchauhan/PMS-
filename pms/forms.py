from datetime import date
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    RoomType, Room, Guest, Reservation, Stay,
    Invoice, InvoiceItem, Payment, GuestRequest, ShiftHandover
)


class GuestForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = [
            'first_name', 'last_name', 'phone', 'email', 'address',
            'nationality', 'id_type', 'id_number', 'preferences', 'remarks'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'guest@example.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'City, State, Country'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. United States, Canadian, etc.'}),
            'id_type': forms.Select(attrs={'class': 'form-select'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Passport or ID number'}),
            'preferences': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g. Non-smoking, High floor, Extra pillows'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'VIP notes or guest alerts'}),
        }


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = [
            'guest', 'room_type', 'assigned_room', 'check_in_date', 'check_out_date',
            'num_adults', 'num_children', 'rate_per_night', 'special_requests'
        ]
        widgets = {
            'guest': forms.Select(attrs={'class': 'form-select'}),
            'room_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_room_type'}),
            'assigned_room': forms.Select(attrs={'class': 'form-select', 'id': 'id_assigned_room'}),
            'check_in_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'check_out_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'num_adults': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 6}),
            'num_children': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 4}),
            'rate_per_night': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'special_requests': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Special amenities or timing requests'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in_date')
        check_out = cleaned_data.get('check_out_date')
        room = cleaned_data.get('assigned_room')
        room_type = cleaned_data.get('room_type')

        if check_in and check_out:
            if check_out <= check_in:
                self.add_error('check_out_date', "Check-out date must be after check-in date.")

        if room and room_type and room.room_type != room_type:
            self.add_error('assigned_room', f"Room {room.room_number} is not a {room_type.name}.")

        if room and check_in and check_out:
            overlap = Reservation.objects.filter(
                assigned_room=room,
                status__in=['CONFIRMED', 'CHECKED_IN']
            ).exclude(pk=self.instance.pk).filter(
                check_in_date__lt=check_out,
                check_out_date__gt=check_in
            )
            if overlap.exists():
                self.add_error('assigned_room', f"Room {room.room_number} is already booked for these dates ({overlap.first().booking_reference}).")

        return cleaned_data


class CheckInReservationForm(forms.Form):
    """Form to confirm check-in of an existing reservation."""
    room = forms.ModelChoiceField(
        queryset=Room.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Assign Room"
    )
    num_occupants = forms.IntegerField(
        initial=1, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Number of Occupants"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Front desk arrival notes'}),
        label="Check-in Notes"
    )

    def __init__(self, reservation, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reservation = reservation
        # Allow vacant and clean rooms of the reserved type, OR the pre-assigned room if already set
        qs = Room.objects.filter(room_type=reservation.room_type, status='AVAILABLE')
        if reservation.assigned_room:
            qs = qs | Room.objects.filter(pk=reservation.assigned_room.pk)
        self.fields['room'].queryset = qs.distinct()
        if reservation.assigned_room:
            self.fields['room'].initial = reservation.assigned_room
        elif qs.exists():
            self.fields['room'].initial = qs.first()
        self.fields['num_occupants'].initial = reservation.num_adults + reservation.num_children


class WalkInCheckInForm(forms.Form):
    """Seamless walk-in guest check-in at the front desk."""
    # Guest Info
    first_name = forms.CharField(max_length=60, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=60, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}))
    phone = forms.CharField(max_length=25, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 000-0000'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'guest@example.com'}))
    id_type = forms.ChoiceField(choices=Guest.ID_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    id_number = forms.CharField(max_length=60, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID or Passport Number'}))
    nationality = forms.CharField(initial='Domestic / Citizen', widget=forms.TextInput(attrs={'class': 'form-control'}))

    # Stay Details
    room = forms.ModelChoiceField(
        queryset=Room.objects.filter(status='AVAILABLE', clean_status='CLEAN'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Available Room"
    )
    check_out_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Expected Check-out Date"
    )
    num_occupants = forms.IntegerField(
        initial=1, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    custom_rate = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to use room base rate', 'step': '0.01'}),
        label="Agreed Rate / Night"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Front desk notes'}),
        label="Notes / Special Requests"
    )

    def clean_check_out_date(self):
        check_out = self.cleaned_data.get('check_out_date')
        if check_out and check_out <= date.today():
            raise forms.ValidationError("Expected check-out date must be in the future.")
        return check_out


class CheckOutForm(forms.Form):
    """Process check-out, record final payment, and release room to cleaning."""
    payment_method = forms.ChoiceField(
        choices=Payment.METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    amount_paid = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Payment Amount Received"
    )
    transaction_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Card approval code, UPI Ref, etc.'}),
        label="Transaction Ref / Auth Code"
    )
    discount_amount = forms.DecimalField(
        required=False, initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Manager Authorized Discount"
    )
    discount_reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for discount'}),
        label="Discount Authorization Note"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Final departure remarks / key return note'}),
        label="Check-out Remarks"
    )


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['category', 'description', 'quantity', 'unit_price', 'date_charged']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Club Sandwich & Juice'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'date_charged': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'transaction_id', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transaction ID / Auth Code'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Payment notes'}),
        }


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['room_number', 'floor', 'room_type', 'status', 'clean_status', 'current_rate', 'notes']
        widgets = {
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 101'}),
            'floor': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'room_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'clean_status': forms.Select(attrs={'class': 'form-select'}),
            'current_rate': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to use base rate', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Room notes'}),
        }


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = ['name', 'code', 'base_rate', 'max_occupancy', 'amenities', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Deluxe King'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DLX'}),
            'base_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_occupancy': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'amenities': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g. King Bed, Mini Bar, Balcony, Wi-Fi'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Room type overview'}),
        }


class GuestRequestForm(forms.ModelForm):
    class Meta:
        model = GuestRequest
        fields = ['room', 'guest', 'request_text', 'priority', 'status']
        widgets = {
            'room': forms.Select(attrs={'class': 'form-select'}),
            'guest': forms.Select(attrs={'class': 'form-select'}),
            'request_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g. Extra pillows, laundry pickup, late checkout'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class ShiftHandoverForm(forms.ModelForm):
    class Meta:
        model = ShiftHandover
        fields = ['shift', 'date', 'cash_in_drawer', 'notes', 'pending_matters']
        widgets = {
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cash_in_drawer': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Events during shift, VIP arrivals, complaints, room repairs...'}),
            'pending_matters': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tasks that must be followed up by the next shift...'}),
        }
