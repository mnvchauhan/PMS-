from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Rooms & Room Rack
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/matrix/', views.room_matrix, name='room_matrix'),
    path('rooms/add/', views.room_create, name='room_create'),
    path('rooms/<int:pk>/edit/', views.room_update, name='room_update'),
    path('rooms/<int:pk>/clean/', views.room_clean_toggle, name='room_clean_toggle'),
    path('rooms/types/', views.room_type_list, name='room_type_list'),
    path('rooms/types/<int:pk>/edit/', views.room_type_update, name='room_type_update'),

    # Guests
    path('guests/', views.guest_list, name='guest_list'),
    path('guests/add/', views.guest_create, name='guest_create'),
    path('guests/<int:pk>/', views.guest_detail, name='guest_detail'),
    path('guests/<int:pk>/edit/', views.guest_update, name='guest_update'),

    # Reservations
    path('reservations/', views.reservation_list, name='reservation_list'),
    path('reservations/add/', views.reservation_create, name='reservation_create'),
    path('reservations/<int:pk>/', views.reservation_detail, name='reservation_detail'),
    path('reservations/<int:pk>/cancel/', views.reservation_cancel, name='reservation_cancel'),
    path('reservations/<int:pk>/checkin/', views.check_in_reservation, name='check_in_reservation'),

    # Front Desk Operations
    path('arrivals/', views.arrivals_list, name='arrivals_list'),
    path('departures/', views.departures_list, name='departures_list'),
    path('in-house/', views.in_house_list, name='in_house_list'),
    path('walk-in/', views.walk_in_check_in, name='walk_in_check_in'),

    # Check-out & Stays
    path('stays/<int:pk>/checkout/', views.check_out, name='check_out'),

    # Billing & Folio
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/add-item/', views.add_invoice_item, name='add_invoice_item'),
    path('invoices/<int:pk>/add-payment/', views.add_payment, name='add_payment'),

    # Front Desk Requests & Handover
    path('requests/', views.guest_request_list, name='guest_request_list'),
    path('requests/<int:pk>/status/', views.guest_request_update_status, name='guest_request_update_status'),
    path('handovers/', views.shift_handover_list, name='shift_handover_list'),

    # Reports
    path('reports/', views.reports_hub, name='reports'),
    path('reports/export/arrivals-csv/', views.export_arrivals_csv, name='export_arrivals_csv'),
    path('reports/export/departures-csv/', views.export_departures_csv, name='export_departures_csv'),
    path('reports/export/revenue-csv/', views.export_revenue_csv, name='export_revenue_csv'),
]
