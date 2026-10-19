from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from pms.models import (
    RoomType, Room, Guest, Reservation, Stay, Invoice, InvoiceItem,
    Payment, GuestRequest, ShiftHandover, UserProfile, ActivityLog
)


class Command(BaseCommand):
    help = "Seeds database with initial hotel front office demo data (staff, rooms, guests, bookings, stays, invoices)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Hotel PMS Front Office Data..."))

        # 1. Staff Accounts
        gsa_user, created = User.objects.get_or_create(
            username="gsa",
            defaults={"first_name": "Alex", "last_name": "Rivera", "email": "gsa@grandhorizon.hotel"}
        )
        if created:
            gsa_user.set_password("gsa123")
            gsa_user.save()
        UserProfile.objects.update_or_create(
            user=gsa_user,
            defaults={"role": "GSA", "phone": "+1 (555) 234-5678", "employee_id": "GSA-104"}
        )

        manager_user, created = User.objects.get_or_create(
            username="manager",
            defaults={"first_name": "Sophia", "last_name": "Vance", "email": "manager@grandhorizon.hotel", "is_staff": True}
        )
        if created:
            manager_user.set_password("manager123")
            manager_user.save()
        UserProfile.objects.update_or_create(
            user=manager_user,
            defaults={"role": "MANAGER", "phone": "+1 (555) 890-1234", "employee_id": "MGR-002"}
        )

        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={"first_name": "System", "last_name": "Admin", "email": "admin@grandhorizon.hotel", "is_staff": True, "is_superuser": True}
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
        UserProfile.objects.update_or_create(
            user=admin_user,
            defaults={"role": "ADMIN", "phone": "+1 (555) 000-1111", "employee_id": "ADM-001"}
        )

        # 2. Room Types
        sgl, _ = RoomType.objects.get_or_create(
            code="SGL",
            defaults={
                "name": "Standard Single",
                "base_rate": Decimal("85.00"),
                "max_occupancy": 1,
                "description": "Cozy room with plush single bed, work desk, and private bath.",
                "amenities": "High-Speed Wi-Fi, 42-inch Smart TV, Work Desk, Air Conditioning, Shower"
            }
        )

        dlx, _ = RoomType.objects.get_or_create(
            code="DLX",
            defaults={
                "name": "Deluxe King",
                "base_rate": Decimal("140.00"),
                "max_occupancy": 2,
                "description": "Spacious king bedroom with city skyline view and premium bathroom.",
                "amenities": "King Size Bed, Mini Bar, City View, Espresso Maker, Bathtub, Safe"
            }
        )

        dbl, _ = RoomType.objects.get_or_create(
            code="DBL",
            defaults={
                "name": "Double Queen",
                "base_rate": Decimal("175.00"),
                "max_occupancy": 4,
                "description": "Ideal for families or traveling colleagues with two queen beds.",
                "amenities": "2 Queen Beds, Sitting Area, Mini Fridge, Microwave, Wi-Fi, Shower/Tub"
            }
        )

        ste, _ = RoomType.objects.get_or_create(
            code="STE",
            defaults={
                "name": "Executive Suite",
                "base_rate": Decimal("260.00"),
                "max_occupancy": 3,
                "description": "Luxury suite with separate living parlor, master king bedroom, and panoramic balcony.",
                "amenities": "Private Balcony, Living Room, Jacuzzi Tub, Butler Service, Nespresso, Walk-in Closet"
            }
        )

        # 3. Rooms
        room_data = [
            # Floor 1
            {"number": "101", "floor": 1, "type": sgl, "status": "AVAILABLE", "clean": "CLEAN", "notes": "Near garden entrance"},
            {"number": "102", "floor": 1, "type": sgl, "status": "OCCUPIED", "clean": "DIRTY", "notes": "Guest in-house"},
            {"number": "103", "floor": 1, "type": dlx, "status": "AVAILABLE", "clean": "CLEAN", "notes": "Courtyard view"},
            {"number": "104", "floor": 1, "type": dlx, "status": "CLEANING", "clean": "DIRTY", "notes": "Departed 10:30 AM, awaiting housekeeping clearance"},
            {"number": "105", "floor": 1, "type": dbl, "status": "RESERVED", "clean": "CLEAN", "notes": "Reserved for today arrival"},
            # Floor 2
            {"number": "201", "floor": 2, "type": dlx, "status": "OCCUPIED", "clean": "DIRTY", "notes": "Departure scheduled for today noon"},
            {"number": "202", "floor": 2, "type": dlx, "status": "AVAILABLE", "clean": "CLEAN", "notes": "Quiet corner unit"},
            {"number": "203", "floor": 2, "type": dbl, "status": "OCCUPIED", "clean": "DIRTY", "notes": "Walk-in guest family"},
            {"number": "204", "floor": 2, "type": dbl, "status": "AVAILABLE", "clean": "CLEAN", "notes": "Adjacent to elevator"},
            {"number": "205", "floor": 2, "type": ste, "status": "OUT_OF_ORDER", "clean": "DIRTY", "notes": "AC repair in progress by engineering"},
            # Floor 3
            {"number": "301", "floor": 3, "type": ste, "status": "AVAILABLE", "clean": "CLEAN", "notes": "Executive floor access"},
            {"number": "302", "floor": 3, "type": ste, "status": "OCCUPIED", "clean": "DIRTY", "notes": "VIP Corporate guest"},
            {"number": "303", "floor": 3, "type": dlx, "status": "AVAILABLE", "clean": "CLEAN", "notes": "Skyline view"},
            {"number": "304", "floor": 3, "type": dbl, "status": "AVAILABLE", "clean": "CLEAN", "notes": "Double queen quiet side"},
        ]

        rooms = {}
        for rd in room_data:
            r, _ = Room.objects.update_or_create(
                room_number=rd["number"],
                defaults={
                    "floor": rd["floor"],
                    "room_type": rd["type"],
                    "status": rd["status"],
                    "clean_status": rd["clean"],
                    "notes": rd["notes"],
                }
            )
            rooms[rd["number"]] = r

        # 4. Guests
        g1, _ = Guest.objects.update_or_create(
            phone="+1 (555) 789-0123",
            defaults={
                "first_name": "Elena",
                "last_name": "Rostova",
                "email": "elena.rostova@example.com",
                "nationality": "France",
                "id_type": "PASSPORT",
                "id_number": "FR98823104",
                "address": "14 Rue de Rivoli, Paris, France",
                "preferences": "Feather-free pillows, high floor preferred",
                "remarks": "VIP Loyalty Member (Gold Tier)"
            }
        )

        g2, _ = Guest.objects.update_or_create(
            phone="+1 (555) 345-6789",
            defaults={
                "first_name": "Carlos",
                "last_name": "Mendez",
                "email": "cmendez@globaltech.io",
                "nationality": "Mexico",
                "id_type": "PASSPORT",
                "id_number": "MX44510298",
                "address": "Av. Insurgentes Sur 1602, Mexico City",
                "preferences": "Late check-out request, quiet room",
                "remarks": "Attending local conference"
            }
        )

        g3, _ = Guest.objects.update_or_create(
            phone="+1 (555) 901-2345",
            defaults={
                "first_name": "David",
                "last_name": "Miller",
                "email": "david.miller@workmail.com",
                "nationality": "United States",
                "id_type": "DRIVING_LICENSE",
                "id_number": "DL-CA-9938201",
                "address": "742 Evergreen Terrace, Springfield, OR",
                "preferences": "Twin crib requested",
                "remarks": "Family vacation with 2 children"
            }
        )

        g4, _ = Guest.objects.update_or_create(
            phone="+1 (555) 678-9012",
            defaults={
                "first_name": "Sarah",
                "last_name": "Jenkins",
                "email": "sarah.j@apexventures.com",
                "nationality": "United Kingdom",
                "id_type": "PASSPORT",
                "id_number": "GB77192033",
                "address": "221B Baker St, London, UK",
                "preferences": "Sparkling water daily, newspaper in morning",
                "remarks": "Managing Director at Apex Ventures"
            }
        )

        g5, _ = Guest.objects.update_or_create(
            phone="+1 (555) 432-1098",
            defaults={
                "first_name": "Liam",
                "last_name": "Johnson",
                "email": "liam.johnson@example.com",
                "nationality": "Canada",
                "id_type": "NATIONAL_ID",
                "id_number": "CAN-ID-556102",
                "address": "88 King St West, Toronto, ON",
                "preferences": "Early breakfast box on departure day",
                "remarks": "Frequent business traveler"
            }
        )

        g6, _ = Guest.objects.update_or_create(
            phone="+1 (555) 876-5432",
            defaults={
                "first_name": "Priya",
                "last_name": "Sharma",
                "email": "priya.sharma@innovate.org",
                "nationality": "India",
                "id_type": "PASSPORT",
                "id_number": "IND-Z8829103",
                "address": "12 Richmond Road, Bangalore, India",
                "preferences": "Extra hanger set, non-smoking strictly",
                "remarks": "Reserved for today arrival"
            }
        )

        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        tomorrow = today + timedelta(days=1)
        two_days_later = today + timedelta(days=2)
        three_days_later = today + timedelta(days=3)

        # 5. Reservations
        # Today's Arrival: Priya Sharma (Reserved Room 105)
        res_today, _ = Reservation.objects.update_or_create(
            guest=g6,
            check_in_date=today,
            defaults={
                "room_type": dbl,
                "assigned_room": rooms["105"],
                "check_out_date": two_days_later,
                "num_adults": 2,
                "num_children": 0,
                "rate_per_night": Decimal("175.00"),
                "special_requests": "Arriving around 4 PM. Request ground floor room.",
                "status": "CONFIRMED",
                "created_by": gsa_user,
            }
        )

        # Tomorrow's Arrival: New Booking
        res_tomorrow, _ = Reservation.objects.update_or_create(
            guest=g5,
            check_in_date=tomorrow,
            defaults={
                "room_type": dlx,
                "assigned_room": rooms["103"],
                "check_out_date": three_days_later,
                "num_adults": 1,
                "num_children": 0,
                "rate_per_night": Decimal("140.00"),
                "special_requests": "Late arrival after 8:00 PM.",
                "status": "CONFIRMED",
                "created_by": gsa_user,
            }
        )

        # In-House Stay 1: Room 102 (Elena Rostova, Single)
        res_102, _ = Reservation.objects.update_or_create(
            guest=g1,
            check_in_date=yesterday,
            defaults={
                "room_type": sgl,
                "assigned_room": rooms["102"],
                "check_out_date": two_days_later,
                "num_adults": 1,
                "num_children": 0,
                "rate_per_night": Decimal("85.00"),
                "status": "CHECKED_IN",
                "created_by": gsa_user,
            }
        )
        stay_102, _ = Stay.objects.update_or_create(
            room=rooms["102"],
            status="ACTIVE",
            defaults={
                "reservation": res_102,
                "guest": g1,
                "check_in_time": timezone.now() - timedelta(days=1),
                "expected_check_out": two_days_later,
                "num_occupants": 1,
                "rate_per_night": Decimal("85.00"),
                "checked_in_by": gsa_user,
                "notes": "Checked in at front desk yesterday afternoon."
            }
        )
        inv_102, _ = Invoice.objects.get_or_create(
            stay=stay_102,
            defaults={"guest": g1}
        )
        # Charges for 102
        if not inv_102.items.exists():
            InvoiceItem.objects.create(
                invoice=inv_102, category="ROOM", description="Room Charge - Night 1 (Room 102)",
                quantity=1, unit_price=Decimal("85.00"), date_charged=yesterday
            )
            InvoiceItem.objects.create(
                invoice=inv_102, category="FOOD_BEVERAGE", description="Room Service - Club Sandwich & Sparkling Water",
                quantity=1, unit_price=Decimal("28.00"), date_charged=yesterday
            )
            # Partial advance payment
            Payment.objects.create(
                invoice=inv_102, amount=Decimal("100.00"), payment_method="CREDIT_CARD",
                transaction_id="AUTH-992144", notes="Deposit at check-in", recorded_by=gsa_user
            )

        # In-House Stay 2: Room 201 (Carlos Mendez, Deluxe King - Departure Due Today!)
        res_201, _ = Reservation.objects.update_or_create(
            guest=g2,
            check_in_date=two_days_ago,
            defaults={
                "room_type": dlx,
                "assigned_room": rooms["201"],
                "check_out_date": today,
                "num_adults": 1,
                "num_children": 0,
                "rate_per_night": Decimal("140.00"),
                "status": "CHECKED_IN",
                "created_by": gsa_user,
            }
        )
        stay_201, _ = Stay.objects.update_or_create(
            room=rooms["201"],
            status="ACTIVE",
            defaults={
                "reservation": res_201,
                "guest": g2,
                "check_in_time": timezone.now() - timedelta(days=2),
                "expected_check_out": today,
                "num_occupants": 1,
                "rate_per_night": Decimal("140.00"),
                "checked_in_by": gsa_user,
                "notes": "Scheduled check-out today at 12:00 PM."
            }
        )
        inv_201, _ = Invoice.objects.get_or_create(
            stay=stay_201,
            defaults={"guest": g2}
        )
        if not inv_201.items.exists():
            InvoiceItem.objects.create(
                invoice=inv_201, category="ROOM", description="Room Charge - 2 Nights (Room 201)",
                quantity=2, unit_price=Decimal("140.00"), date_charged=two_days_ago
            )
            InvoiceItem.objects.create(
                invoice=inv_201, category="LAUNDRY", description="Express Laundry - 2 Suits & 3 Shirts",
                quantity=1, unit_price=Decimal("35.00"), date_charged=yesterday
            )
            # Unpaid invoice for demonstration of front desk collection workflow

        # In-House Stay 3: Room 203 (David Miller - Walk In, Double Queen)
        stay_203, _ = Stay.objects.update_or_create(
            room=rooms["203"],
            status="ACTIVE",
            defaults={
                "guest": g3,
                "check_in_time": timezone.now() - timedelta(hours=3),
                "expected_check_out": three_days_later,
                "num_occupants": 3,
                "rate_per_night": Decimal("175.00"),
                "checked_in_by": gsa_user,
                "notes": "Walk-in registration. Family with 2 kids."
            }
        )
        inv_203, _ = Invoice.objects.get_or_create(
            stay=stay_203,
            defaults={"guest": g3}
        )
        if not inv_203.items.exists():
            InvoiceItem.objects.create(
                invoice=inv_203, category="ROOM", description="Room Charge - 3 Nights (Room 203)",
                quantity=3, unit_price=Decimal("175.00"), date_charged=today
            )
            InvoiceItem.objects.create(
                invoice=inv_203, category="SERVICE", description="Baby Crib Extra Amenity Setup",
                quantity=1, unit_price=Decimal("20.00"), date_charged=today
            )
            # Fully paid upfront
            Payment.objects.create(
                invoice=inv_203, amount=inv_203.total_amount, payment_method="DEBIT_CARD",
                transaction_id="TXN-DEBIT-8831", notes="Prepaid entire stay at walk-in check-in", recorded_by=gsa_user
            )

        # In-House Stay 4: Room 302 (Sarah Jenkins, Executive Suite VIP)
        stay_302, _ = Stay.objects.update_or_create(
            room=rooms["302"],
            status="ACTIVE",
            defaults={
                "guest": g4,
                "check_in_time": timezone.now() - timedelta(days=1),
                "expected_check_out": tomorrow,
                "num_occupants": 1,
                "rate_per_night": Decimal("260.00"),
                "checked_in_by": manager_user,
                "notes": "VIP corporate account."
            }
        )
        inv_302, _ = Invoice.objects.get_or_create(
            stay=stay_302,
            defaults={"guest": g4}
        )
        if not inv_302.items.exists():
            InvoiceItem.objects.create(
                invoice=inv_302, category="ROOM", description="Executive Suite Rate - 2 Nights",
                quantity=2, unit_price=Decimal("260.00"), date_charged=yesterday
            )
            InvoiceItem.objects.create(
                invoice=inv_302, category="MINIBAR", description="Premium Champagne & Chocolates",
                quantity=1, unit_price=Decimal("85.00"), date_charged=yesterday
            )

        # Past Stay: Room 104 (Liam Johnson - Checked Out earlier today, room in CLEANING)
        stay_104, _ = Stay.objects.update_or_create(
            room=rooms["104"],
            status="CHECKED_OUT",
            defaults={
                "guest": g5,
                "check_in_time": timezone.now() - timedelta(days=2),
                "expected_check_out": today,
                "actual_check_out_time": timezone.now() - timedelta(hours=4),
                "num_occupants": 1,
                "rate_per_night": Decimal("140.00"),
                "checked_in_by": gsa_user,
                "checked_out_by": gsa_user,
                "notes": "Guest checked out this morning at 10:30 AM."
            }
        )
        inv_104, _ = Invoice.objects.get_or_create(
            stay=stay_104,
            defaults={"guest": g5}
        )
        if not inv_104.items.exists():
            InvoiceItem.objects.create(
                invoice=inv_104, category="ROOM", description="Room Charge - 2 Nights (Room 104)",
                quantity=2, unit_price=Decimal("140.00"), date_charged=two_days_ago
            )
            # Paid in full at checkout
            Payment.objects.create(
                invoice=inv_104, amount=inv_104.total_amount, payment_method="CASH",
                transaction_id="CASH-REC-104", notes="Settled in full at front desk cash drawer", recorded_by=gsa_user
            )

        # 6. Guest Requests
        GuestRequest.objects.get_or_create(
            room=rooms["102"],
            guest=g1,
            request_text="Extra hypoallergenic pillows and two bottles of mineral water.",
            defaults={"priority": "MEDIUM", "status": "PENDING", "stay": stay_102}
        )
        GuestRequest.objects.get_or_create(
            room=rooms["201"],
            guest=g2,
            request_text="Luggage porter assistance at 11:45 AM for check-out.",
            defaults={"priority": "HIGH", "status": "IN_PROGRESS", "stay": stay_201}
        )
        GuestRequest.objects.get_or_create(
            room=rooms["302"],
            guest=g4,
            request_text="Morning Financial Times newspaper and extra bathrobes.",
            defaults={
                "priority": "LOW",
                "status": "COMPLETED",
                "stay": stay_302,
                "completed_at": timezone.now() - timedelta(hours=2)
            }
        )

        # 7. Shift Handover
        ShiftHandover.objects.get_or_create(
            shift="MORNING",
            date=today,
            defaults={
                "notes": "Morning operations ran smoothly. Room 104 checked out at 10:30 AM, awaiting cleaning clearance. Room 205 AC maintenance technician scheduled for 2:00 PM.",
                "pending_matters": "1. Collect balance on Room 201 check-out.\n2. Room 105 arrival (Priya Sharma) arriving ~4:00 PM.\n3. Verify housekeeping clears Room 104 before 3:00 PM.",
                "cash_in_drawer": Decimal("450.00"),
                "handed_over_by": gsa_user,
            }
        )

        # 8. Activity Logs
        ActivityLog.objects.create(
            user=gsa_user,
            action="Check-in",
            details="Registered walk-in guest David Miller into Room 203"
        )
        ActivityLog.objects.create(
            user=gsa_user,
            action="Check-out",
            details="Completed check-out for Liam Johnson (Room 104). Room status set to CLEANING."
        )
        ActivityLog.objects.create(
            user=manager_user,
            action="Maintenance",
            details="Marked Room 205 OUT OF ORDER for AC repair"
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded Grand Horizon Hotel PMS sample data!"))
        self.stdout.write("Front Desk Staff: username 'gsa', password 'gsa123'")
        self.stdout.write("Manager Staff: username 'manager', password 'manager123'")
        self.stdout.write("Admin: username 'admin', password 'admin123'")
