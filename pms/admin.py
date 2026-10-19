from django.contrib import admin
from .models import (
    RoomType, Room, Guest, Reservation, Stay,
    Invoice, InvoiceItem, Payment, GuestRequest, ShiftHandover,
    UserProfile, ActivityLog
)


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'base_rate', 'max_occupancy', 'total_rooms_count')
    search_fields = ('name', 'code')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'floor', 'room_type', 'status', 'clean_status', 'effective_rate')
    list_filter = ('status', 'clean_status', 'floor', 'room_type')
    search_fields = ('room_number',)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'email', 'nationality', 'id_type', 'created_at')
    search_fields = ('first_name', 'last_name', 'phone', 'email', 'id_number')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('booking_reference', 'guest', 'room_type', 'assigned_room', 'check_in_date', 'check_out_date', 'status')
    list_filter = ('status', 'room_type', 'check_in_date')
    search_fields = ('booking_reference', 'guest__first_name', 'guest__last_name', 'guest__phone')


@admin.register(Stay)
class StayAdmin(admin.ModelAdmin):
    list_display = ('guest', 'room', 'check_in_time', 'expected_check_out', 'status', 'rate_per_night')
    list_filter = ('status', 'room__room_type', 'expected_check_out')
    search_fields = ('guest__first_name', 'guest__last_name', 'room__room_number')


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'guest', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('invoice_number', 'guest__first_name', 'guest__last_name')
    inlines = [InvoiceItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'payment_method', 'transaction_id', 'payment_date', 'recorded_by')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('invoice__invoice_number', 'transaction_id')


@admin.register(GuestRequest)
class GuestRequestAdmin(admin.ModelAdmin):
    list_display = ('room', 'guest', 'priority', 'status', 'created_at')
    list_filter = ('status', 'priority', 'room')
    search_fields = ('request_text', 'room__room_number', 'guest__first_name')


@admin.register(ShiftHandover)
class ShiftHandoverAdmin(admin.ModelAdmin):
    list_display = ('shift', 'date', 'cash_in_drawer', 'handed_over_by', 'created_at')
    list_filter = ('shift', 'date')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'employee_id')
    list_filter = ('role',)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'details')
    list_filter = ('action', 'timestamp')
    search_fields = ('details', 'action', 'user__username')
