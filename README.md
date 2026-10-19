# Grand Horizon Hotel - Front Office PMS (Property Management System)

A simple, practical, and fully functional **Hotel Property Management System (PMS)** built with **Python**, **Django 6**, **HTML5**, **Bootstrap 5**, and **SQLite**.

Designed specifically for **Guest Service Associates (GSA)** and **Front Desk Staff** working hotel shifts to manage guest check-ins, check-outs, room inventory, reservations, billing folios, and shift handovers with high speed and zero corporate bloat.

---

## 🏨 System Overview & Key Features

### 1. Front Desk Dashboard
- **Live Database Figures:**
  - **Total Rooms**, **Available Rooms**, **Occupied Rooms**, **Reserved Rooms**, **Housekeeping/Cleaning Rooms**, and **Out of Order Rooms**.
  - **Real-Time Occupancy Rate (%)** dynamically computed from database rooms.
  - **Today's Arrivals Count:** Confirmed reservations arriving today.
  - **Today's Departures Count:** Active in-house guests scheduled to depart today.
  - **In-House Guest Count:** Currently staying guests.
  - **Pending Cashier Balance:** Total outstanding folio balances across all active stays.
- **Shift Handover Alert Widget:** Quick glance at unresolved matters left by the previous shift.
- **Visual Room Matrix Snapshot:** High-level status by floor with 1-click shortcuts.

---

### 2. Room Management & Visual Room Rack
- **Visual Room Rack Matrix (`/rooms/matrix/`):**
  - Floor-by-floor visual room cards with color-coded status badges:
    - 🟩 **Available** (Clean & ready for check-in)
    - 🟥 **Occupied** (Guest in-house with stay details)
    - 🟦 **Reserved** (Booked for arrival)
    - 🟨 **Cleaning / Dirty** (Housekeeping needed)
    - ⬜ **Out of Order** (Maintenance)
  - **1-Click Actions:** Fast check-in from available rooms, quick check-out links on occupied rooms, and 1-click **"Mark Clean"** housekeeping clearance.
- **Room Types & Rates (`/rooms/types/`):**
  - Standard Single (`SGL`), Deluxe King (`DLX`), Double Queen (`DBL`), and Executive Suite (`STE`).
  - Configurable base rates, max occupant capacity, and amenity tags.
- **Room Inventory Table (`/rooms/`):** Full searchable table with floor, type, status, and clean status filters.

---

### 3. Guest Management & Privacy Protection
- **Guest Profiles (`/guests/`):**
  - Full Name, Phone, Email, Physical Address, Nationality.
  - ID Document Type (Passport, National ID, Driver's License, Voter ID) and Document Number.
  - Special guest preferences (e.g. *high floor, feather-free pillows, late check-in*).
  - Internal remarks & VIP loyalty status.
- **Data Privacy Protection:** Identification numbers are automatically masked (`•••• 1234`) across operational lists to protect guest privacy from shoulder-surfing.
- **Guest Stay History (`/guests/<id>/`):** View all past and current reservations, rooms occupied, and billing history.

---

### 4. Reservation Management
- **Automatic Reference Generation:** Every reservation automatically receives a unique reference in the format `RES-YYYYMMDD-XXXXXX`.
- **Date & Overlap Validation:**
  - Prevents check-out dates on or before check-in dates.
  - **Overlap Booking Prevention:** The system validates assigned rooms at both model and form levels, preventing double-bookings while allowing same-day turnarounds (check-in on the departure day).
- **Estimated Total:** Automatically calculated based on nights stayed and room rate.
- **Reservation Lifecycle:** `CONFIRMED` $\rightarrow$ `CHECKED_IN` $\rightarrow$ `CHECKED_OUT` (or `CANCELLED` / `NO_SHOW`).

---

### 5. Front Desk Check-In Workflows
- **Advance Reservation Check-In (`/reservations/<id>/checkin/`):**
  1. GSA verifies guest credentials and booking details.
  2. Confirms room availability and clean status.
  3. Assigns room, records actual check-in time and number of occupants.
  4. Automatically changes Reservation status to `CHECKED_IN`.
  5. Automatically sets Room status to `OCCUPIED` and clean status to `DIRTY`.
  6. Automatically opens an active `Stay` record and generates an initial `Invoice` with room night charges.
- **Walk-In Registration & Check-In (`/walk-in/`):**
  - Fast, streamlined 1-step form to register a new guest or find an existing guest by phone, assign an available clean room, enter nights and custom rate, and check them in instantly.

---

### 6. Check-Out Workflow & Room State Machine
- **Front Desk Check-Out (`/stays/<id>/checkout/`):**
  1. Displays nights stayed, room charges, and any additional room service or amenity charges.
  2. Applies 10% standard hotel tax and authorized manager discounts with documented reasons.
  3. Displays all payments already received and shows the **Net Outstanding Balance Due**.
  4. Collects final settlement via Cash, Credit Card, Debit Card, UPI, or Bank Wire.
  5. Records timestamped payment receipt with transaction reference.
  6. Marks `Stay` status as `CHECKED_OUT`.
  7. **Strict Hotel Rule Enforced:** Room status transitions to **`CLEANING` (`DIRTY`)**, **NEVER directly to `AVAILABLE`**.
  8. Redirects to printable guest folio.

---

### 7. Housekeeping Clearance Workflow
- After a room is vacated, it remains in `CLEANING` (`DIRTY`) status and cannot be checked in by GSAs.
- Once housekeeping completes room turnover, front desk or housekeeping staff click **"Mark Clean"** (`/rooms/<id>/clean/`).
- The room status returns to **`AVAILABLE` (`CLEAN`)** and is immediately ready for new arrivals.

---

### 8. Billing, Folio & Payments
- **Itemized Folio (`/invoices/<id>/`):**
  - Room charges (`ROOM`)
  - Food & Beverage / Dining (`FOOD_BEVERAGE`)
  - Laundry Service (`LAUNDRY`)
  - Mini Bar (`MINIBAR`)
  - Airport Transfer / Cab (`TRANSPORT`)
  - Extra Amenities (`SERVICE`)
- **Payment Ledger:** Individual payments recorded with payment method, auth code, timestamp, and GSA user reference.
- **Printable Folio Receipt:** Clean, professional printable guest invoice formatted with CSS `@media print` rules for thermal or A4 printing.

---

### 9. Front Desk Shift Operations
- **Today's Arrivals (`/arrivals/`):** List of confirmed guests arriving today with quick "Check In" button.
- **Today's Departures (`/departures/`):** List of in-house guests due to depart today with remaining balance indicator and 1-click "Check Out" launcher.
- **In-House Guest Roster (`/in-house/`):** Complete manifest of all occupants currently in the hotel.
- **Guest Service Requests (`/requests/`):** Track housekeeping and guest requests (pillows, luggage assistance, repairs) with priorities (*Low*, *Medium*, *High*, *Urgent*) and status (*Pending*, *In Progress*, *Completed*).
- **Shift Handover Logs (`/handovers/`):** Front desk GSAs record shift notes, carry-over pending matters for incoming staff, and reconcile the cash drawer balance.

---

### 10. Reports & CSV Export (`/reports/`)
- **Daily Performance Metrics:** Occupancy %, room breakdown, and arrival/departure totals.
- **Revenue by Payment Method:** Breakdown of collections by Cash, Credit Card, Debit Card, and UPI.
- **1-Click CSV Downloads:**
  - Export Arrivals List (`.csv`)
  - Export Departures List (`.csv`)
  - Export Daily Cashier & Revenue Report (`.csv`)

---

## 🛠 Technology Stack
- **Backend:** Python 3.14+, Django 6.1+
- **Database:** SQLite 3 (ORM with decimal precision, transactions, and foreign key constraints)
- **Frontend:** HTML5, Vanilla CSS, Bootstrap 5.3, Bootstrap Icons
- **Authentication:** Django built-in auth with custom `UserProfile` roles (`GSA`, `MANAGER`, `ADMIN`)

---

## 🚀 Quick Setup & Execution

### 1. Prerequisites & Virtual Environment
Ensure you are in the project folder with the virtual environment activated:
```bash
cd "pms software for gsa"
source ./venv/bin/activate
```

### 2. Database Migrations
Run database migrations to initialize all tables:
```bash
python manage.py migrate
```

### 3. Seed Demo Front Office Data
Populate the database with realistic rooms across 3 floors, room types, active guests, confirmed reservations, in-house stays, and shift handovers:
```bash
python manage.py seed_pms_data
```

### 4. Run the Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Open your browser and navigate to: **`http://127.0.0.1:8000/`**

---

## 🔑 Login Credentials

The seed command creates three pre-configured accounts:

| Role | Username | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Front Desk Staff (GSA)** | `gsa` | `gsa123` | Daily front desk operations: check-in, check-out, room rack, bookings, folios, handovers |
| **Front Office Manager** | `manager` | `manager123` | Room management, rate adjustments, reports, staff audit |
| **System Administrator** | `admin` | `admin123` | Full Django Admin access (`/admin/`) and database administration |

---

## 🧪 Automated Test Suite

A comprehensive test suite of 18 test cases validates all critical hotel business rules:
```bash
python manage.py test pms
```

### Test Coverage Highlights:
- ✅ Room availability and custom rate logic.
- ✅ Overlapping reservation prevention (strict double-booking prevention).
- ✅ Consecutive same-day turnaround bookings allowed.
- ✅ Reservation date validations (check-out after check-in).
- ✅ Reservation check-in workflow (room status $\rightarrow$ `OCCUPIED`/`DIRTY`, stay & invoice created).
- ✅ Walk-in check-in workflow.
- ✅ Check-out workflow (room status transitions to `CLEANING`/`DIRTY`, never `AVAILABLE`).
- ✅ Housekeeping clearance toggle (`CLEANING` $\rightarrow$ `AVAILABLE`).
- ✅ Itemized billing calculations, 10% tax calculation, and partial/full payment tracking.
- ✅ Reports hub and CSV exports (arrivals, departures, revenue).
- ✅ Front desk shift handovers with cash drawer balancing.
- ✅ Guest service requests priority tracking.
- ✅ Data privacy protection with masked ID numbers (`•••• 1234`).
- ✅ Authentication security redirects.

---

## 📁 Project Structure

```text
pms software for gsa/
├── manage.py
├── requirements.txt
├── README.md
├── config/
│   ├── __init__.py
│   ├── settings.py           # Django settings, apps, templates, static
│   ├── urls.py               # Main URL routing (points directly to pms.urls)
│   ├── asgi.py
│   └── wsgi.py
├── pms/                      # Hotel PMS Application
│   ├── __init__.py
│   ├── admin.py              # Django admin registrations & inlines
│   ├── apps.py
│   ├── forms.py              # All front office forms & validations
│   ├── models.py             # 12 Hotel PMS models & business methods
│   ├── urls.py               # 20+ Front office URL routes
│   ├── views.py              # View logic for all front desk workflows
│   ├── tests.py              # 18 Automated unit & integration tests
│   ├── management/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── seed_pms_data.py  # Realistic hotel sample data generator
│   └── migrations/
│       ├── 0001_initial.py
│       └── __init__.py
├── static/
│   └── css/
│       └── style.css         # Custom hotel styling, room rack cards, print folio
└── templates/
    ├── base.html             # Grand Horizon sidebar navigation & topbar
    ├── registration/
    │   └── login.html        # Front desk staff login with demo credentials
    └── pms/
        ├── dashboard.html             # Front office dashboard
        ├── room_matrix.html           # Visual Room Rack matrix by floor
        ├── room_list.html             # Rooms table with filters
        ├── room_form.html             # Add/Edit room
        ├── room_type_list.html        # Room types & rates
        ├── room_type_form.html        # Edit room type
        ├── guest_list.html            # Guest directory
        ├── guest_form.html            # Register guest
        ├── guest_detail.html          # Guest stay history & profile
        ├── reservation_list.html      # Reservations roster
        ├── reservation_form.html      # Create reservation
        ├── reservation_detail.html    # Reservation summary
        ├── reservation_confirm_cancel.html
        ├── arrivals_list.html         # Today's arrivals
        ├── departures_list.html       # Today's departures
        ├── in_house_list.html         # In-house guest roster
        ├── check_in_reservation.html  # Reservation check-in form
        ├── walk_in_check_in.html      # Fast walk-in check-in
        ├── check_out.html             # Check-out & payment settlement
        ├── invoice_detail.html        # Printable folio & charges ledger
        ├── guest_request_list.html    # Guest service requests
        ├── shift_handover_list.html   # Shift handovers & cash drawer
        └── reports_hub.html           # Audit reports & CSV export
```
