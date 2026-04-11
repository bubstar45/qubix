from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import (
    physical_investments, 
    physical_product_detail, 
    physical_purchase, 
    physical_confirm_payment,
    physical_cart,
    physical_checkout,
    physical_checkout_vault_info,
    physical_checkout_shipping_info,
    physical_checkout_shipping_info_confirm,
    physical_payment,
    physical_add_to_cart,
    physical_update_cart,
    physical_remove_from_cart,
    physical_product_detail_page,
    physical_checkout_vault_confirm,
    physical_checkout_shipping_confirm,
    physical_payment_redirect,
    physical_payment_page,
    physical_save_purchase_data,
    physical_payment_process,
    physical_team_pending,
    physical_team_verify,
    physical_track_order,
    download_certificate,
    physical_request_delivery,
    physical_holding_detail,
    physical_sell_holding,
    download_invoice,
    physical_request_delivery_page,
    physical_request_delivery_confirm,
    physical_request_delivery_payment,
    physical_product_api_detail,
    physical_checkout_vault_confirm_first,
    physical_clear_session,
    physical_sell_confirm,
    physical_sell_payment,
    download_vault_certificate_html,
    download_allocated_storage,
    download_authenticity_certificate,
    download_delivery_receipt,
    download_insurance_certificate,
    download_proof_of_ownership,
    download_purchase_invoice,
    download_shipping_confirmation,
    download_shipping_invoice,
    download_storage_agreement,
    verify_document,
    password_reset_request,
    password_reset_confirm,
)

urlpatterns = [
    path('physical/product-test/<int:product_id>/', views.physical_product_detail_page_new, name='physical_product_detail_test'),

    # ============= PUBLIC URLs =============
    path('', views.landing, name='landing'),
    path('register/', views.register, name='register'),
    path('verify/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # ============= PASSWORD RESET URLs (Forgot Password) =============
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(template_name='core/auth/password_reset.html'),
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='core/auth/password_reset_done.html'),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name='core/auth/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='core/auth/password_reset_complete.html'),
         name='password_reset_complete'),
    
    # ============= DASHBOARD URLs =============
    path('dashboard/', views.dashboard, name='dashboard'),
    path('stocks/', views.stocks, name='stocks'),
    path('minerals/', views.minerals, name='minerals'),
    path('transactions/', views.transactions, name='transactions'),
    path('news/', views.market_news, name='market_news'),
    path('notifications/', views.notifications, name='notifications'),
    path('notification/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # ============= PORTFOLIO MANAGEMENT =============
    path('manage-portfolio/', views.manage_portfolio, name='manage_portfolio'),
    path('asset/<int:asset_id>/', views.asset_detail, name='asset_detail'),
    path('alert/<int:asset_id>/', views.create_price_alert, name='create_price_alert'),
    
    # ============= INVESTMENT URLs =============
    path('buy/<int:asset_id>/', views.buy_asset, name='buy_asset'),
    path('sell/<int:asset_id>/', views.sell_asset, name='sell_asset'),
    path('deposit/', views.deposit, name='deposit'),
    path('holdings/', views.holdings, name='holdings'),
    
    # ============= API ENDPOINTS =============
    path('api/price/<int:asset_id>/', views.get_asset_price, name='api_price'),
    path('api/prices/', views.get_all_prices, name='api_prices'),
    path('api/history/<int:asset_id>/', views.get_asset_history, name='api_history'),
    
    # ============= ADMIN URLs =============
    path('admin/pending/transactions/', views.admin_pending_transactions, name='admin_pending_transactions'),
    path('admin/approve/transaction/<int:transaction_id>/', views.admin_approve_transaction, name='admin_approve_transaction'),
    path('admin/reject/transaction/<int:transaction_id>/', views.admin_reject_transaction, name='admin_reject_transaction'),
    path('admin/pending/withdrawals/', views.admin_pending_withdrawals, name='admin_pending_withdrawals'),
    path('admin/approve/withdrawal/<int:withdrawal_id>/', views.admin_approve_withdrawal, name='admin_approve_withdrawal'),
    path('admin/reject/withdrawal/<int:withdrawal_id>/', views.admin_reject_withdrawal, name='admin_reject_withdrawal'),
    path('admin/manage-assets/', views.admin_manage_assets, name='admin_manage_assets'),
    
    # ============= ADMIN IMPERSONATION URLs =============
    path('admin/impersonate/start/<int:user_id>/', views.admin_impersonate_start, name='admin_impersonate_start'),
    path('admin/impersonate/stop/', views.admin_impersonate_stop, name='admin_impersonate_stop'),
    
    # ============= REAL ESTATE URLs =============
    path('real-estate/', views.real_estate_list, name='real_estate_list'),
    path('real-estate/<int:property_id>/', views.real_estate_detail, name='real_estate_detail'),
    path('real-estate/<int:property_id>/invest/', views.real_estate_invest, name='real_estate_invest'),
    path('real-estate/<int:property_id>/withdraw/', views.real_estate_withdraw, name='real_estate_withdraw'),
    path('my-real-estate/', views.real_estate_my_investments, name='real_estate_my_investments'),
    path('real-estate/dividends/', views.real_estate_dividends, name='real_estate_dividends'),
    path('admin/real-estate/properties/', views.admin_real_estate_properties, name='admin_real_estate_properties'),
    path('admin/real-estate/property/<int:property_id>/edit/', views.admin_real_estate_edit_property, name='admin_real_estate_edit_property'),
    path('admin/real-estate/property/<int:property_id>/delete/', views.admin_real_estate_delete_property, name='admin_real_estate_delete_property'),

    # ============= REAL ESTATE DOCUMENT DOWNLOADS =============
    path('real-estate/download/certificate/<int:investment_id>/', views.download_investment_certificate, name='download_investment_certificate'),
    path('real-estate/download/dividend/<int:dividend_id>/', views.download_dividend_statement, name='download_dividend_statement'),
    path('real-estate/download/invoice/<int:investment_id>/', views.download_purchase_invoice_real_estate, name='download_purchase_invoice_real_estate'),
    path('real-estate/download/prospectus/<int:property_id>/', views.download_property_prospectus, name='download_property_prospectus'),
    path('real-estate/download/title/<int:investment_id>/', views.download_title_certificate, name='download_title_certificate'),
    path('real-estate/download/operating/<int:investment_id>/', views.download_operating_agreement, name='download_operating_agreement'),
    path('real-estate/download/annual/<int:investment_id>/', views.download_annual_report, name='download_annual_report'),
    path('real-estate/download/capital/<int:investment_id>/', views.download_capital_call, name='download_capital_call'),
    path('real-estate/download/exit/<int:investment_id>/', views.download_exit_statement, name='download_exit_statement'),
    path('real-estate/download/k1/<int:investment_id>/', views.download_k1_tax_summary, name='download_k1_tax_summary'),

    # ============= DEPOSIT & WITHDRAWAL URLs =============
    path('deposit/billing/', views.deposit_billing, name='deposit_billing'),
    path('deposit/payment/', views.deposit_payment, name='deposit_payment'),
    path('deposit/crypto/select/', views.deposit_crypto_select, name='deposit_crypto_select'),
    path('deposit/crypto/pay/<int:deposit_id>/', views.deposit_crypto_pay, name='deposit_crypto_pay'),
    path('deposit/crypto/status/<int:deposit_id>/', views.deposit_crypto_status, name='deposit_crypto_status'),
    path('withdraw/', views.withdraw, name='withdraw'),
    path('withdraw/fee/', views.withdraw_fee, name='withdraw_fee'),
    path('withdraw/initiate/', views.withdraw_initiate, name='withdraw_initiate'),
    path('withdraw/receipt/', views.withdraw_receipt, name='withdraw_receipt'),

    # ============= PHYSICAL INVESTMENTS URLs =============
    path('physical/', physical_investments, name='physical_investments'),
    path('physical/cart/', physical_cart, name='physical_cart'),
    path('physical/product/<int:product_id>/', physical_product_detail_page, name='physical_product_detail_page'),
    path('physical/checkout/', physical_checkout, name='physical_checkout'),
    path('physical/checkout/vault/', physical_checkout_vault_info, name='physical_checkout_vault'),
    path('physical/checkout/vault/confirm/<int:product_id>/', physical_checkout_vault_confirm, name='physical_checkout_vault_confirm'),
    path('physical/checkout/vault/confirm/', physical_checkout_vault_confirm_first, name='physical_checkout_vault_confirm_first'),
    path('physical/checkout/shipping/<int:product_id>/', physical_checkout_shipping_info, name='physical_checkout_shipping'),
    path('physical/checkout/shipping/confirm/<int:product_id>/', physical_checkout_shipping_confirm, name='physical_checkout_shipping_confirm'),
    path('physical/payment/', physical_payment, name='physical_payment'),
    path('physical/payment/page/', physical_payment_page, name='physical_payment_page'),
    path('physical/payment/redirect/', physical_payment_redirect, name='physical_payment_redirect'),
    path('physical/track/<int:transaction_id>/', physical_track_order, name='physical_track_order'),
    
    # PDF DOCUMENT DOWNLOADS
    path('physical/certificate/<int:holding_id>/', download_certificate, name='download_certificate'),
    path('physical/invoice/<int:transaction_id>/', download_invoice, name='download_invoice'),
    path('physical/download/vault-certificate/<int:holding_id>/', download_vault_certificate_html, name='download_vault_certificate_html'),
    path('physical/download/allocated-storage/<int:holding_id>/', download_allocated_storage, name='download_allocated_storage'),
    path('physical/download/authenticity/<int:holding_id>/', download_authenticity_certificate, name='download_authenticity_certificate'),
    path('physical/download/delivery-receipt/<int:transaction_id>/', download_delivery_receipt, name='download_delivery_receipt'),
    path('physical/download/insurance/<int:holding_id>/', download_insurance_certificate, name='download_insurance_certificate'),
    path('physical/download/proof-ownership/<int:holding_id>/', download_proof_of_ownership, name='download_proof_of_ownership'),
    path('physical/download/purchase-invoice/<int:transaction_id>/', download_purchase_invoice, name='download_purchase_invoice'),
    path('physical/download/shipping-confirmation/<int:transaction_id>/', download_shipping_confirmation, name='download_shipping_confirmation'),
    path('physical/download/shipping-invoice/<int:transaction_id>/', download_shipping_invoice, name='download_shipping_invoice'),
    path('physical/download/storage-agreement/<int:holding_id>/', download_storage_agreement, name='download_storage_agreement'),
    
    # Delivery request pages
    path('physical/request-delivery/<int:holding_id>/', physical_request_delivery_page, name='physical_request_delivery_page'),
    path('physical/request-delivery/confirm/<int:holding_id>/', physical_request_delivery_confirm, name='physical_request_delivery_confirm'),
    path('physical/request-delivery/payment/<int:holding_id>/', physical_request_delivery_payment, name='physical_request_delivery_payment'),
    
    # Cart management
    path('physical/cart/update/<int:item_id>/', physical_update_cart, name='physical_update_cart'),
    path('physical/cart/remove/<int:item_id>/', physical_remove_from_cart, name='physical_remove_from_cart'),
    
    # PHYSICAL API ENDPOINTS
    path('physical/api/add-to-cart/<int:product_id>/', physical_add_to_cart, name='physical_add_to_cart'),
    path('physical/api/confirm-payment/', physical_confirm_payment, name='physical_confirm_payment'),
    path('physical/api/product/<int:product_id>/', physical_product_detail, name='physical_product_detail'),
    path('physical/api/product/<int:product_id>/detail/', physical_product_api_detail, name='physical_product_api_detail'),
    path('physical/api/purchase/<int:product_id>/', physical_purchase, name='physical_purchase'),
    path('physical/api/payment/process/', physical_payment_process, name='physical_payment_process'),
    path('physical/api/request-delivery/<int:holding_id>/', physical_request_delivery, name='physical_request_delivery'),
    path('physical/api/holding/<int:holding_id>/', physical_holding_detail, name='physical_holding_detail'),
    path('physical/api/sell-holding/<int:holding_id>/', physical_sell_holding, name='physical_sell_holding'),

    # TEAM/SUPPORT URLs
    path('team/physical/pending/', physical_team_pending, name='physical_team_pending'),
    path('team/physical/verify/<int:transaction_id>/', physical_team_verify, name='physical_team_verify'),
    path('physical/clear-session/', physical_clear_session, name='physical_clear_session'),
    path('physical/save-purchase/', physical_save_purchase_data, name='physical_save_purchase'),
    path('physical/sell/confirm/<int:holding_id>/', physical_sell_confirm, name='physical_sell_confirm'),
    path('physical/sell/payment/<int:holding_id>/', physical_sell_payment, name='physical_sell_payment'),
    path('verify/<str:code>/', verify_document, name='verify_document'),
    path('news/<int:news_id>/', views.news_detail, name='news_detail'),

    # NOTIFICATION API URLs
    path('api/notifications/', views.api_notifications, name='api_notifications'),
    path('api/notifications/count/', views.api_notification_count, name='api_notification_count'),
    path('api/notifications/<int:notification_id>/read/', views.api_mark_notification_read, name='api_mark_notification_read'),
    path('api/notifications/mark-all-read/', views.api_mark_all_read, name='api_mark_all_read'),
    path('api/notifications/admin/', views.api_admin_notifications, name='api_admin_notifications'),
    
    # CUSTOMER SUPPORT URLs
    path('api/support/messages/', views.api_support_messages, name='api_support_messages'),
    path('api/support/send-message/', views.api_support_send_message, name='api_support_send_message'),
    path('api/support/schedule-call/', views.api_support_schedule_call, name='api_support_schedule_call'),
    
    # User Support URLs
    path('support/tickets/', views.support_tickets, name='support_tickets'),
    path('support/ticket/<int:ticket_id>/', views.support_ticket_detail, name='support_ticket_detail'),
    
    # Admin Support URLs
    path('staff/support/tickets/', views.admin_support_tickets, name='admin_support_tickets'),
    path('staff/support/reply/<int:ticket_id>/', views.admin_reply_to_ticket, name='admin_reply_to_ticket'),
    path('staff/support/confirm-call/<int:call_id>/', views.admin_confirm_call, name='admin_confirm_call'),
    
    # Search & FAQ
    path('api/search/', views.api_search, name='api_search'),
    path('faq/', views.faq, name='faq'),
    path('api/support/unread-count/', views.api_unread_ticket_count, name='api_unread_ticket_count'),
    path('admin/core/supportticket/<int:ticket_id>/reply/', views.admin_reply_ticket, name='admin_reply_ticket'),
    path('admin/reply-ticket/<int:ticket_id>/', views.admin_reply_ticket_page, name='admin_reply_ticket_page'),
    path('support/reply/<int:ticket_id>/', views.admin_reply_ticket_page, name='admin_reply_ticket_page'),

    # PROFILE URLs
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),

    # PASSWORD CHANGE (logged in users)
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='core/auth/password_change.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='core/auth/password_change_done.html'), name='password_change_done'),

    path('reset-password/', password_reset_request, name='password_reset_request'),
    path('reset-password/<uidb64>/<token>/', password_reset_confirm, name='password_reset_confirm'),
]