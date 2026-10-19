from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from pms.models import (
    RoomType, Room, Guest, Reservation, Stay, Invoice, InvoiceItem,
    Payment, GuestRequest, ShiftHandover, UserProfile
)


class HotelPMSTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.gsa_user = User.objects.create_user(
            username='gsa_test', password='password123', first_name='Alex', last_name='GSA'
        )
        UserProfile.objects.create(user=self.gsa_user, role='GSA', employee_id='GSA-01')

        self.mgr_user = User.objects.create_user(
            username='mgr_test', password='password123', first_name='Sophia', last_name='Manager', is_staff=True
        )
        UserProfile.objects.create(user=self.mgr_user, role='MANAGER', employee_id='MGR-01')

        # Room Types
        self.sgl_type = RoomType.objects.create(
            name='Single Room', code='SGL', base_rate=Decimal('100.00'), max_occupancy=1
        )
        self.dlx_type = RoomType.objects.create(
            name='Deluxe King', code='DLX', base_rate=Decimal('150.00'), max_occupancy=2
        )

        # Rooms
        self.room_101 = Room.objects.create(
            room_number='101', floor=1, room_type=self.sgl_type, status='AVAILABLE', clean_status='CLEAN'
        )
        self.room_102 = Room.objects.create(
            room_number='102', floor=1, room_type=self.dlx_type, status='AVAILABLE', clean_status='CLEAN'
        )

        # Guest
        self.guest = Guest.objects.create(
            first_name='John', last_name='Doe', phone='+1-555-0101', email='john@example.com',
            nationality='US', id_type='PASSPORT', id_number='P12345678'
        )

        self.today = date.today()
        self.tomorrow = self.today + timedelta(days=1)
        self.day_after = self.today + timedelta(days=2)


class RoomAvailabilityAndOverlapTests(HotelPMSTestCase):
    def test_room_properties(self):
        self.assertTrue(self.room_101.is_vacant)
        self.assertTrue(self.room_101.can_check_in)
        self.assertEqual(self.room_101.effective_rate, Decimal('100.00'))

        # Set custom rate
        self.room_101.current_rate = Decimal('115.00')
        self.assertEqual(self.room_101.effective_rate, Decimal('115.00'))

    def test_overlapping_reservation_prevention(self):
        # Reservation 1: today to day_after on room 101
        res1 = Reservation.objects.create(
            guest=self.guest, room_type=self.sgl_type, assigned_room=self.room_101,
            check_in_date=self.today, check_out_date=self.day_after,
            rate_per_night=Decimal('100.00'), status='CONFIRMED'
        )
        self.assertTrue(res1.booking_reference.startswith('RES-'))

        # Reservation 2: overlapping dates (tomorrow to day_after + 1) on same room
        res2 = Reservation(
            guest=self.guest, room_type=self.sgl_type, assigned_room=self.room_101,
            check_in_date=self.tomorrow, check_out_date=self.today + timedelta(days=3),
            rate_per_night=Decimal('100.00'), status='CONFIRMED'
        )
        # Should raise ValidationError in clean()
        with self.assertRaises(ValidationError):
            res2.clean()

    def test_consecutive_non_overlapping_reservations_allowed(self):
        # res1: today to tomorrow
        Reservation.objects.create(
            guest=self.guest, room_type=self.sgl_type, assigned_room=self.room_101,
            check_in_date=self.today, check_out_date=self.tomorrow,
            rate_per_night=Decimal('100.00'), status='CONFIRMED'
        )

        # res2: tomorrow to day_after (check-in exactly when res1 checks out)
        res2 = Reservation(
            guest=self.guest, room_type=self.sgl_type, assigned_room=self.room_101,
            check_in_date=self.tomorrow, check_out_date=self.day_after,
            rate_per_night=Decimal('100.00'), status='CONFIRMED'
        )
        # Should pass validation cleanly
        try:
            res2.clean()
        except ValidationError:
            self.fail("Consecutive reservations should be permitted without overlap error.")

    def test_invalid_dates_rejected(self):
        # Check-out before or on check-in
        res = Reservation(
            guest=self.guest, room_type=self.sgl_type,
            check_in_date=self.tomorrow, check_out_date=self.today,
            rate_per_night=Decimal('100.00')
        )
        with self.assertRaises(ValidationError):
            res.clean()


class CheckInWorkflowTests(HotelPMSTestCase):
    def test_check_in_from_reservation(self):
        self.client.login(username='gsa_test', password='password123')

        res = Reservation.objects.create(
            guest=self.guest, room_type=self.sgl_type, assigned_room=self.room_101,
            check_in_date=self.today, check_out_date=self.tomorrow,
            rate_per_night=Decimal('100.00'), status='CONFIRMED'
        )

        response = self.client.post(reverse('check_in_reservation', args=[res.pk]), {
            'room': self.room_101.pk,
            'num_occupants': 1,
            'notes': 'All luggage delivered to room.'
        })

        # Check redirect to invoice detail
        self.assertEqual(response.status_code, 302)

        # Verify Room state updated
        self.room_101.refresh_from_db()
        self.assertEqual(self.room_101.status, 'OCCUPIED')
        self.assertEqual(self.room_101.clean_status, 'DIRTY')

        # Verify Reservation state updated
        res.refresh_from_db()
        self.assertEqual(res.status, 'CHECKED_IN')

        # Verify Stay created
        stay = Stay.objects.get(reservation=res)
        self.assertEqual(stay.status, 'ACTIVE')
        self.assertEqual(stay.room, self.room_101)

        # Verify initial Invoice and room charge item created
        invoice = stay.invoice
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.items.count(), 1)
        item = invoice.items.first()
        self.assertEqual(item.category, 'ROOM')
        self.assertEqual(item.amount, Decimal('100.00'))
        # Subtotal: $100, Tax 10%: $10, Total: $110
        self.assertEqual(invoice.total_amount, Decimal('110.00'))

    def test_walk_in_check_in(self):
        self.client.login(username='gsa_test', password='password123')

        response = self.client.post(reverse('walk_in_check_in'), {
            'first_name': 'WalkIn',
            'last_name': 'Customer',
            'phone': '+1-555-9988',
            'email': 'walkin@example.com',
            'nationality': 'Domestic',
            'id_type': 'DRIVING_LICENSE',
            'id_number': 'DL-88229',
            'room': self.room_102.pk,
            'check_out_date': self.day_after.isoformat(),
            'num_occupants': 2,
            'custom_rate': '150.00',
            'notes': 'Walk-in registration'
        })
        self.assertEqual(response.status_code, 302)

        self.room_102.refresh_from_db()
        self.assertEqual(self.room_102.status, 'OCCUPIED')
        self.assertEqual(self.room_102.clean_status, 'DIRTY')

        guest = Guest.objects.get(phone='+1-555-9988')
        self.assertEqual(guest.first_name, 'WalkIn')
        stay = Stay.objects.get(room=self.room_102, status='ACTIVE')
        self.assertEqual(stay.guest, guest)
        self.assertEqual(stay.nights_count, 2)


class CheckOutWorkflowTests(HotelPMSTestCase):
    def setUp(self):
        super().setUp()
        # Create an active stay in room 101
        self.room_101.status = 'OCCUPIED'
        self.room_101.clean_status = 'DIRTY'
        self.room_101.save()

        self.stay = Stay.objects.create(
            guest=self.guest, room=self.room_101, check_in_time=timezone.now() - timedelta(days=2),
            expected_check_out=self.today, num_occupants=1, rate_per_night=Decimal('100.00'),
            status='ACTIVE'
        )
        self.invoice = Invoice.objects.create(stay=self.stay, guest=self.guest, tax_rate_percent=Decimal('10.00'))
        InvoiceItem.objects.create(
            invoice=self.invoice, category='ROOM', description='2 Nights Room Charge',
            quantity=2, unit_price=Decimal('100.00'), date_charged=self.today - timedelta(days=2)
        )
        # Total with 10% tax = 200 + 20 = $220.00

    def test_check_out_and_room_cleaning_status(self):
        self.client.login(username='gsa_test', password='password123')

        # Check initial balance
        self.assertEqual(self.invoice.balance_due, Decimal('220.00'))

        # Post check-out with full settlement
        response = self.client.post(reverse('check_out', args=[self.stay.pk]), {
            'amount_paid': '220.00',
            'payment_method': 'CREDIT_CARD',
            'transaction_id': 'TXN-SETTLE-001',
            'discount_amount': '0.00',
            'notes': 'Guest settled in full via Visa'
        })
        self.assertEqual(response.status_code, 302)

        # Verify stay marked as checked out
        self.stay.refresh_from_db()
        self.assertEqual(self.stay.status, 'CHECKED_OUT')
        self.assertIsNotNone(self.stay.actual_check_out_time)

        # Verify payment recorded and invoice marked PAID
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'PAID')
        self.assertEqual(self.invoice.balance_due, Decimal('0.00'))
        self.assertEqual(self.invoice.payments.count(), 1)

        # CRITICAL TEST: Room must NOT be AVAILABLE! Must be CLEANING and DIRTY!
        self.room_101.refresh_from_db()
        self.assertEqual(self.room_101.status, 'CLEANING')
        self.assertEqual(self.room_101.clean_status, 'DIRTY')
        self.assertFalse(self.room_101.can_check_in)

    def test_housekeeping_clearance_toggle(self):
        """Room goes from CLEANING -> AVAILABLE only when marked clean."""
        self.client.login(username='gsa_test', password='password123')

        self.room_101.status = 'CLEANING'
        self.room_101.clean_status = 'DIRTY'
        self.room_101.save()

        response = self.client.get(reverse('room_clean_toggle', args=[self.room_101.pk]))
        self.assertEqual(response.status_code, 302)

        self.room_101.refresh_from_db()
        self.assertEqual(self.room_101.status, 'AVAILABLE')
        self.assertEqual(self.room_101.clean_status, 'CLEAN')
        self.assertTrue(self.room_101.can_check_in)


class BillingAndInvoiceTests(HotelPMSTestCase):
    def test_invoice_recalculation_and_payments(self):
        stay = Stay.objects.create(
            guest=self.guest, room=self.room_101, check_in_time=timezone.now(),
            expected_check_out=self.tomorrow, num_occupants=1, rate_per_night=Decimal('100.00')
        )
        invoice = Invoice.objects.create(stay=stay, guest=self.guest, tax_rate_percent=Decimal('10.00'))

        # Add room charge: $100
        InvoiceItem.objects.create(
            invoice=invoice, category='ROOM', description='Room Night 1', quantity=1, unit_price=Decimal('100.00')
        )
        # Add minibar: $20
        InvoiceItem.objects.create(
            invoice=invoice, category='MINIBAR', description='Snacks & Drinks', quantity=1, unit_price=Decimal('20.00')
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal('120.00'))
        self.assertEqual(invoice.tax_amount, Decimal('12.00'))
        self.assertEqual(invoice.total_amount, Decimal('132.00'))
        self.assertEqual(invoice.status, 'UNPAID')

        # Add partial payment: $50
        Payment.objects.create(
            invoice=invoice, amount=Decimal('50.00'), payment_method='CASH', recorded_by=self.gsa_user
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PARTIAL')
        self.assertEqual(invoice.balance_due, Decimal('82.00'))

        # Add remaining payment: $82
        Payment.objects.create(
            invoice=invoice, amount=Decimal('82.00'), payment_method='CREDIT_CARD', recorded_by=self.gsa_user
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PAID')
        self.assertEqual(invoice.balance_due, Decimal('0.00'))


class ReportsAndCSVTests(HotelPMSTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='gsa_test', password='password123')

    def test_reports_hub_view(self):
        response = self.client.get(reverse('reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hotel Reports & Analytics')

    def test_revenue_csv_export(self):
        response = self.client.get(reverse('export_revenue_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="revenue_report_', response['Content-Disposition'])

    def test_arrivals_and_departures_csv(self):
        r_arr = self.client.get(reverse('export_arrivals_csv'))
        self.assertEqual(r_arr.status_code, 200)
        self.assertEqual(r_arr['Content-Type'], 'text/csv')

        r_dep = self.client.get(reverse('export_departures_csv'))
        self.assertEqual(r_dep.status_code, 200)
        self.assertEqual(r_dep['Content-Type'], 'text/csv')


class FrontDeskOperationsTests(HotelPMSTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='gsa_test', password='password123')

    def test_dashboard_metrics_from_db(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Front Office Dashboard')
        self.assertContains(response, 'Available Rooms')
        self.assertContains(response, 'Occupied')

    def test_room_matrix_rack(self):
        response = self.client.get(reverse('room_matrix'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '101')
        self.assertContains(response, '102')

    def test_shift_handover_creation(self):
        response = self.client.post(reverse('shift_handover_list'), {
            'shift': 'MORNING',
            'date': self.today.isoformat(),
            'notes': 'Normal morning shift. All check-ins greeted.',
            'pending_matters': 'Follow up on Room 102 pillows.',
            'cash_in_drawer': '350.00'
        })
        self.assertEqual(response.status_code, 302)
        handover = ShiftHandover.objects.get(shift='MORNING', date=self.today)
        self.assertEqual(handover.cash_in_drawer, Decimal('350.00'))
        self.assertEqual(handover.handed_over_by, self.gsa_user)

    def test_guest_request_status_update(self):
        req = GuestRequest.objects.create(
            room=self.room_101, guest=self.guest, request_text='Need extra towels',
            priority='HIGH', status='PENDING'
        )
        response = self.client.post(reverse('guest_request_update_status', args=[req.pk]), {
            'status': 'COMPLETED'
        })
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'COMPLETED')
        self.assertIsNotNone(req.completed_at)


class SecurityAndAccessTests(HotelPMSTestCase):
    def test_unauthenticated_user_redirected(self):
        # Without logging in
        client = Client()
        response = client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_masked_guest_id_protection(self):
        guest = Guest.objects.create(
            first_name='Secret', last_name='Agent', phone='+1-555-007',
            id_type='PASSPORT', id_number='SECRET987654321'
        )
        self.assertEqual(guest.masked_id, '•••• 4321')
