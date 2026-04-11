from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

def send_html_email(subject, template_name, context, to_email):
    """Send professional HTML email with plain text fallback"""
    try:
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_welcome_email(user):
    """Send welcome email to new user"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'user_email': user.email,
        'dashboard_url': '/dashboard/',
        'support_url': '/support/',
        'unsubscribe_url': '/unsubscribe/',
    }
    return send_html_email(
        subject='Welcome to Qubix — Your Investment Journey Begins',
        template_name='core/emails/welcome_email.html',
        context=context,
        to_email=user.email
    )

def send_verification_email(user, code):
    """Send verification code email"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'verification_code': code,
        'verify_url': '/verify/',
        'resend_url': '/resend-verification/',
        'support_url': '/support/',
    }
    return send_html_email(
        subject='Verify Your Qubix Account',
        template_name='core/emails/verification_email.html',
        context=context,
        to_email=user.email
    )

def send_transaction_confirmation_email(user, transaction):
    """Send transaction confirmation email for stocks/minerals/real estate"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'transaction_id': transaction.id,
        'transaction_type': transaction.transaction_type,
        'asset_name': transaction.asset.name if transaction.asset else 'Cash',
        'asset_symbol': transaction.asset.symbol if transaction.asset else 'USD',
        'quantity': transaction.quantity,
        'price_per_unit': transaction.price_at_time or (transaction.total_amount / transaction.quantity if transaction.quantity else transaction.total_amount),
        'total_amount': transaction.total_amount,
        'transaction_date': transaction.created_at.strftime('%B %d, %Y at %I:%M %p'),
        'transaction_url': f'/transactions/{transaction.id}/',
        'invoice_url': f'/transactions/{transaction.id}/invoice/',
        'support_url': '/support/',
    }
    return send_html_email(
        subject=f'Transaction Confirmed — {transaction.transaction_type.upper()} {transaction.asset.symbol if transaction.asset else "Cash"}',
        template_name='core/emails/transaction_confirmation.html',
        context=context,
        to_email=user.email
    )

# ============= DEPOSIT EMAILS =============

def send_deposit_confirmation_email(user, deposit):
    """Send email when user confirms crypto deposit (pending verification)"""
    context = {
        'user': user,  # ← THIS MUST BE HERE
        'user_name': user.get_full_name() or user.username,
        'amount': f"${deposit.usd_amount:,.2f}",
        'crypto_amount': f"{deposit.crypto_amount:.8f} {deposit.crypto.symbol}",
        'crypto_symbol': deposit.crypto.symbol,  # ← ADD THIS TOO
        'deposit_id': deposit.id,
        'status': 'pending verification',
        'date': deposit.created_at.strftime('%B %d, %Y'),
        'dashboard_url': '/dashboard/',
        'support_url': '/support/',  # ← ADD THIS
        'wallet_address': deposit.wallet_address,  # ← ADD THIS (your template uses it)
    }
    return send_html_email(
        subject=f'Deposit Initiated - ${deposit.usd_amount:,.2f} Pending Verification',
        template_name='core/emails/deposit_confirmation.html',
        context=context,
        to_email=user.email
    )

def send_deposit_approved_email(user, deposit):
    """Send email when admin approves deposit and credits funds"""
    context = {
        'user': user,  # ← ADD THIS LINE
        'user_name': user.get_full_name() or user.username,
        'amount': f"${deposit.usd_amount:,.2f}",
        'crypto_amount': f"{deposit.crypto_amount:.8f} {deposit.crypto.symbol}",
        'crypto_symbol': deposit.crypto.symbol,
        'deposit_id': deposit.id,
        'date': deposit.completed_at.strftime('%B %d, %Y') if deposit.completed_at else timezone.now().strftime('%B %d, %Y'),
        'new_balance': f"${user.portfolio.cash_balance:,.2f}",
    }
    return send_html_email(
        subject=f'Deposit Approved - ${deposit.usd_amount:,.2f} Added to Your Account',
        template_name='core/emails/deposit_approved.html',
        context=context,
        to_email=user.email
    )

# ============= WITHDRAWAL EMAILS =============

def send_withdrawal_request_email(user, withdrawal):
    """Send email when user requests withdrawal"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'amount': f"${withdrawal.amount:,.2f}",
        'crypto_amount': f"{withdrawal.crypto_amount:.8f} {withdrawal.crypto_currency.symbol}",
        'crypto_symbol': withdrawal.crypto_currency.symbol,
        'wallet_address': withdrawal.wallet_address,
        'fee_amount': f"${withdrawal.fee_amount:,.2f}",
        'fee_percentage': withdrawal.fee_percentage,
        'net_amount': f"${withdrawal.amount - withdrawal.fee_amount:,.2f}",
        'request_id': withdrawal.id,
        'date': withdrawal.created_at.strftime('%B %d, %Y'),
        'support_url': '/support/',
    }
    return send_html_email(
        subject=f'Withdrawal Request Submitted - ${withdrawal.amount:,.2f}',
        template_name='core/emails/withdrawal_request.html',
        context=context,
        to_email=user.email
    )

def send_withdrawal_approved_email(user, withdrawal):
    """Send email when admin approves withdrawal"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'amount': f"${withdrawal.amount:,.2f}",
        'crypto_amount': f"{withdrawal.crypto_amount:.8f} {withdrawal.crypto_currency.symbol}",
        'crypto_symbol': withdrawal.crypto_currency.symbol,
        'wallet_address': withdrawal.wallet_address,
        'fee_amount': f"${withdrawal.fee_amount:,.2f}",
        'net_amount': f"${withdrawal.amount - withdrawal.fee_amount:,.2f}",
        'request_id': withdrawal.id,
        'date': withdrawal.processed_at.strftime('%B %d, %Y'),
        'support_url': '/support/',
    }
    return send_html_email(
        subject=f'Withdrawal Approved - ${withdrawal.amount:,.2f} Processing',
        template_name='core/emails/withdrawal_approved.html',
        context=context,
        to_email=user.email
    )

# ============= PHYSICAL PRODUCT EMAILS =============

def send_physical_order_confirmation_email(user, transaction):
    """Send email when physical product order is confirmed (after payment verification)"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'order_id': transaction.id,
        'product_name': transaction.product.name,
        'product_spec': transaction.product.specification,
        'quantity': transaction.quantity,
        'total_amount': f"${transaction.total_amount:,.2f}",
        'delivery_method': transaction.get_delivery_method_display(),
        'order_date': transaction.created_at.strftime('%B %d, %Y'),
        'tracking_url': f'/physical/track/{transaction.id}/',
        'support_url': '/support/',
    }
    
    # Add vault location for vault orders
    if transaction.delivery_method == 'vault':
        context['vault_location'] = 'Zurich, Switzerland'
    
    return send_html_email(
        subject=f'Order Confirmed — #{transaction.id}',
        template_name='core/emails/physical_order_confirmation.html',
        context=context,
        to_email=user.email
    )

def send_physical_order_shipped_email(user, transaction):
    """Send email when physical product order is shipped"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'order_id': transaction.id,
        'product_name': transaction.product.name,
        'quantity': transaction.quantity,
        'tracking_number': transaction.tracking_number or 'Pending',
        'shipped_date': transaction.shipped_at.strftime('%B %d, %Y'),
        'estimated_delivery': transaction.estimated_delivery.strftime('%B %d, %Y') if transaction.estimated_delivery else '10-14 business days',
        'carrier': 'DHL Secure Courier',
        'tracking_url': f'/physical/track/{transaction.id}/',
        'support_url': '/support/',
    }
    return send_html_email(
        subject=f'Order Shipped — #{transaction.id}',
        template_name='core/emails/physical_order_shipped.html',
        context=context,
        to_email=user.email
    )

def send_physical_order_delivered_email(user, transaction):
    """Send email when physical product order is delivered"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'order_id': transaction.id,
        'product_name': transaction.product.name,
        'quantity': transaction.quantity,
        'delivered_date': transaction.delivered_at.strftime('%B %d, %Y'),
        'support_url': '/support/',
    }
    return send_html_email(
        subject=f'Order Delivered — #{transaction.id}',
        template_name='core/emails/physical_order_delivered.html',
        context=context,
        to_email=user.email
    )

def send_physical_payment_received_email(user, transaction):
    """Send email when payment is received and under review"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'order_id': transaction.id,
        'product_name': transaction.product.name,
        'quantity': transaction.quantity,
        'total_amount': f"${transaction.total_amount:,.2f}",
        'payment_method': transaction.payment_method,
        'order_date': transaction.created_at.strftime('%B %d, %Y'),
        'support_url': '/support/',
    }
    return send_html_email(
        subject=f'Payment Received — Order #{transaction.id} Under Review',
        template_name='core/emails/physical_payment_received.html',
        context=context,
        to_email=user.email
    )

def send_price_alert_email(user, alert, asset, current_price, change_percent):
    """Send price alert email"""
    context = {
        'user_name': user.get_full_name() or user.username,
        'asset_name': asset.name,
        'asset_symbol': asset.symbol,
        'alert_type': alert.alert_type,
        'target_price': alert.target_price,
        'current_price': current_price,
        'change_percent': change_percent,
        'asset_url': f'/asset/{asset.id}/',
        'alerts_url': '/alerts/',
    }
    return send_html_email(
        subject=f'Price Alert: {asset.symbol} has {alert.alert_type} ${alert.target_price}',
        template_name='core/emails/price_alert_email.html',
        context=context,
        to_email=user.email
    )

def send_withdrawal_rejected_email(user, withdrawal):
    """Send email when admin rejects withdrawal request"""
    context = {
        'user': user,
        'withdrawal': withdrawal,
    }
    return send_html_email(
        subject=f'Withdrawal Request Rejected - ${withdrawal.amount:,.2f}',
        template_name='core/emails/withdrawal_rejected.html',
        context=context,
        to_email=user.email
    )    