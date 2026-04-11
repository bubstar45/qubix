import random
import threading
import time
import io
import os
import qrcode
from io import BytesIO
import base64
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from .utils.email_utils import send_physical_payment_received_email
from .utils.email_utils import (
    send_welcome_email,
    send_verification_email,
    send_transaction_confirmation_email,
    send_price_alert_email,
    send_html_email,
    send_deposit_confirmation_email,
    send_deposit_approved_email,
    send_withdrawal_request_email,
    send_withdrawal_approved_email,
    send_physical_payment_received_email,
    send_physical_order_confirmation_email,
    send_physical_order_shipped_email,
    send_physical_order_delivered_email,
)
from weasyprint import HTML
from playwright.sync_api import sync_playwright
from django.template.loader import render_to_string
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import get_template
from io import BytesIO
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from .models import PhysicalCart, PhysicalCartItem
from .models import (
    CustomUser, Asset, Portfolio, Holding, Transaction, WithdrawalRequest, 
    MarketNews, PriceCandle, Notification, PriceAlert,
    RealEstateProperty, RealEstateInvestment, RealEstateDividend,
    CryptoCurrency, CryptoDeposit,
    PhysicalProduct, PhysicalHolding, PhysicalTransaction,
    SupportTicket, SupportMessage, ScheduledCall
)
from .forms import RegistrationForm, LoginForm, VerificationForm, BuyAssetForm, DepositForm, WithdrawalForm

def landing(request):
    return render(request, 'core/landing.html')
    
def is_admin(user):
    return user.is_staff or user.is_superuser

# Background thread for price updates
def update_all_prices():
    """Background thread to update all asset prices"""
    while True:
        try:
            assets = Asset.objects.filter(is_active=True, price_update_enabled=True, price_min__isnull=False, price_max__isnull=False)
            for asset in assets:
                asset.update_price()
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            print(f"Price update error: {e}")
            time.sleep(5)

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Store registration data in session, DON'T create user yet
                request.session['pending_registration'] = {
                    'email': form.cleaned_data['email'],
                    'password1': form.cleaned_data['password1'],
                    'first_name': form.cleaned_data.get('first_name', ''),
                    'last_name': form.cleaned_data.get('last_name', ''),
                    'username': form.cleaned_data.get('username', ''),
                }
                
                # Generate verification code
                code = str(random.randint(100000, 999999))
                request.session['verification_code'] = code
                request.session['verification_email'] = form.cleaned_data['email']
                request.session['code_expires'] = (timezone.now() + timezone.timedelta(minutes=10)).isoformat()
                
                # Send verification email (create a temp user object just for email)
                class TempUser:
                    def __init__(self, email, first_name, last_name, username):
                        self.email = email
                        self.first_name = first_name
                        self.last_name = last_name
                        self.username = username
                    def get_full_name(self):
                        return f"{self.first_name} {self.last_name}".strip() or self.username
                
                temp_user = TempUser(
                    email=form.cleaned_data['email'],
                    first_name=form.cleaned_data.get('first_name', ''),
                    last_name=form.cleaned_data.get('last_name', ''),
                    username=form.cleaned_data.get('username', '')
                )
                
                send_verification_email(temp_user, code)
                
                messages.success(request, f"Verification code sent to {form.cleaned_data['email']}")
                return redirect('verify_email')
                
            except Exception as e:
                print(f"Registration error: {e}")
                messages.error(request, "An error occurred. Please try again.")
                return redirect('register')
    else:
        form = RegistrationForm()
    
    return render(request, 'core/auth/register.html', {'form': form})

def verify_email(request):
    # Get pending registration from session
    pending = request.session.get('pending_registration')
    expected_code = request.session.get('verification_code')
    code_expires = request.session.get('code_expires')
    
    if not pending or not expected_code:
        messages.error(request, "Session expired. Please register again.")
        return redirect('register')
    
    # Check if code expired
    if code_expires:
        from datetime import datetime
        expires_at = datetime.fromisoformat(code_expires)
        if timezone.now() > expires_at:
            messages.error(request, "Verification code has expired. Please register again.")
            request.session.pop('pending_registration', None)
            request.session.pop('verification_code', None)
            request.session.pop('code_expires', None)
            return redirect('register')
    
    if request.method == 'POST':
        form = VerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            
            if code == expected_code:
                # NOW create the user
                with transaction.atomic():
                    user = CustomUser.objects.create_user(
                        email=pending['email'],
                        password=pending['password1'],
                        username=pending.get('username', pending['email'].split('@')[0]),
                        first_name=pending.get('first_name', ''),
                        last_name=pending.get('last_name', ''),
                    )
                    user.email_verified = True
                    user.save()
                    
                    # Create portfolio
                    Portfolio.objects.create(user=user, cash_balance=10000.00)
                    
                    # Log the user in
                    login(request, user)
                    
                    # Clear session
                    request.session.pop('pending_registration', None)
                    request.session.pop('verification_code', None)
                    request.session.pop('code_expires', None)
                    
                    messages.success(request, "Email verified successfully! Welcome to Qubix.")
                    return redirect('dashboard')
            else:
                messages.error(request, "Invalid verification code. Please try again.")
    else:
        form = VerificationForm()
    
    return render(request, 'core/auth/verify.html', {
        'form': form,
        'email': pending.get('email', '')
    })

def resend_verification(request):
    pending = request.session.get('pending_registration')
    
    if not pending:
        messages.error(request, "Session expired. Please register again.")
        return redirect('register')
    
    # Generate new verification code
    code = str(random.randint(100000, 999999))
    request.session['verification_code'] = code
    request.session['code_expires'] = (timezone.now() + timezone.timedelta(minutes=10)).isoformat()
    
    # Create temp user for email
    class TempUser:
        def __init__(self, email, first_name, last_name, username):
            self.email = email
            self.first_name = first_name
            self.last_name = last_name
            self.username = username
        def get_full_name(self):
            return f"{self.first_name} {self.last_name}".strip() or self.username
    
    temp_user = TempUser(
        email=pending['email'],
        first_name=pending.get('first_name', ''),
        last_name=pending.get('last_name', ''),
        username=pending.get('username', '')
    )
    
    send_verification_email(temp_user, code)
    
    messages.success(request, f"New verification code sent to {pending['email']}")
    return redirect('verify_email')
    
def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            # Authenticate using email
            user = authenticate(request, username=email, password=password)
            
            if user:
                if user.email_verified:
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.first_name}!")
                    return redirect('dashboard')
                else:
                    # Store user ID in session for verification
                    request.session['temp_user_id'] = user.id
                    messages.warning(request, "Please verify your email first.")
                    return redirect('verify_email')
            else:
                messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()
    
    return render(request, 'core/auth/login.html', {'form': form})

def user_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('landing')

# In core/views.py, update your dashboard view:

# ============= ADMIN IMPERSONATION VIEWS =============

@staff_member_required
def admin_impersonate_start(request, user_id):
    """Admin impersonates a user - logs in as that user without password"""
    from django.contrib.auth import login
    from django.contrib import messages
    
    target_user = get_object_or_404(CustomUser, id=user_id)
    
    # Store original admin info in session
    request.session['impersonating'] = True
    request.session['original_user_id'] = request.user.id
    request.session['original_user_email'] = request.user.email
    
    # Log in as target user
    login(request, target_user)
    
    messages.success(request, f"You are now impersonating {target_user.email}. You have full access to their account.")
    return redirect('dashboard')


@staff_member_required
def admin_impersonate_stop(request):
    """Stop impersonating and return to admin account"""
    from django.contrib.auth import login
    from django.contrib import messages
    
    if request.session.get('impersonating'):
        original_user_id = request.session.get('original_user_id')
        if original_user_id:
            original_user = get_object_or_404(CustomUser, id=original_user_id)
            login(request, original_user)
            
            # Clear impersonation session data
            request.session.pop('impersonating', None)
            request.session.pop('original_user_id', None)
            request.session.pop('original_user_email', None)
            
            messages.success(request, f"Returned to admin account: {original_user.email}")
    
    return redirect('admin:core_customuser_changelist')


def add_impersonation_banner(request):
    """Context processor to show impersonation banner"""
    return {
        'is_impersonating': request.session.get('impersonating', False),
    }

@login_required
def dashboard(request):
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    from django.core.cache import cache
    
    portfolio = request.user.portfolio
    holdings = portfolio.holdings.select_related('asset').filter(quantity__gt=0)
    recent_transactions = request.user.transactions.all().order_by('-created_at')[:10]
    trending = Asset.objects.filter(is_active=True).order_by('-price_change_24h')[:5]
    recent_news = MarketNews.objects.filter(is_published=True).order_by('-published_at')[:3]
    
    # ─── OPTIMIZATION: Cache assets data (no historical prices) ───
    cache_key = 'dashboard_assets_light'
    assets_json = cache.get(cache_key)
    
    if assets_json is None:
        assets = Asset.objects.filter(is_active=True).only(
            'id', 'symbol', 'name', 'category', 'current_price', 
            'price_change_24h', 'market_cap', 'pe_ratio', 'dividend_yield',
            'revenue_ttm', 'net_income_ttm', 'beta', 'price_min', 'price_max'
        )
        assets_json = json.dumps([{
            'id': a.id,
            'symbol': a.symbol,
            'name': a.name,
            'category': a.category,
            'current_price': float(a.current_price),
            'price_change_24h': float(a.price_change_24h),
            'market_cap': a.market_cap,
            'pe_ratio': a.pe_ratio,
            'dividend_yield': float(a.dividend_yield) if a.dividend_yield else None,
            'revenue_ttm': a.revenue_ttm,
            'net_income_ttm': a.net_income_ttm,
            'beta': float(a.beta) if a.beta else None,
            'price_min': float(a.price_min) if a.price_min else None,
            'price_max': float(a.price_max) if a.price_max else None,
        } for a in assets], cls=DjangoJSONEncoder)
        cache.set(cache_key, assets_json, 600)
    
    # ─── Holdings JSON (user-specific, no cache) ───
    holdings_json = json.dumps([{
        'asset_symbol': h.asset.symbol,
        'asset_name': h.asset.name,
        'quantity': float(h.quantity),
        'current_price': float(h.asset.current_price),
        'profit_percent': float(h.profit_percent()),
        'average_price': float(h.average_price),
        'current_value': float(h.current_value())
    } for h in holdings], cls=DjangoJSONEncoder)
    
    # ─── Transactions JSON (user-specific) ───
    transactions_json = json.dumps([{
        'type': t.transaction_type,
        'symbol': t.asset.symbol if t.asset else 'CASH',
        'name': t.asset.name if t.asset else ('Deposit' if t.transaction_type == 'deposit' else 'Withdrawal'),
        'quantity': float(t.quantity) if t.quantity else 0,
        'total': float(t.get_effective_total_amount()),
        'date': t.get_effective_created_at().strftime('%Y-%m-%d'),
        'emoji': get_transaction_emoji(t)
    } for t in recent_transactions], cls=DjangoJSONEncoder)
    
    # Calculate asset allocation
    allocation = portfolio.get_asset_allocation()
    
    # ========== ADD REAL ESTATE DATA HERE ==========
    # (Put the code right here, before the context dictionary)
    real_estate_investments = RealEstateInvestment.objects.filter(user=request.user).select_related('property')
    real_estate_investments_json = json.dumps([{
        'id': inv.id,
        'property_id': inv.property.id,
        'property_name': inv.property.name,
        'amount_invested': float(inv.amount_invested),
        'shares': inv.shares,
        'total_dividends': float(sum(d.amount for d in inv.dividends.all())),
    } for inv in real_estate_investments], cls=DjangoJSONEncoder)
    
    real_estate_dividends_json = json.dumps([{
        'id': div.id,
        'investment_id': div.investment.id,
        'property_name': div.investment.property.name,
        'amount': float(div.amount),
        'month': div.month.strftime('%B %Y'),
    } for div in RealEstateDividend.objects.filter(investment__user=request.user).order_by('-month')], cls=DjangoJSONEncoder)
    # ========== END REAL ESTATE DATA ==========
    
    context = {
        'portfolio': portfolio,
        'holdings': holdings,
        'recent_transactions': recent_transactions,
        'trending': trending,
        'recent_news': recent_news,
        'total_value': portfolio.total_value(),
        'unrealized_pl': portfolio.unrealized_pl(),
        'allocation': allocation,
        'total_assets': len(holdings),
        'assets_json': assets_json,
        'holdings_json': holdings_json,
        'transactions_json': transactions_json,
        # Add these two lines to the context:
        'real_estate_investments_json': real_estate_investments_json,
        'real_estate_dividends_json': real_estate_dividends_json,
    }
    return render(request, 'core/dashboard/index.html', context)
@login_required
def stocks(request):
    stocks = Asset.objects.filter(category='stock', is_active=True)
    return render(request, 'core/dashboard/stocks.html', {'stocks': stocks})

@login_required
def minerals(request):
    minerals = Asset.objects.filter(category='mineral', is_active=True)
    return render(request, 'core/dashboard/minerals.html', {'minerals': minerals})

@login_required
def transactions(request):
    all_transactions = request.user.transactions.all().order_by('-created_at')
    # Add effective values to each transaction
    for tx in all_transactions:
        tx.effective_date = tx.get_effective_created_at()
        tx.effective_amount = tx.get_effective_total_amount()
    return render(request, 'core/dashboard/transactions.html', {'transactions': all_transactions})

@login_required
def asset_detail(request, asset_id):
    """Detailed view for a specific asset with full chart data and calculator"""
    import json
    from decimal import Decimal
    from django.core.cache import cache
    
    asset = get_object_or_404(Asset, id=asset_id, is_active=True)
    
    # Cache historical prices for this asset
    cache_key = f'asset_historical_{asset_id}'
    historical_periods = cache.get(cache_key)
    
    if historical_periods is None:
        historical_periods = {
            '1D': asset.get_historical_prices('1D'),
            '1W': asset.get_historical_prices('1W'),
            '1M': asset.get_historical_prices('1M'),
            '3M': asset.get_historical_prices('3M'),
            '1Y': asset.get_historical_prices('1Y'),
            '5Y': asset.get_historical_prices('5Y'),
        }
        # Cache for 5 minutes
        cache.set(cache_key, historical_periods, 300)
    
    # Check if user has holdings in this asset
    holding = None
    holding_current_value = 0
    try:
        holding = Holding.objects.get(portfolio=request.user.portfolio, asset=asset)
        holding_current_value = holding.current_value()
    except Holding.DoesNotExist:
        pass
    
    context = {
        'asset': asset,
        'holding': holding,
        'holding_current_value': holding_current_value,
        'portfolio_value': request.user.portfolio.total_value(),
        'cash_balance': request.user.portfolio.cash_balance,
        'can_sell': holding is not None and holding.quantity > 0,
        # Historical data for chart (from cache)
        'historical_1d': json.dumps(historical_periods['1D']),
        'historical_1w': json.dumps(historical_periods['1W']),
        'historical_1m': json.dumps(historical_periods['1M']),
        'historical_3m': json.dumps(historical_periods['3M']),
        'historical_1y': json.dumps(historical_periods['1Y']),
        'historical_5y': json.dumps(historical_periods['5Y']),
    }
    return render(request, 'core/dashboard/asset_detail.html', context)
@login_required
def manage_portfolio(request):
    """Detailed portfolio management view"""
    portfolio = request.user.portfolio
    holdings = portfolio.holdings.select_related('asset').all()
    
    # Calculate totals
    total_value = portfolio.total_value()
    holdings_data = []
    for holding in holdings:
        current_value = holding.current_value()
        profit_loss = holding.unrealized_pl()
        holdings_data.append({
            'holding': holding,
            'current_value': current_value,
            'profit_loss': profit_loss,
            'profit_percent': holding.profit_percent()
        })
    
    context = {
        'portfolio': portfolio,
        'holdings': holdings_data,
        'total_value': total_value,
        'cash_balance': portfolio.cash_balance,
        'unrealized_pl': portfolio.unrealized_pl(),
        'total_assets': len(holdings),
        'total_deposits': portfolio.total_deposits,
        'total_withdrawals': portfolio.total_withdrawals,
        'total_dividends': portfolio.total_dividends,
        'ytd_performance': portfolio.ytd_performance,
    }
    return render(request, 'core/dashboard/manage_portfolio.html', context)

@login_required
def market_news(request):
    """Market news page"""
    news = MarketNews.objects.filter(is_published=True).order_by('-published_at')
    categories = MarketNews.CATEGORY_CHOICES
    
    context = {
        'news': news,
        'categories': categories
    }
    return render(request, 'core/dashboard/news.html', context)

@login_required
def notifications(request):
    """User notifications page"""
    notifications = request.user.notifications.all().order_by('-created_at')
    # Add effective date to each notification
    for n in notifications:
        n.effective_date = n.get_effective_created_at()
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count
    }
    return render(request, 'core/dashboard/notifications.html', context)

@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    return JsonResponse({'status': 'success'})

@login_required
def create_price_alert(request, asset_id):
    """Create a price alert for an asset"""
    asset = get_object_or_404(Asset, id=asset_id)
    
    if request.method == 'POST':
        target_price = float(request.POST.get('target_price'))
        alert_type = request.POST.get('alert_type')
        
        alert = PriceAlert.objects.create(
            user=request.user,
            asset=asset,
            target_price=target_price,
            alert_type=alert_type
        )
        
        messages.success(request, f"Price alert created for {asset.symbol} when it goes {alert_type} ${target_price}")
        return redirect('asset_detail', asset_id=asset_id)
    
    return redirect('asset_detail', asset_id=asset_id)

from django.views.decorators.csrf import csrf_exempt
import json

@login_required
@csrf_exempt
def buy_asset(request, asset_id):
    """API endpoint for buying assets - INSTANT APPROVAL"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    try:
        import json
        data = json.loads(request.body)
        quantity = float(data.get('quantity', 0))
        
        if quantity <= 0:
            return JsonResponse({'error': 'Invalid quantity'}, status=400)
        
        asset = get_object_or_404(Asset, id=asset_id, is_active=True)
        portfolio = request.user.portfolio
        total = quantity * float(asset.current_price)
        
        # Convert to float for comparison
        if total > float(portfolio.cash_balance):
            return JsonResponse({'error': 'Insufficient funds'}, status=400)
        
        # Process the transaction immediately
        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
            # Update portfolio cash - Convert to Decimal for storage
            new_balance = float(portfolio.cash_balance) - total
            portfolio.cash_balance = Decimal(str(new_balance))
            portfolio.save()
            
            # Update or create holding
            holding, created = Holding.objects.get_or_create(
                portfolio=portfolio,
                asset=asset,
                defaults={
                    'quantity': quantity,
                    'average_price': float(asset.current_price)
                }
            )
            
            if not created:
                # Update average price for existing holding
                total_quantity = float(holding.quantity) + quantity
                total_cost = (float(holding.quantity) * float(holding.average_price)) + (quantity * float(asset.current_price))
                holding.average_price = Decimal(str(total_cost / total_quantity))
                holding.quantity = Decimal(str(total_quantity))
                holding.save()
            
            # Record transaction
            tx = Transaction.objects.create(
                user=request.user,
                asset=asset,
                transaction_type='buy',
                quantity=quantity,
                price_at_time=float(asset.current_price),
                total_amount=Decimal(str(total)),
                status='approved'
            )
            send_transaction_confirmation_email(request.user, tx)
            # Create notification
            Notification.objects.create(
                user=request.user,
                title=f"Purchase Confirmed",
                message=f"You successfully bought {quantity} shares of {asset.symbol} for ${total:,.2f}.",
                notification_type='transaction'
            )
        
        return JsonResponse({'success': True, 'message': f'Successfully bought {quantity} shares of {asset.symbol}!'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
def sell_asset(request, asset_id):
    """API endpoint for selling assets - INSTANT APPROVAL"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    try:
        import json
        data = json.loads(request.body)
        quantity = float(data.get('quantity', 0))
        
        if quantity <= 0:
            return JsonResponse({'error': 'Invalid quantity'}, status=400)
        
        asset = get_object_or_404(Asset, id=asset_id, is_active=True)
        portfolio = request.user.portfolio
        holding = Holding.objects.filter(portfolio=portfolio, asset=asset).first()
        
        if not holding or quantity > float(holding.quantity):
            return JsonResponse({'error': 'Insufficient holdings'}, status=400)
        
        total = quantity * float(asset.current_price)
        
        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
            # Update holding
            new_quantity = float(holding.quantity) - quantity
            if new_quantity <= 0:
                holding.delete()
            else:
                holding.quantity = Decimal(str(new_quantity))
                holding.save()
            
            # Update portfolio cash - Convert to Decimal for storage
            new_balance = float(portfolio.cash_balance) + total
            portfolio.cash_balance = Decimal(str(new_balance))
            portfolio.save()
            
            # Record transaction
            tx = Transaction.objects.create(
                user=request.user,
                asset=asset,
                transaction_type='sell',
                quantity=quantity,
                price_at_time=float(asset.current_price),
                total_amount=Decimal(str(total)),
                status='approved'
            )
            send_transaction_confirmation_email(request.user, tx)
            # Create notification
            Notification.objects.create(
                user=request.user,
                title=f"Sale Confirmed",
                message=f"You successfully sold {quantity} shares of {asset.symbol} for ${total:,.2f}.",
                notification_type='transaction'
            )
        
        return JsonResponse({'success': True, 'message': f'Successfully sold {quantity} shares of {asset.symbol}!'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)        

@login_required
def withdraw(request):
    """Step 1: Enter withdrawal details"""
    from .models import CryptoCurrency
    
    cryptos = CryptoCurrency.objects.filter(is_active=True)
    portfolio = request.user.portfolio
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        crypto_id = request.POST.get('crypto_id')
        wallet_address = request.POST.get('wallet_address')
        
        crypto = get_object_or_404(CryptoCurrency, id=crypto_id, is_active=True)
        
        if amount <= 0:
            messages.error(request, "Please enter a valid amount.")
            return redirect('withdraw')
        
        if amount > portfolio.cash_balance:
            messages.error(request, f"Insufficient funds. Available balance: ${portfolio.cash_balance:,.2f}")
            return redirect('withdraw')
        
        if amount < 10:
            messages.error(request, "Minimum withdrawal is $10")
            return redirect('withdraw')
        
        if not wallet_address or len(wallet_address) < 10:
            messages.error(request, "Please enter a valid wallet address.")
            return redirect('withdraw')
        
        # Calculate amounts
        crypto_amount = amount / crypto.rate_usd
        fee_percentage = Decimal('5.00')
        fee_amount = amount * (fee_percentage / 100)
        fee_crypto_amount = fee_amount / crypto.rate_usd
        
        # Store in session for next steps
        request.session['withdraw_amount'] = float(amount)
        request.session['withdraw_crypto_id'] = crypto.id
        request.session['withdraw_crypto_symbol'] = crypto.symbol
        request.session['withdraw_crypto_name'] = crypto.name
        request.session['withdraw_crypto_amount'] = float(crypto_amount)
        request.session['withdraw_rate'] = float(crypto.rate_usd)
        request.session['withdraw_network'] = crypto.network
        request.session['withdraw_wallet_address'] = wallet_address
        request.session['withdraw_fee_percentage'] = float(fee_percentage)
        request.session['withdraw_fee_amount'] = float(fee_amount)
        request.session['withdraw_fee_crypto_amount'] = float(fee_crypto_amount)
        
        return redirect('withdraw_fee')
    
    context = {
        'cryptos': cryptos,
        'cash_balance': portfolio.cash_balance,
    }
    return render(request, 'core/dashboard/withdraw.html', context)


@login_required
def withdraw_fee(request):
    """Step 2: Pay the 5% fee"""
    from .models import CryptoCurrency
    
    amount = request.session.get('withdraw_amount')
    crypto_id = request.session.get('withdraw_crypto_id')
    crypto_symbol = request.session.get('withdraw_crypto_symbol')
    crypto_name = request.session.get('withdraw_crypto_name')
    fee_amount = request.session.get('withdraw_fee_amount')
    fee_crypto_amount = request.session.get('withdraw_fee_crypto_amount')
    wallet_address = request.session.get('withdraw_wallet_address')
    
    if not amount or not crypto_id:
        messages.error(request, "Please start a new withdrawal.")
        return redirect('withdraw')
    
    # Get crypto wallet address for fee payment
    crypto = CryptoCurrency.objects.get(id=crypto_id)
    fee_wallet_address = crypto.wallet_address
    
    # Update session with fee wallet address
    request.session['withdraw_fee_wallet_address'] = fee_wallet_address
    
    cryptos = CryptoCurrency.objects.filter(is_active=True)
    
    context = {
        'cryptos': cryptos,
        'withdrawal_amount': amount,
        'crypto_id': crypto_id,
        'crypto_symbol': crypto_symbol,
        'crypto_name': crypto_name,
        'fee_amount': fee_amount,
        'fee_crypto_amount': fee_crypto_amount,
        'wallet_address': fee_wallet_address,
    }
    return render(request, 'core/dashboard/withdraw_fee.html', context)

@login_required
@csrf_exempt
def withdraw_initiate(request):
    """Initiate withdrawal after fee payment confirmation"""
    from decimal import Decimal
    from .models import WithdrawalRequest, Transaction, CryptoCurrency
    from django.db import transaction as db_transaction
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    try:
        # Get all data from session
        amount = request.session.get('withdraw_amount')
        crypto_id = request.session.get('withdraw_crypto_id')
        crypto_symbol = request.session.get('withdraw_crypto_symbol')
        crypto_amount = request.session.get('withdraw_crypto_amount')
        rate = request.session.get('withdraw_rate')
        wallet_address = request.session.get('withdraw_wallet_address')
        fee_percentage = request.session.get('withdraw_fee_percentage')
        fee_amount = request.session.get('withdraw_fee_amount')
        fee_crypto_amount = request.session.get('withdraw_fee_crypto_amount')
        
        if not amount or not crypto_id:
            return JsonResponse({'error': 'No withdrawal in progress'}, status=400)
        
        crypto = CryptoCurrency.objects.get(id=crypto_id)
        portfolio = request.user.portfolio
        
        with db_transaction.atomic():
            # Deduct FULL amount from user's cash balance
            portfolio.cash_balance -= Decimal(str(amount))
            portfolio.save()
            
            # Create withdrawal request with fee details
            withdrawal = WithdrawalRequest.objects.create(
                user=request.user,
                amount=Decimal(str(amount)),
                crypto_currency=crypto,
                crypto_amount=Decimal(str(crypto_amount)),
                rate_used=Decimal(str(rate)),
                wallet_address=wallet_address,
                fee_percentage=Decimal(str(fee_percentage)),
                fee_amount=Decimal(str(fee_amount)),
                fee_crypto_amount=Decimal(str(fee_crypto_amount)),
                fee_paid=True,
                fee_paid_at=timezone.now(),
                status='pending'
            )
            send_withdrawal_request_email(request.user, withdrawal)
            # Create transaction record for recent activity
            Transaction.objects.create(
                user=request.user,
                transaction_type='withdraw',
                total_amount=Decimal(str(amount)),
                status='pending',
                notes=f"Withdrawal: ${amount:,.2f} - Fee ${fee_amount:,.2f} paid"
            )
            Notification.objects.create(
                user=request.user,
                title="Withdrawal Request Submitted",
                message=f"Your withdrawal request of ${amount:,.2f} has been submitted and is pending admin approval.",
                notification_type='withdraw',
                is_read=False
            )    
            # Mark fee as paid in session
            request.session['withdraw_fee_paid'] = True
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        print(f"Withdrawal initiation error: {e}")
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def withdraw_receipt(request):
    """Step 3: View receipt after withdrawal is initiated"""
    from decimal import Decimal
    
    # Get all data from session
    amount = request.session.get('withdraw_amount')
    crypto_symbol = request.session.get('withdraw_crypto_symbol')
    crypto_amount = request.session.get('withdraw_crypto_amount')
    wallet_address = request.session.get('withdraw_wallet_address')
    fee_amount = request.session.get('withdraw_fee_amount')
    fee_crypto_amount = request.session.get('withdraw_fee_crypto_amount')
    fee_paid = request.session.get('withdraw_fee_paid', False)
    
    if not amount or not fee_paid:
        messages.error(request, "No withdrawal in progress.")
        return redirect('dashboard')
    
    context = {
        'withdrawal_amount': amount,
        'crypto_symbol': crypto_symbol,
        'crypto_amount': crypto_amount,
        'fee_amount': fee_amount,
        'fee_crypto_amount': fee_crypto_amount,
        'wallet_address': wallet_address,
    }
    return render(request, 'core/dashboard/withdraw_receipt.html', context)

# API Endpoints
@csrf_exempt
def get_asset_price(request, asset_id):
    """AJAX endpoint to get latest price"""
    try:
        asset = Asset.objects.get(id=asset_id)
        return JsonResponse({
            'price': float(asset.current_price),
            'change_percent': float(asset.price_change_24h),
            'symbol': asset.symbol,
            'name': asset.name,
            'volume_24h': asset.volume_24h,
            'market_cap': asset.market_cap
        })
    except Asset.DoesNotExist:
        return JsonResponse({'error': 'Asset not found'}, status=404)

@csrf_exempt
def get_all_prices(request):
    """AJAX endpoint to get all asset prices"""
    assets = Asset.objects.filter(is_active=True)
    data = {}
    for asset in assets:
        data[asset.symbol] = {
            'price': float(asset.current_price),
            'change_percent': float(asset.price_change_24h),
            'name': asset.name,
            'category': asset.category,
            'market_cap': asset.market_cap,
            'volume_24h': asset.volume_24h
        }
    return JsonResponse(data)

@csrf_exempt
def get_asset_history(request, asset_id):
    """AJAX endpoint to get price history for chart using candles"""
    try:
        asset = Asset.objects.get(id=asset_id)
        days = int(request.GET.get('days', 7))
        cutoff = timezone.now() - timezone.timedelta(days=days)
        candles = PriceCandle.objects.filter(asset=asset, timestamp__gte=cutoff).order_by('timestamp')
        
        data = {
            'symbol': asset.symbol,
            'prices': [float(c.close) for c in candles],
            'timestamps': [c.timestamp.strftime('%Y-%m-%d %H:%M') for c in candles],
            'highs': [float(c.high) for c in candles],
            'lows': [float(c.low) for c in candles],
            'opens': [float(c.open) for c in candles]
        }
        return JsonResponse(data)
    except Asset.DoesNotExist:
        return JsonResponse({'error': 'Asset not found'}, status=404)

# Admin Views
@login_required
@user_passes_test(is_admin)
def admin_pending_transactions(request):
    pending = Transaction.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'core/admin/pending_transactions.html', {'transactions': pending})

@login_required
@user_passes_test(is_admin)
def admin_approve_transaction(request, transaction_id):
    transaction_obj = get_object_or_404(Transaction, id=transaction_id)
    
    if request.method == 'POST':
        transaction_obj.approve(request.user)
        
        # Create notification for user
        Notification.objects.create(
            user=transaction_obj.user,
            title=f"Transaction Approved",
            message=f"Your {transaction_obj.transaction_type} order for ${transaction_obj.total_amount:,.2f} has been approved.",
            notification_type='transaction',
            related_object_id=transaction_obj.id
        )
        
        messages.success(request, f"Transaction #{transaction_id} approved.")
        return redirect('admin_pending_transactions')
    
    return render(request, 'core/admin/approve_transaction.html', {'transaction': transaction_obj})

@login_required
@user_passes_test(is_admin)
def admin_reject_transaction(request, transaction_id):
    transaction_obj = get_object_or_404(Transaction, id=transaction_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        transaction_obj.reject(request.user, reason)
        
        # Create notification for user
        Notification.objects.create(
            user=transaction_obj.user,
            title=f"Transaction Rejected",
            message=f"Your {transaction_obj.transaction_type} order for ${transaction_obj.total_amount:,.2f} has been rejected. Reason: {reason}",
            notification_type='transaction',
            related_object_id=transaction_obj.id
        )
        
        messages.success(request, f"Transaction #{transaction_id} rejected.")
        return redirect('admin_pending_transactions')
    
    return render(request, 'core/admin/reject_transaction.html', {'transaction': transaction_obj})

@login_required
@user_passes_test(is_admin)
def admin_pending_withdrawals(request):
    pending = WithdrawalRequest.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'core/admin/pending_withdrawals.html', {'withdrawals': pending})

@login_required
@user_passes_test(is_admin)
def admin_approve_withdrawal(request, withdrawal_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if request.method == 'POST':
        # The approve method now handles transaction update
        withdrawal.approve(request.user)
        
        messages.success(request, f"Withdrawal #{withdrawal_id} approved.")
        return redirect('admin_pending_withdrawals')
    
    return render(request, 'core/admin/approve_withdrawal.html', {'withdrawal': withdrawal})

@login_required
@user_passes_test(is_admin)
def admin_reject_withdrawal(request, withdrawal_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        # The reject method now handles transaction update and fund return
        withdrawal.reject(request.user, reason)
        
        messages.success(request, f"Withdrawal #{withdrawal_id} rejected.")
        return redirect('admin_pending_withdrawals')
    
    return render(request, 'core/admin/reject_withdrawal.html', {'withdrawal': withdrawal})

@login_required
@user_passes_test(is_admin)
def admin_manage_assets(request):
    """Admin view to manage assets and their price ranges"""
    assets = Asset.objects.all().order_by('category', 'symbol')
    
    if request.method == 'POST':
        asset_id = request.POST.get('asset_id')
        asset = get_object_or_404(Asset, id=asset_id)
        
        asset.price_min = request.POST.get('price_min')
        asset.price_max = request.POST.get('price_max')
        asset.volatility = request.POST.get('volatility')
        asset.price_update_enabled = request.POST.get('price_update_enabled') == 'on'
        asset.save()
        
        messages.success(request, f"Asset {asset.symbol} updated successfully.")
        return redirect('admin_manage_assets')
    
    return render(request, 'core/admin/manage_assets.html', {'assets': assets})


# ============= REAL ESTATE VIEWS (UPDATED with Personalized Tracking) =============

@login_required
def real_estate_list(request):
    """List all available real estate properties - Shows personalized data per user"""
    properties = RealEstateProperty.objects.filter(status='funding').order_by('-created_at')
    
    # Get user's real estate investments for totals
    user_investments = RealEstateInvestment.objects.filter(user=request.user).select_related('property')
    
    # Calculate totals
    total_invested = sum(inv.amount_invested for inv in user_investments)
    
    # Calculate total dividends
    total_dividends = 0
    for investment in user_investments:
        total_dividends += sum(d.amount for d in investment.dividends.all())
    
    # Count number of properties user has invested in
    investments_count = user_investments.count()
    
    # Prepare properties with personalized display data
    for prop in properties:
        user_investment = user_investments.filter(property=prop).first()
        
        if user_investment:
            # User has invested - show their personal data
            prop.display_remaining = user_investment.personal_remaining
            prop.display_funded_percent = user_investment.personal_funded_percent
            prop.display_investor_count = user_investment.personal_investor_count
        else:
            # User hasn't invested - show admin baseline
            prop.display_remaining = prop.total_available
            prop.display_funded_percent = prop.funded_percent
            prop.display_investor_count = prop.investor_count
    
    context = {
        'properties': properties,
        'total_invested': total_invested,      # Add this
        'total_dividends': total_dividends,    # Add this
        'investments_count': investments_count, # Add this
    }
    return render(request, 'core/real_estate/list.html', context)


@login_required
def real_estate_detail(request, property_id):
    """Property detail page - Shows personalized data for the user"""
    property_obj = get_object_or_404(RealEstateProperty, id=property_id)
    user_investment = RealEstateInvestment.objects.filter(
        user=request.user, 
        property=property_obj
    ).first()
    
    if user_investment:
        # User has invested - show their personal data
        display_remaining = user_investment.personal_remaining
        display_funded_percent = user_investment.personal_funded_percent
        display_investor_count = user_investment.personal_investor_count
        has_invested = True
    else:
        # User hasn't invested - show admin baseline
        display_remaining = property_obj.total_available
        display_funded_percent = property_obj.funded_percent
        display_investor_count = property_obj.investor_count
        has_invested = False
    
    context = {
        'property': property_obj,
        'has_invested': has_invested,
        'user_investment': user_investment,
        'price_per_share': property_obj.price_per_share,
        'display_remaining': display_remaining,
        'display_funded_percent': display_funded_percent,
        'display_investor_count': display_investor_count,
    }
    return render(request, 'core/real_estate/detail.html', context)


@login_required
def real_estate_invest(request, property_id):
    """Handle investment in a property - with period selection and confirmation"""
    if request.method != 'POST':
        return redirect('real_estate_detail', property_id=property_id)
    
    property_obj = get_object_or_404(RealEstateProperty, id=property_id)
    amount = Decimal(request.POST.get('amount', 0))
    investment_period_months = int(request.POST.get('investment_period', 12))  # Get the selected period
    
    # Check if user already has an investment
    user_investment = RealEstateInvestment.objects.filter(
        user=request.user, 
        property=property_obj
    ).first()
    
    # Determine remaining amount based on user's personal state
    if user_investment:
        remaining = user_investment.personal_remaining
    else:
        remaining = property_obj.total_available
    
    # Validation
    if amount < 100:
        messages.error(request, "Minimum investment is $100")
        return redirect('real_estate_detail', property_id=property_id)
    
    if amount > remaining:
        messages.error(request, f"Only ${remaining:,.2f} remaining for your investment limit")
        return redirect('real_estate_detail', property_id=property_id)
    
    # Validate investment period (minimum 6 months)
    if investment_period_months < 6:
        messages.error(request, "Minimum investment period is 6 months")
        return redirect('real_estate_detail', property_id=property_id)
    
    # Calculate maturity date
    maturity_date = timezone.now() + timedelta(days=investment_period_months * 30)
    
    shares = int(amount / property_obj.price_per_share)
    
    # Calculate expected returns
    annual_return_rate = float(getattr(property_obj, 'expected_annual_return', 8.5))
    period_years = investment_period_months / 12
    expected_value_at_maturity = float(amount) * ((1 + annual_return_rate / 100) ** period_years)
    expected_profit = expected_value_at_maturity - float(amount)
    
    with transaction.atomic():
        if user_investment:
            # Update existing investment (user investing more)
            # Recalculate weighted average period
            old_weight = user_investment.amount_invested
            new_weight = amount
            total_weight = old_weight + new_weight
            
            weighted_period = (
                (user_investment.investment_period_months * old_weight) + 
                (investment_period_months * new_weight)
            ) / total_weight
            
            user_investment.amount_invested += amount
            user_investment.shares += shares
            user_investment.personal_remaining -= amount
            user_investment.investment_period_months = int(weighted_period)
            user_investment.maturity_date = timezone.now() + timedelta(days=user_investment.investment_period_months * 30)
            user_investment.expected_value_at_maturity = Decimal(str(expected_value_at_maturity))
            user_investment.calculate_personal_metrics()
            user_investment.save()
            
            investment_message = f"Added ${amount:,.2f} to your investment in {property_obj.name}. Total investment: ${user_investment.amount_invested:,.2f}"
        else:
            # Create new investment with personalized tracking
            user_investment = RealEstateInvestment.objects.create(
                user=request.user,
                property=property_obj,
                shares=shares,
                amount_invested=amount,
                personal_remaining=property_obj.total_available - amount,
                investment_period_months=investment_period_months,
                maturity_date=timezone.now() + timedelta(days=investment_period_months * 30),
                expected_annual_return=Decimal(str(annual_return_rate)),
                expected_value_at_maturity=Decimal(str(expected_value_at_maturity)),
            )
            user_investment.calculate_personal_metrics()
            
            investment_message = f"Successfully invested ${amount:,.2f} in {property_obj.name}. You now own {shares} shares."
        
        # Deduct from user's cash balance
        portfolio = request.user.portfolio
        portfolio.cash_balance -= amount
        portfolio.save()
        
        # Create transaction record
        tx = Transaction.objects.create(
            user=request.user,
            transaction_type='buy',
            quantity=shares,
            price_at_time=float(property_obj.price_per_share),
            total_amount=amount,
            status='approved',
            notes=f"Real Estate Investment in {property_obj.name} - {investment_period_months} months lock-in period"
        )
        send_transaction_confirmation_email(request.user, tx)
        # Create notification
        Notification.objects.create(
            user=request.user,
            title=f"Real Estate Investment Confirmed",
            message=f"{investment_message}\n\nLock-in period: {investment_period_months} months\nMaturity date: {user_investment.maturity_date.strftime('%B %d, %Y')}\nExpected value at maturity: ${expected_value_at_maturity:,.2f}",
            notification_type='transaction'
        )
    
    messages.success(request, f"{investment_message} Your investment is locked until {user_investment.maturity_date.strftime('%B %d, %Y')}.")
    return redirect('real_estate_detail', property_id=property_id)

@login_required
def real_estate_my_investments(request):
    """User's real estate portfolio - Shows all user's investments"""
    investments = RealEstateInvestment.objects.filter(user=request.user).select_related('property')
    
    total_invested = sum(i.get_effective_amount_invested() for i in investments)
    
    # Calculate total dividends properly
    total_dividends = 0
    for investment in investments:
        investment.total_dividends = sum(d.amount for d in investment.dividends.all())
        total_dividends += investment.total_dividends
        # Add effective values
        investment.effective_invested_at = investment.get_effective_invested_at()
        investment.effective_amount = investment.get_effective_amount_invested()
    
    # Calculate personalized metrics for each investment
    for inv in investments:
        inv.current_remaining = inv.personal_remaining
        inv.current_funded_percent = inv.personal_funded_percent
    
    context = {
        'investments': investments,
        'total_invested': total_invested,
        'total_dividends': total_dividends,
    }
    return render(request, 'core/real_estate/my_investments.html', context)

@login_required
def real_estate_dividends(request):
    """Real estate dividend history for the user"""
    # Get actual Dividend model objects, not dictionaries
    dividends = RealEstateDividend.objects.filter(
        investment__user=request.user
    ).select_related('investment__property').order_by('-month')
    
    # Calculate total dividends
    total_dividends = sum(d.amount for d in dividends)
    
    context = {
        'dividends': dividends,  # Pass the actual model objects, not a list of dicts
        'total_dividends': total_dividends,
    }
    return render(request, 'core/real_estate/dividends.html', context)

# Admin Real Estate Views
@login_required
@user_passes_test(is_admin)
def admin_real_estate_properties(request):
    """Admin view to manage real estate properties"""
    properties = RealEstateProperty.objects.all().order_by('-created_at')
    return render(request, 'core/admin/real_estate_properties.html', {'properties': properties})


@login_required
@user_passes_test(is_admin)
def admin_real_estate_edit_property(request, property_id):
    """Admin view to edit a real estate property"""
    property_obj = get_object_or_404(RealEstateProperty, id=property_id)
    
    if request.method == 'POST':
        # Update property fields
        property_obj.name = request.POST.get('name')
        property_obj.location = request.POST.get('location')
        property_obj.address = request.POST.get('address')
        property_obj.beds = request.POST.get('beds')
        property_obj.baths = request.POST.get('baths')
        property_obj.sqft = request.POST.get('sqft')
        property_obj.year_built = request.POST.get('year_built')
        property_obj.purchase_price = request.POST.get('purchase_price')
        property_obj.total_available = request.POST.get('total_available')
        property_obj.monthly_rent = request.POST.get('monthly_rent')
        property_obj.annual_cash_flow = request.POST.get('annual_cash_flow')
        property_obj.total_shares = request.POST.get('total_shares')
        property_obj.price_per_share = request.POST.get('price_per_share')
        property_obj.status = request.POST.get('status')
        property_obj.badge = request.POST.get('badge')
        property_obj.market_description = request.POST.get('market_description')
        property_obj.property_description = request.POST.get('property_description')
        property_obj.funded_percent = request.POST.get('funded_percent', 0)
        property_obj.investor_count = request.POST.get('investor_count', 0)
        property_obj.save()
        
        messages.success(request, f"Property {property_obj.name} updated successfully.")
        return redirect('admin_real_estate_properties')
    
    return render(request, 'core/admin/real_estate_edit_property.html', {'property': property_obj})


@login_required
@user_passes_test(is_admin)
def admin_real_estate_delete_property(request, property_id):
    """Admin view to delete a real estate property"""
    property_obj = get_object_or_404(RealEstateProperty, id=property_id)
    property_name = property_obj.name
    
    if request.method == 'POST':
        # Also delete all related investments
        RealEstateInvestment.objects.filter(property=property_obj).delete()
        property_obj.delete()
        messages.success(request, f"Property {property_name} and all related investments deleted successfully.")
        return redirect('admin_real_estate_properties')
    
    return render(request, 'core/admin/real_estate_delete_property.html', {'property': property_obj})

def get_transaction_emoji(transaction):
    """Return appropriate emoji for transaction type"""
    if transaction.transaction_type == 'deposit':
        return '💰'
    if transaction.transaction_type == 'withdraw':
        return '🏦'
    if transaction.transaction_type == 'dividend':
        return '💸'
    if not transaction.asset:
        return '📊'
    if transaction.asset.category == 'mineral':
        return '💎'
    return '📈'
# ============= CRYPTO DEPOSIT VIEWS =============

@login_required
def deposit_crypto_select(request):
    """Step 1: Select cryptocurrency and enter amount"""
    cryptos = CryptoCurrency.objects.filter(is_active=True)
    
    if request.method == 'POST':
        crypto_id = request.POST.get('crypto_id')
        usd_amount = Decimal(request.POST.get('usd_amount', 0))
        
        crypto = get_object_or_404(CryptoCurrency, id=crypto_id, is_active=True)
        
        if usd_amount < crypto.min_deposit_usd:
            messages.error(request, f"Minimum deposit is ${crypto.min_deposit_usd:,.2f}")
            return redirect('deposit_crypto_select')
        
        if usd_amount > crypto.max_deposit_usd:
            messages.error(request, f"Maximum deposit is ${crypto.max_deposit_usd:,.2f}")
            return redirect('deposit_crypto_select')
        
        # Calculate crypto amount
        crypto_amount = usd_amount / crypto.rate_usd
        
        # Create deposit request
        deposit = CryptoDeposit.objects.create(
            user=request.user,
            crypto=crypto,
            usd_amount=usd_amount,
            crypto_amount=crypto_amount,
            rate_used=crypto.rate_usd,
            wallet_address=crypto.wallet_address,
            status='pending'
        )
        
        # Generate QR code
        deposit.generate_qr_code()
        deposit.save()
        
        return redirect('deposit_crypto_pay', deposit_id=deposit.id)
    
    context = {
        'cryptos': cryptos,
    }
    return render(request, 'core/dashboard/deposit_crypto_select.html', context)


@login_required
def deposit_crypto_pay(request, deposit_id):
    """Step 2: Show QR code and payment details"""
    deposit = get_object_or_404(CryptoDeposit, id=deposit_id, user=request.user)
    
    # Check if expired
    if deposit.is_expired() and deposit.status == 'pending':
        deposit.status = 'expired'
        deposit.save()
        messages.warning(request, "This deposit request has expired. Please create a new one.")
        return redirect('deposit_crypto_select')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'cancel':
            deposit.status = 'cancelled'
            deposit.save()
            messages.info(request, "Deposit cancelled.")
            return redirect('dashboard')
        
        elif action == 'confirm_payment':
            deposit.status = 'paid'
            deposit.confirmed_at = timezone.now()
            deposit.save()
            
            # Create notification for user
            Notification.objects.create(
                user=deposit.user,
                title="Deposit Payment Confirmed",
                message=f"Your deposit of ${deposit.usd_amount:,.2f} has been confirmed. Waiting for admin verification.",
                notification_type='deposit'
            )
            
            messages.success(request, "Payment confirmation received! Our team will verify and credit your account shortly.")
            return redirect('dashboard')
    
    context = {
        'deposit': deposit,
        'time_remaining': deposit.get_time_remaining(),
    }
    return render(request, 'core/dashboard/deposit_crypto_pay.html', context)


@login_required
def deposit_crypto_status(request, deposit_id):
    """AJAX endpoint to check deposit status and time remaining"""
    deposit = get_object_or_404(CryptoDeposit, id=deposit_id, user=request.user)
    
    return JsonResponse({
        'status': deposit.status,
        'time_remaining': deposit.get_time_remaining(),
        'is_expired': deposit.is_expired(),
        'usd_amount': float(deposit.usd_amount),
        'crypto_amount': float(deposit.crypto_amount),
        'crypto_symbol': deposit.crypto.symbol,
    })

def deposit(request):
    """Step 1: Select currency and enter amount"""
    cryptos = CryptoCurrency.objects.filter(is_active=True)
    
    if request.method == 'POST':
        crypto_id = request.POST.get('crypto_id')
        amount = request.POST.get('usd_amount')
        
        if crypto_id and amount:
            request.session['deposit_crypto_id'] = crypto_id
            request.session['deposit_amount'] = float(amount)
            
            return redirect('deposit_billing')
    
    context = {'cryptos': cryptos}
    return render(request, 'core/dashboard/deposit.html', context)


@login_required
def deposit_billing(request):
    """Step 2: Billing details"""
    # Get data from session
    amount = request.session.get('deposit_amount')
    crypto_id = request.session.get('deposit_crypto_id')
    network = request.session.get('deposit_network')
    
    if not amount or not crypto_id:
        messages.error(request, "Please start a new deposit.")
        return redirect('deposit')
    
    if request.method == 'POST':
        # Save billing info to session
        request.session['billing_name'] = request.POST.get('full_name')
        request.session['billing_email'] = request.POST.get('email')
        request.session['billing_phone'] = request.POST.get('phone')
        request.session['billing_country'] = request.POST.get('country')
        
        return redirect('deposit_payment')
    
    cryptos = CryptoCurrency.objects.filter(is_active=True)
    
    context = {
        'cryptos': cryptos,
        'deposit_amount': amount,
        'deposit_crypto_id': crypto_id,
        'deposit_network': network,
    }
    return render(request, 'core/dashboard/deposit_billing.html', context)


@login_required
def deposit_payment(request):
    """Step 3: QR code and payment"""
    
    # Get data from session
    amount = request.session.get('deposit_amount')
    crypto_id = request.session.get('deposit_crypto_id')
    network = request.session.get('deposit_network')
    
    # Handle POST request (when user confirms payment)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'confirm_payment':
            try:
                from decimal import Decimal
                from django.utils import timezone
                from datetime import timedelta
                from django.db import transaction as db_transaction
                from .models import CryptoCurrency, CryptoDeposit, Transaction
                from .utils.email_utils import send_deposit_confirmation_email
                
                # Get the crypto
                selected_crypto = CryptoCurrency.objects.get(id=crypto_id)
                
                with db_transaction.atomic():
                    # Calculate crypto amount
                    crypto_amount = Decimal(str(amount)) / selected_crypto.rate_usd
                    
                    # Create the deposit record
                    deposit = CryptoDeposit.objects.create(
                        user=request.user,
                        crypto=selected_crypto,
                        usd_amount=Decimal(str(amount)),
                        crypto_amount=crypto_amount,
                        rate_used=selected_crypto.rate_usd,
                        wallet_address=selected_crypto.wallet_address,
                        status='paid',
                        confirmed_at=timezone.now(),
                        expires_at=timezone.now() + timedelta(minutes=20)
                    )
                    
                    # Send email confirmation
                    send_deposit_confirmation_email(request.user, deposit)
                    
                    # Create notification for user
                    Notification.objects.create(
                        user=request.user,
                        title="Deposit Initiated 💰",
                        message=f"Your deposit of ${deposit.usd_amount:,.2f} has been submitted and is pending admin verification.",
                        notification_type='deposit',
                        is_read=False
                    )
                    
                    # CREATE TRANSACTION RECORD for Recent Activity
                    Transaction.objects.create(
                        user=request.user,
                        transaction_type='deposit',
                        total_amount=Decimal(str(amount)),
                        status='pending',  # Pending admin approval
                        notes=f"Crypto deposit: {crypto_amount:.8f} {selected_crypto.symbol}"
                    )
                    
                    # Clear session data
                    request.session.pop('deposit_amount', None)
                    request.session.pop('deposit_crypto_id', None)
                    request.session.pop('deposit_network', None)
                    request.session.pop('billing_name', None)
                    request.session.pop('billing_email', None)
                    request.session.pop('billing_phone', None)
                    request.session.pop('billing_country', None)
                    
                    messages.success(request, f"Payment confirmation received! Your deposit of ${amount:,.2f} is pending admin verification.")
                    
                    return redirect('dashboard')
                    
            except Exception as e:
                print(f"Error creating deposit: {e}")
                messages.error(request, f"Error processing deposit: {str(e)}")
                return redirect('dashboard')
    
    # For GET request - show the payment page
    if not amount or not crypto_id:
        messages.error(request, "Please start a new deposit.")
        return redirect('deposit')
    
    # Get cryptocurrencies for the template
    from .models import CryptoCurrency
    all_cryptos = CryptoCurrency.objects.filter(is_active=True)
    
    context = {
        'cryptos': all_cryptos,
        'deposit_amount': amount,
        'deposit_crypto_id': crypto_id,
        'deposit_network': network,
    }
    return render(request, 'core/dashboard/deposit_payment.html', context)
    

@login_required
def holdings(request):
    """View to show all user holdings including real estate"""
    portfolio = request.user.portfolio
    holdings = portfolio.holdings.select_related('asset').all()
    
    holdings_data = []
    for holding in holdings:
        # Add effective values to each holding
        holding.effective_purchase_date = holding.get_effective_purchase_date()
        holding.effective_quantity = holding.get_effective_quantity()
        holding.effective_average_price = holding.get_effective_average_price()
        
        holdings_data.append({
            'holding': holding,
            'current_value': holding.current_value(),
            'profit_loss': holding.unrealized_pl(),
            'profit_percent': holding.profit_percent(),
            'effective_quantity': holding.effective_quantity,
            'effective_average_price': holding.effective_average_price,
            'effective_purchase_date': holding.effective_purchase_date,
        })
    
    # Get real estate investments
    from .models import RealEstateInvestment
    real_estate_investments = RealEstateInvestment.objects.filter(user=request.user).select_related('property')
    
    # Calculate total dividends for each real estate investment
    for inv in real_estate_investments:
        inv.total_dividends = sum(d.amount for d in inv.dividends.all())
    
    total_value = sum(h['current_value'] for h in holdings_data) + sum(inv.amount_invested for inv in real_estate_investments)
    total_unrealized_pl = sum(h['profit_loss'] for h in holdings_data)
    
    context = {
        'holdings': holdings_data,
        'real_estate_investments': real_estate_investments,
        'total_value': total_value,
        'total_unrealized_pl': total_unrealized_pl,
        'now': timezone.now(),
    }
    return render(request, 'core/dashboard/holdings.html', context)       

from .models import PhysicalProduct, PhysicalHolding, PhysicalTransaction

from .models import PhysicalCart, PhysicalCartItem

@login_required
def physical_investments(request):
    """Physical investments marketplace page"""
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    from decimal import Decimal
 
    products = PhysicalProduct.objects.filter(is_active=True)
 
    # Get or create cart
    cart, created = PhysicalCart.objects.get_or_create(user=request.user)
 
    # ── CONFIRMED holdings only ──────────────────────────────────────────────
    # PhysicalHolding records are only created by the admin when they confirm
    # a transaction, so this queryset naturally excludes pending transactions.
    holdings = PhysicalHolding.objects.filter(
        user=request.user
    ).select_related('product', 'transaction').order_by('-id')
 
    # ========== ADD EFFECTIVE VALUES TO EACH HOLDING ==========
    for holding in holdings:
        holding.effective_purchase_date = holding.get_effective_purchase_date()
        holding.effective_quantity = holding.get_effective_quantity()
        holding.effective_current_value = holding.get_effective_current_value()
    # ============================================================
 
    # Count by type
    vaulted_count = holdings.filter(service_type='vault').count()
    shipped_count = holdings.filter(service_type='shipped').count()
 
    # ── Total value = sum of current_value() for confirmed holdings ONLY ────
    # While an asset is under_review there is no PhysicalHolding record yet,
    # so total_value stays $0 until admin confirms.
    total_value = sum(h.current_value() for h in holdings)
 
    # ── All transactions for the Transactions tab ────────────────────────────
    all_user_transactions = PhysicalTransaction.objects.filter(
        user=request.user
    ).order_by('-created_at')
 
    # ========== ADD EFFECTIVE VALUES TO TRANSACTIONS ==========
    for tx in all_user_transactions:
        tx.effective_created_at = tx.get_effective_created_at()
        tx.effective_total_amount = tx.get_effective_total_amount()
    # ============================================================
 
    # Pending = under admin review (no holding created yet)
    pending_transactions = all_user_transactions.filter(status='under_review')
 
    # Other statuses for the admin-facing sections (kept for compatibility)
    processing_transactions = all_user_transactions.filter(status='confirmed_processing')
    vault_transactions      = all_user_transactions.filter(status='confirmed_vault')
    shipped_transactions    = all_user_transactions.filter(status='shipped')
    delivered_transactions  = all_user_transactions.filter(status='delivered')
    cancelled_transactions  = all_user_transactions.filter(status='cancelled')
 
    # ── Products JSON (for any JS that needs it) ─────────────────────────────
    products_json = json.dumps([{
        'id':              p.id,
        'name':            p.name,
        'year':            p.year or '',
        'category':        p.category,
        'specification':   p.specification,
        'current_price':   float(p.current_price),
        'spot_price':      float(p.spot_price),
        'price_change_24h':float(p.price_change_24h),
        'shipping_fee':    float(p.shipping_fee),
        'purity':          p.purity,
        'weight':          p.weight,
        'mint':            p.mint,
        'dimensions':      p.dimensions or 'N/A',
        'main_image':      p.main_image.url if p.main_image else None,
        'stock_quantity':  p.stock_quantity,
    } for p in products], cls=DjangoJSONEncoder)
 
    context = {
        'products':                 products,
        'holdings':                 holdings,
        'total_value':              total_value,      # ← confirmed holdings only
        'vaulted_count':            vaulted_count,    # ← 0 until admin confirms
        'shipped_count':            shipped_count,    # ← 0 until admin confirms
        'all_transactions':         all_user_transactions,
        'pending_transactions':     pending_transactions,
        'processing_transactions':  processing_transactions,
        'vault_transactions':       vault_transactions,
        'shipped_transactions':     shipped_transactions,
        'delivered_transactions':   delivered_transactions,
        'cancelled_transactions':   cancelled_transactions,
        'cart':                     cart,
        'cart_items':               cart.items.all(),
        'cart_total':               cart.get_total(),
        'cart_count':               cart.get_item_count(),
        'products_json':            products_json,
    }
    return render(request, 'core/physical_investments.html', context)

@login_required
@require_POST
def physical_add_to_cart(request, product_id):
    """Add product to cart"""
    product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
    quantity = int(request.POST.get('quantity', 1))
    
    cart, created = PhysicalCart.objects.get_or_create(user=request.user)
    
    cart_item, created = PhysicalCartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    return JsonResponse({
        'success': True,
        'cart_count': cart.get_item_count(),
        'cart_total': float(cart.get_total()),
        'message': f'{product.name} added to cart'
    })


@login_required
def physical_cart(request):
    """View cart page"""
    cart = PhysicalCart.objects.get_or_create(user=request.user)[0]
    items = cart.items.select_related('product').all()
    
    context = {
        'cart': cart,
        'items': items,
        'total': cart.get_total(),
        'item_count': cart.get_item_count(),
    }
    return render(request, 'core/physical_cart.html', context)


@login_required
@require_POST
def physical_update_cart(request, item_id):
    """Update cart item quantity"""
    cart_item = get_object_or_404(PhysicalCartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity <= 0:
        cart_item.delete()
    else:
        cart_item.quantity = quantity
        cart_item.save()
    
    cart = cart_item.cart
    return JsonResponse({
        'success': True,
        'cart_count': cart.get_item_count(),
        'cart_total': float(cart.get_total()),
        'item_subtotal': float(cart_item.get_subtotal()) if cart_item.id else 0,
    })


@login_required
@require_POST
def physical_remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart_item = get_object_or_404(PhysicalCartItem, id=item_id, cart__user=request.user)
    cart = cart_item.cart
    cart_item.delete()
    
    return JsonResponse({
        'success': True,
        'cart_count': cart.get_item_count(),
        'cart_total': float(cart.get_total()),
    })


@login_required
def physical_checkout(request):
    """Checkout page - choose delivery method"""
    cart = get_object_or_404(PhysicalCart, user=request.user)
    items = cart.items.select_related('product').all()
    
    if not items.exists():
        messages.error(request, "Your cart is empty")
        return redirect('physical_investments')
    
    # Clear any old session data first
    request.session.pop('checkout_delivery_method', None)
    request.session.pop('shipping_cost', None)
    request.session.pop('shipping_address', None)
    
    subtotal = cart.get_total()
    
    # Build cart_items list FIRST (before the if/else)
    cart_items = []
    for item in items:
        cart_items.append({
            'product_id': item.product.id,
            'product_name': item.product.name,
            'product_spec': item.product.specification,
            'product_image': item.product.main_image.url if item.product.main_image else None,
            'quantity': int(item.quantity),
            'price': float(item.product.current_price),
            'subtotal': float(item.get_subtotal()),
        })
    
    if request.method == 'POST':
        delivery_method = request.POST.get('delivery_method')
        
        # Store delivery method in session
        request.session['checkout_delivery_method'] = delivery_method
        request.session['cart_subtotal'] = float(subtotal)
        
        if delivery_method == 'vault':
            # Store cart items in session for vault
            request.session['checkout_cart_items'] = cart_items
            request.session['checkout_subtotal'] = float(subtotal)
            
            # Redirect to vault confirmation page
            return redirect('physical_checkout_vault_confirm_first')
        else:
            # For shipping from cart with multiple items
            # Store in session that this is a cart checkout
            request.session['checkout_from_cart'] = True
            request.session['checkout_cart_items'] = cart_items
            request.session['checkout_cart_subtotal'] = float(subtotal)
            
            # Redirect to shipping info page - use the first product's ID for the URL
            first_item = items.first()
            return redirect('physical_checkout_shipping', product_id=first_item.product.id)
    
    context = {
        'cart': cart,
        'items': items,
        'subtotal': subtotal,
        'shipping_fee': 0,
        'total': subtotal,
        'cart_count': cart.get_item_count(),
        'item_count': cart.get_item_count(),
        'delivery_method': request.session.get('checkout_delivery_method', 'vault'),
    }
    return render(request, 'core/physical_checkout.html', context)

@login_required
def physical_checkout_vault_info(request):
    """Vault storage information page"""
    delivery_method = request.session.get('checkout_delivery_method')
    if delivery_method != 'vault':
        return redirect('physical_checkout')
    
    if request.method == 'POST':
        # Store vault preference
        request.session['vault_agreed'] = True
        return redirect('physical_payment')
    
    context = {
        'vault_location': 'Zurich, Switzerland',
        'vault_features': [
            '24/7 armed security and surveillance',
            'Fully insured up to full market value',
            'Instant liquidation - sell anytime',
            'Audited annually by PwC',
            'Temperature-controlled storage',
            'Private vault access by appointment',
        ],
        'vault_fees': 'No storage fees for first year, then 0.5% annually',
    }
    return render(request, 'core/physical_checkout_vault.html', context)


@login_required
def physical_checkout_shipping_info(request, product_id):
    """Shipping information page - handles both single product AND cart checkout"""
    
    # Check if this is from cart checkout
    from_cart = request.session.get('checkout_from_cart', False)
    cart_items = request.session.get('checkout_cart_items', [])
    
    if from_cart and cart_items:
        # CART CHECKOUT - multiple items
        # Get the first product for display
        product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
        
        # Calculate total subtotal from all cart items
        # RECALCULATE from cart_items to ensure accuracy
        subtotal = 0
        for item in cart_items:
            subtotal += item.get('subtotal', 0)
        
        # Also check session value as backup
        session_subtotal = request.session.get('checkout_cart_subtotal', 0)
        if subtotal == 0 and session_subtotal > 0:
            subtotal = session_subtotal
        
        quantity = 1  # dummy value, will show all items in template
        
        print("=" * 60)
        print("SHIPPING INFO PAGE - CART CHECKOUT")
        print(f"Number of items: {len(cart_items)}")
        print(f"Recalculated Subtotal: ${subtotal}")
        print(f"Session Subtotal: ${session_subtotal}")
        print("=" * 60)
        
        context = {
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal,
            'is_cart_checkout': True,
            'cart_items': cart_items,
        }
        return render(request, 'core/physical_checkout_shipping.html', context)
    
    else:
        # SINGLE PRODUCT - direct purchase
        product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
        quantity = int(request.GET.get('quantity', 1))
        subtotal = float(product.current_price) * quantity
        
        print("=" * 60)
        print("SHIPPING INFO PAGE - DIRECT PURCHASE")
        print(f"Product: {product.name}")
        print(f"Quantity: {quantity}")
        print(f"Subtotal: ${subtotal}")
        print("=" * 60)
        
        context = {
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal,
            'is_cart_checkout': False,
        }
        return render(request, 'core/physical_checkout_shipping.html', context)
@login_required
def physical_checkout_shipping_info_confirm(request):
    """Shipping confirmation and delivery details page"""
    shipping_address = request.session.get('shipping_address')
    if not shipping_address:
        return redirect('physical_checkout')
    
    cart_total = request.session.get('checkout_cart_total', 0)
    shipping_fee = 25  # Standard shipping fee
    
    if request.method == 'POST':
        request.session['shipping_agreed'] = True
        return redirect('physical_payment')
    
    from datetime import date, timedelta
    estimated_delivery = date.today() + timedelta(days=7)
    
    context = {
        'shipping_address': shipping_address,
        'cart_total': cart_total,
        'shipping_fee': shipping_fee,
        'total': cart_total + shipping_fee,
        'estimated_delivery': estimated_delivery,
        'delivery_timeline': [
            'Order confirmed within 24 hours',
            'Processing: 1-2 business days',
            'Shipping: 3-5 business days',
            'Delivery: 7-10 business days total',
        ],
    }
    return render(request, 'core/physical_checkout_shipping_confirm.html', context)


@login_required
def physical_payment(request):
    """Payment page - handles both single product AND multiple cart items"""
    
    # Check if this is from cart with multiple items
    cart_items = request.session.get('checkout_all_items', [])
    
    if cart_items:
        # MULTIPLE ITEMS FROM CART
        subtotal = request.session.get('checkout_total_amount', 0)
        shipping_cost = request.session.get('shipping_cost', 0)
        delivery_method = request.session.get('payment_delivery_method', 'vault')
        
        print("=" * 60)
        print("PAYMENT PAGE - MULTIPLE ITEMS FROM CART")
        print(f"Number of items: {len(cart_items)}")
        print(f"Subtotal: ${subtotal}")
        print(f"Shipping: ${shipping_cost}")
        print(f"Total: ${subtotal + shipping_cost}")
        print("=" * 60)
        
        # Get first product for display (or you can show all)
        first_item = cart_items[0]
        product = get_object_or_404(PhysicalProduct, id=first_item['product_id'], is_active=True)
        quantity = first_item['quantity']
        
        # Store all items in session for payment confirmation
        request.session['payment_cart_items'] = cart_items
        request.session['payment_cart_total'] = subtotal + shipping_cost
        
        context = {
            'product': product,  # First product for display
            'quantity': quantity,
            'cart_items': cart_items,  # All items for template
            'subtotal': subtotal,
            'shipping_fee': shipping_cost,
            'total': subtotal + shipping_cost,
            'delivery_method': delivery_method,
            'delivery_method_display': 'Qubix Vault Storage' if delivery_method == 'vault' else 'Ship to Address',
            'is_cart_checkout': True,
        }
        return render(request, 'core/physical_payment.html', context)
    
    else:
        # SINGLE PRODUCT - direct purchase
        product_id = request.session.get('payment_product_id')
        quantity = request.session.get('payment_quantity', 1)
        shipping_cost = request.session.get('shipping_cost', 0)
        delivery_method = request.session.get('payment_delivery_method', 'vault')
        
        print("=" * 60)
        print("PAYMENT PAGE - SINGLE PRODUCT")
        print(f"Product ID from session: {product_id}")
        print(f"Quantity: {quantity}")
        print("=" * 60)
        
        if not product_id:
            messages.error(request, "No product selected. Please start over.")
            return redirect('physical_investments')
        
        product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
        
        if delivery_method == 'vault':
            shipping_cost = 0
        
        subtotal = float(product.current_price) * quantity
        total = subtotal + shipping_cost
        
        context = {
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal,
            'shipping_fee': shipping_cost,
            'total': total,
            'delivery_method': delivery_method,
            'delivery_method_display': 'Qubix Vault Storage' if delivery_method == 'vault' else 'Ship to Address',
            'is_cart_checkout': False,
        }
        return render(request, 'core/physical_payment.html', context)

@login_required
@require_POST
def physical_confirm_payment(request):
    """Confirm crypto payment - PENDING admin review"""
    import json
    from decimal import Decimal
    
    try:
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except:
                data = request.POST.dict()
        else:
            data = request.POST.dict()
        
        transaction_id = data.get('transaction_id')
        
        print("=== PHYSICAL CONFIRM PAYMENT ===")
        print(f"Content Type: {request.content_type}")
        print(f"Data received: {data}")
        print(f"Transaction ID: {transaction_id}")
        
        # Check if this is a delivery fee payment
        pending_delivery = request.session.get('pending_delivery_payment')
        
        if pending_delivery:
            print("Processing delivery fee payment - Creating ONE transaction")
            
            holding = get_object_or_404(PhysicalHolding, id=pending_delivery['holding_id'], user=request.user)
            
            # Get the actual crypto currency used
            crypto_used = pending_delivery.get('payment_method', 'BTC')
            
            # Create ONLY ONE transaction for delivery fees
            transaction = PhysicalTransaction.objects.create(
                user=request.user,
                product=holding.product,
                quantity=holding.quantity,
                total_amount=Decimal(str(pending_delivery['total_fees'])),
                shipping_fee=Decimal(str(pending_delivery['shipping_fee'])),
                delivery_method='shipping',
                payment_method='delivery_fee',
                crypto_currency_used=crypto_used,
                shipping_address=pending_delivery['shipping_address'],
                status='under_review',
            )
            
            # Update holding status
            holding.delivery_status = 'pending_delivery'
            holding.save()
            
            # Send notification to admin
            Notification.objects.create(
                user=None,
                title="Delivery Fee Payment - Awaiting Review",
                message=f"User {request.user.email} has paid delivery fees for {holding.quantity} x {holding.product.name}. Transaction #{transaction.id}",
                notification_type='admin_alert',
                is_read=False
            )
            
            # Clear session
            request.session.pop('pending_delivery_payment', None)
            request.session.pop('delivery_request', None)
            
            return JsonResponse({
                'success': True,
                'message': 'Delivery fees paid! Our team will review and process your shipment.',
                'transaction_id': transaction.id,
            })
        
               # ========== SELL FEE CHECK - CORRECTLY PLACED ==========
        # Check if this is a sell fee payment
        pending_sell = request.session.get('pending_sell_payment')
        
        if pending_sell:
            print("Processing sell fee payment - Creating sell request")
            
            holding = get_object_or_404(PhysicalHolding, id=pending_sell['holding_id'], user=request.user)
            
            # Get the actual crypto currency used
            crypto_used = pending_sell.get('payment_method', 'BTC')
            
            # Create a sell transaction record
            sell_transaction = PhysicalTransaction.objects.create(
                user=request.user,
                product=holding.product,
                quantity=holding.quantity,
                total_amount=Decimal(str(pending_sell['current_value'])),
                shipping_fee=Decimal('0'),
                delivery_method='sell',
                payment_method='sell_fee',
                crypto_currency_used=crypto_used,
                shipping_address={'wallet_address': pending_sell['wallet_address'], 'crypto_currency': pending_sell['crypto_currency']},
                status='under_review',
                payment_confirmed_at=timezone.now(),
            )
            
            # Mark holding as pending sell
            holding.delivery_status = 'pending_sell'
            holding.save()
            
            # ========== SEND EMAIL TO USER ==========
            send_physical_payment_received_email(request.user, sell_transaction)
            # ========================================
            
            # ========== CREATE NOTIFICATION FOR USER ==========
            Notification.objects.create(
                user=request.user,
                title="Sell Request Submitted",
                message=f"Your request to sell {holding.quantity} x {holding.product.name} has been submitted. Our team will review and process your sale.",
                notification_type='shop',
                is_read=False
            )
            # ===================================================
            
            # Send notification to admin
            Notification.objects.create(
                user=None,
                title="Sell Request - Awaiting Review",
                message=f"User {request.user.email} requested to sell {holding.quantity} x {holding.product.name} for ${pending_sell['net_payout']:,.2f} (after fees). Wallet: {pending_sell['wallet_address']}",
                notification_type='admin_alert',
                is_read=False
            )
            
            # Clear session
            request.session.pop('pending_sell_payment', None)
            request.session.pop('pending_sell_request', None)
            
            return JsonResponse({
                'success': True,
                'message': 'Sell request submitted! Our team will review and process your sale.',
                'transaction_id': sell_transaction.id,
            })
        # ========== END OF SELL FEE CHECK ==========
        
        elif transaction_id and transaction_id != '' and transaction_id != 'None' and transaction_id != 'null':
            print(f"Processing existing transaction ID: {transaction_id}")
            try:
                transaction = PhysicalTransaction.objects.get(id=transaction_id, user=request.user)
            except PhysicalTransaction.DoesNotExist:
                return JsonResponse({'error': 'Transaction not found'}, status=400)
            
            if transaction.status == 'under_review':
                # DO NOT auto-approve - mark payment as received, keep under_review
                transaction.payment_confirmed_at = timezone.now()
                transaction.save()
                
                # Send notification to admin about payment
                Notification.objects.create(
                    user=None,
                    title="Payment Received - Awaiting Verification",
                    message=f"User {request.user.email} has made payment for order #{transaction_id}. Please verify and confirm.",
                    notification_type='admin_alert',
                    is_read=False
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment recorded! Our team will verify your payment and confirm your order.',
                    'transaction_id': transaction.id,
                })
            
            return JsonResponse({'error': 'Already processed'}, status=400)
        
        else:
            # NEW ORDER - Check if this is from cart with multiple items
            cart_items = request.session.get('payment_cart_items', [])
            
            if cart_items:
                # MULTIPLE ITEMS FROM CART
                print("=" * 60)
                print("Processing MULTIPLE items from cart")
                print(f"Number of items: {len(cart_items)}")
                print("=" * 60)
                
                transactions = []
                delivery_method = request.session.get('payment_delivery_method', 'vault')
                payment_method = request.session.get('payment_method', 'BTC')
                shipping_address = request.session.get('shipping_address', {})
                shipping_cost = Decimal(str(request.session.get('shipping_cost', 0)))
                
                for item in cart_items:
                    try:
                        product = PhysicalProduct.objects.get(id=item['product_id'], is_active=True)
                        quantity = Decimal(str(item['quantity']))
                        subtotal = Decimal(str(item['subtotal']))
                        
                        # For vault, shipping fee is 0
                        if delivery_method == 'vault':
                            item_shipping = Decimal('0')
                        else:
                            # Split shipping cost proportionally among items
                            total_subtotal = Decimal(str(request.session.get('checkout_total_amount', 0)))
                            if total_subtotal > 0:
                                item_shipping = shipping_cost * (subtotal / total_subtotal)
                            else:
                                item_shipping = Decimal('0')
                        
                        total_amount = subtotal + item_shipping
                        
                        transaction = PhysicalTransaction.objects.create(
                            user=request.user,
                            product=product,
                            quantity=quantity,
                            total_amount=total_amount,
                            shipping_fee=item_shipping,
                            delivery_method=delivery_method,
                            payment_method=payment_method,
                            shipping_address=shipping_address,
                            status='under_review',
                            payment_confirmed_at=timezone.now(),
                        )
                        transactions.append(transaction)
                        print(f"  ✓ Created transaction for {product.name}: ${total_amount}")
                        
                    except Exception as e:
                        print(f"Error creating transaction for item: {e}")
                        continue
                
                if transactions:
                    # ========== ADD EMAILS AND NOTIFICATIONS FOR CART ITEMS ==========
                    for transaction in transactions:
                        # Send email to user
                        send_physical_payment_received_email(request.user, transaction)
                        
                        # Create notification for user
                        Notification.objects.create(
                            user=request.user,
                            title="Payment Received - Order Under Review",
                            message=f"Your payment for {transaction.quantity} x {transaction.product.name} has been received. Our team will review and confirm your order.",
                            notification_type='shop',
                            is_read=False
                        )
                    # ================================================================
                    
                    # Clear cart
                    try:
                        cart = PhysicalCart.objects.filter(user=request.user).first()
                        if cart:
                            cart.items.all().delete()
                            print("Cart cleared")
                    except Exception as e:
                        print(f"Error clearing cart: {e}")
                    
                    # Clear all session data
                    request.session.pop('payment_cart_items', None)
                    request.session.pop('checkout_all_items', None)
                    request.session.pop('checkout_cart_items', None)
                    request.session.pop('checkout_subtotal', None)
                    request.session.pop('checkout_total_amount', None)
                    request.session.pop('pending_payment_details', None)
                    request.session.pop('checkout_delivery_method', None)
                    request.session.pop('shipping_address', None)
                    request.session.pop('shipping_cost', None)
                    request.session.pop('payment_method', None)
                    request.session.pop('cart_subtotal', None)
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'Payment recorded for {len(transactions)} item(s)! Our team will verify your payment.',
                        'transaction_ids': [tx.id for tx in transactions],
                    })
                else:
                    return JsonResponse({'error': 'No transactions were created'}, status=400)
            
            else:
                # SINGLE ITEM - existing code for direct purchase
                pending_details_str = request.session.get('pending_payment_details')
                
                print(f"Pending details from session: {pending_details_str}")
                
                if not pending_details_str:
                    return JsonResponse({'error': 'No pending payment found in session'}, status=400)
                
                # Parse the JSON string
                try:
                    if isinstance(pending_details_str, str):
                        pending_details = json.loads(pending_details_str)
                    else:
                        pending_details = pending_details_str
                except json.JSONDecodeError as e:
                    return JsonResponse({'error': f'Invalid JSON: {str(e)}'}, status=400)
                
                if isinstance(pending_details, dict):
                    pending_details = [pending_details]
                
                transactions = []
                for pending in pending_details:
                    if 'product_id' not in pending:
                        continue
                    
                    try:
                        product = PhysicalProduct.objects.get(id=pending['product_id'], is_active=True)
                    except PhysicalProduct.DoesNotExist:
                        continue
                    
                    total_amount = Decimal(str(pending.get('total', 0)))
                    if total_amount == 0:
                        subtotal = Decimal(str(pending.get('subtotal', 0)))
                        shipping_fee = Decimal(str(pending.get('shipping_fee', 0)))
                        total_amount = subtotal + shipping_fee
                    
                    quantity = Decimal(str(pending.get('quantity', 1)))
                    shipping_fee = Decimal(str(pending.get('shipping_fee', 0)))
                    delivery_method = pending.get('delivery_method', 'vault')
                    payment_method = pending.get('payment_method', 'BTC')
                    shipping_address = pending.get('shipping_address', {})
                    
                    if delivery_method == 'vault':
                        shipping_fee = Decimal('0')
                    
                    transaction = PhysicalTransaction.objects.create(
                        user=request.user,
                        product=product,
                        quantity=quantity,
                        total_amount=total_amount,
                        shipping_fee=shipping_fee,
                        delivery_method=delivery_method,
                        payment_method=payment_method,
                        shipping_address=shipping_address,
                        status='under_review',
                        payment_confirmed_at=timezone.now(),
                    )
                    transactions.append(transaction)
                
                if not transactions:
                    return JsonResponse({'error': 'No transactions were created'}, status=400)
                
                # ========== ADD EMAILS AND NOTIFICATIONS FOR SINGLE ITEMS ==========
                for transaction in transactions:
                    # Send email to user
                    send_physical_payment_received_email(request.user, transaction)
                    
                    # Create notification for user
                    Notification.objects.create(
                        user=request.user,
                        title="Payment Received - Order Under Review",
                        message=f"Your payment for {transaction.quantity} x {transaction.product.name} has been received. Our team will review and confirm your order.",
                        notification_type='shop',
                        is_read=False
                    )
                # ====================================================================
                
                # Send notifications to admin (keep existing)
                for transaction in transactions:
                    Notification.objects.create(
                        user=None,
                        title="New Order - Awaiting Verification",
                        message=f"User {request.user.email} has placed a new order for {transaction.quantity} x {transaction.product.name} worth ${transaction.total_amount}. Please verify payment.",
                        notification_type='admin_alert',
                        is_read=False
                    )
                
                # Clear cart
                try:
                    cart = PhysicalCart.objects.filter(user=request.user).first()
                    if cart:
                        cart.items.all().delete()
                except Exception as e:
                    print(f"Error clearing cart: {e}")
                
                # Clear session
                request.session.pop('pending_payment_details', None)
                request.session.pop('checkout_delivery_method', None)
                request.session.pop('shipping_address', None)
                request.session.pop('shipping_cost', None)
                request.session.pop('payment_method', None)
                request.session.pop('cart_subtotal', None)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Payment recorded! Our team will verify your payment and confirm your order(s).',
                    'transaction_ids': [tx.id for tx in transactions],
                })

    except Exception as e:
        print(f"Error in physical_confirm_payment: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def physical_product_detail(request, product_id):
    """API endpoint for product details"""
    try:
        product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
        
        # Convert all Decimal values to float for JSON serialization
        data = {
            'id': product.id,
            'name': product.name,
            'year': product.year or '',
            'category': product.category,
            'specification': product.specification,
            'purity': product.purity,
            'weight': product.weight,
            'mint': product.mint,
            'dimensions': product.dimensions or 'N/A',
            'current_price': float(product.current_price),
            'spot_price': float(product.spot_price),
            'price_change_24h': float(product.price_change_24h),
            'shipping_fee': float(product.shipping_fee),
            'stock_quantity': product.stock_quantity,
            'premium_percent': float(product.get_premium_percent()),  # Convert to float
        }
        
        # Add main image if exists
        if product.main_image and product.main_image.url:
            data['main_image'] = product.main_image.url
        
        return JsonResponse(data)
        
    except Exception as e:
        print(f"Error in physical_product_detail: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def physical_purchase(request, product_id):
    """Handle physical product purchase"""
    from decimal import Decimal
    
    product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
    
    try:
        data = json.loads(request.body)
        quantity = Decimal(str(data.get('quantity', 1)))
        service_type = data.get('service_type', 'vault')
        shipping_address = data.get('shipping_address', {})
        payment_method = data.get('payment_method', 'BTC')
        
        # Check stock
        if quantity > product.stock_quantity:
            return JsonResponse({'error': 'Insufficient stock'}, status=400)
        
        # Calculate total
        total = product.current_price * quantity
        if service_type == 'shipped':
            total += product.shipping_fee * quantity
        
        # Check user balance (if needed)
        if total > request.user.portfolio.cash_balance:
            return JsonResponse({'error': 'Insufficient funds'}, status=400)
        
        # Create transaction
        transaction = PhysicalTransaction.objects.create(
            user=request.user,
            product=product,
            quantity=quantity,
            total_amount=total,
            shipping_fee=product.shipping_fee if service_type == 'shipped' else 0,
            delivery_method=service_type,  # Changed: service_type -> delivery_method
            payment_method=payment_method,
            shipping_address=shipping_address,
            status='under_review'  # Changed: pending -> pending_payment
        )
        
        # Generate crypto payment details
        crypto_rates = {
            'BTC': 63800,
            'ETH': 3420,
            'USDT': 1,
            'LTC': 88
        }
        
        crypto_amount = total / crypto_rates.get(payment_method, 1)
        
        return JsonResponse({
            'success': True,
            'transaction_id': transaction.id,
            'crypto_amount': float(crypto_amount),
            'crypto_currency': payment_method,
            'wallet_address': get_wallet_address_from_db(payment_method),  
            'expires_in': 900  # 15 minutes
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def get_wallet_address_from_db(currency_code):
    """Get wallet address from CryptoCurrency model (admin configured)"""
    try:
        # Map currency code to symbol in your CryptoCurrency model
        # Your CryptoCurrency model uses 'symbol' field like 'BTC', 'ETH', etc.
        crypto = CryptoCurrency.objects.filter(symbol=currency_code, is_active=True).first()
        if crypto and crypto.wallet_address:
            return crypto.wallet_address
        # Fallback to BTC if not found
        default_crypto = CryptoCurrency.objects.filter(symbol='BTC', is_active=True).first()
        if default_crypto and default_crypto.wallet_address:
            return default_crypto.wallet_address
        return "Wallet address not configured"
    except Exception as e:
        print(f"Error getting wallet address: {e}")
        return "Wallet address not configured"    

@login_required
def physical_product_detail_page(request, product_id):
    """Full page product detail view - RETURNS HTML"""
    product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
    
    # Clear any old session data for this product (to avoid conflicts)
    request.session.pop('shipping_product_id', None)
    request.session.pop('shipping_quantity', None)
    request.session.pop('shipping_cost', None)
    request.session.pop('shipping_address', None)
    request.session.pop('checkout_delivery_method', None)
    
    cart, created = PhysicalCart.objects.get_or_create(user=request.user)
    cart_count = cart.get_item_count()
    
    context = {
        'product': product,
        'cart_count': cart_count,
    }
    return render(request, 'core/physical_product_detail.html', context)

@login_required
def physical_checkout_vault_confirm(request, product_id):
    """Vault storage confirmation page - DIRECT PURCHASE"""
    product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
    
    # Get quantity from URL parameter
    quantity = int(request.GET.get('quantity', 1))
    
    print(f"=== VAULT CONFIRM PAGE ===")
    print(f"Product ID from URL: {product_id}")
    print(f"Product Name: {product.name}")
    print(f"Quantity from URL: {quantity}")
    
    subtotal = float(product.current_price) * quantity
    total = subtotal  # No shipping fee for vault
    
    # Store in session for payment page
    request.session['payment_product_id'] = product.id
    request.session['payment_quantity'] = quantity
    request.session['payment_delivery_method'] = 'vault'
    request.session['payment_subtotal'] = subtotal
    request.session['payment_total'] = total
    request.session['shipping_cost'] = 0
    
    context = {
        'product': product,
        'quantity': quantity,
        'subtotal': subtotal,
        'total': total,
    }
    return render(request, 'core/physical_checkout_vault_confirm.html', context)

@login_required
def physical_checkout_shipping_confirm(request, product_id):
    """Shipping confirmation page - DIRECT PURCHASE"""
    
    # IMPORTANT: Get product from URL parameter (this is correct)
    product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
    
    # Get quantity from POST (form submission) or GET (URL parameter)
    quantity = int(request.POST.get('quantity', request.GET.get('quantity', 1)))
    
    print("=" * 50)
    print("SHIPPING CONFIRM VIEW CALLED")
    print(f"Product ID from URL: {product_id}")
    print(f"Product Name: {product.name}")
    print(f"Product Price: ${product.current_price}")
    print(f"Quantity from POST/GET: {quantity}")
    print(f"Request Method: {request.method}")
    print("=" * 50)
    
    if request.method == 'POST':
        # Get shipping address from form
        shipping_address = {
            'full_name': request.POST.get('full_name'),
            'phone': request.POST.get('phone'),
            'address_line1': request.POST.get('address_line1'),
            'address_line2': request.POST.get('address_line2', ''),
            'city': request.POST.get('city'),
            'state': request.POST.get('state'),
            'postal_code': request.POST.get('postal_code'),
            'country': request.POST.get('country'),
        }
        
        # Get shipping cost from form (calculated on previous page)
        shipping_cost = float(request.POST.get('shipping_cost', 0))
        
        # Calculate subtotal using the CORRECT product and quantity
        subtotal = float(product.current_price) * quantity
        
        print(f"Subtotal: ${subtotal}")
        print(f"Shipping Cost: ${shipping_cost}")
        print(f"Total: ${subtotal + shipping_cost}")
        
        # Store in session for payment page
        request.session['shipping_address'] = shipping_address
        request.session['shipping_cost'] = shipping_cost
        request.session['shipping_quantity'] = quantity
        request.session['shipping_product_id'] = product.id
        request.session['payment_product_id'] = product.id
        request.session['payment_quantity'] = quantity
        request.session['payment_delivery_method'] = 'shipping'
        request.session['payment_subtotal'] = subtotal
        request.session['payment_total'] = subtotal + shipping_cost
        
        # Redirect to payment page
        return redirect('physical_payment')
    
    # GET request - show the confirmation page with calculated shipping
    # Calculate shipping breakdown
    import re
    weight_str = product.weight
    weight_match = re.search(r'(\d+(?:\.\d+)?)', weight_str)
    weight_value = float(weight_match.group(1)) if weight_match else 1
    
    subtotal = float(product.current_price) * quantity
    weight_factor = weight_value * quantity * 0.5
    if weight_factor > 25:
        weight_factor = 25
    
    insurance = subtotal * 0.01
    
    # Get country from session or default to US
    country = request.session.get('shipping_address', {}).get('country', 'US')
    rates = {
        'US': {'base': 8.99, 'surcharge': 0, 'days': 5},
        'CA': {'base': 12.99, 'surcharge': 2, 'days': 7},
        'GB': {'base': 14.99, 'surcharge': 3, 'days': 8},
        'DE': {'base': 13.99, 'surcharge': 2, 'days': 7},
        'FR': {'base': 13.99, 'surcharge': 2, 'days': 7},
        'CH': {'base': 11.99, 'surcharge': 1, 'days': 6},
        'AE': {'base': 16.99, 'surcharge': 4, 'days': 8},
        'SG': {'base': 15.99, 'surcharge': 3, 'days': 7},
        'AU': {'base': 19.99, 'surcharge': 6, 'days': 10},
    }
    selected = rates.get(country, {'base': 24.99, 'surcharge': 10, 'days': 14})
    base_shipping = selected['base']
    regional_surcharge = selected['surcharge']
    delivery_days = selected['days']
    
    shipping_cost = base_shipping + weight_factor + regional_surcharge + insurance
    total = subtotal + shipping_cost
    
    from datetime import date, timedelta
    estimated_delivery = date.today() + timedelta(days=delivery_days)
    
    context = {
        'product': product,
        'quantity': quantity,
        'subtotal': subtotal,
        'shipping_fee': shipping_cost,
        'total': total,
        'shipping_address': request.session.get('shipping_address', {}),
        'estimated_delivery': estimated_delivery,
        'delivery_days': delivery_days,
        'base_shipping': base_shipping,
        'weight_factor': weight_factor,
        'regional_surcharge': regional_surcharge,
        'insurance': insurance,
        'is_international': country not in ['US', 'CA', 'GB'],
    }
    return render(request, 'core/physical_checkout_shipping_confirm.html', context)
@login_required
@require_POST
def physical_payment_redirect(request):
    """Redirect to payment after confirmation - handles both single and cart items"""
    
    is_cart_checkout = request.POST.get('is_cart_checkout') == 'true'
    delivery_method = request.POST.get('delivery_method')
    
    print("=" * 60)
    print("PAYMENT REDIRECT")
    print(f"Is cart checkout: {is_cart_checkout}")
    print(f"Delivery method: {delivery_method}")
    print("=" * 60)
    
    if is_cart_checkout:
        # For cart checkout, we already have cart_items in session
        request.session['payment_delivery_method'] = delivery_method
        request.session['shipping_cost'] = 0
    else:
        # Single product checkout
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        
        request.session['payment_product_id'] = product_id
        request.session['payment_quantity'] = quantity
        request.session['payment_delivery_method'] = delivery_method
        request.session['shipping_cost'] = 0
    
    # Redirect to physical_payment (NOT physical_payment_page)
    return redirect('physical_payment')


@login_required
def physical_payment_page(request):
    """Payment page after confirmation - shows order summary and payment options"""
    product_id = request.session.get('payment_product_id')
    quantity = request.session.get('payment_quantity', 1)
    delivery_method = request.session.get('payment_delivery_method', 'vault')
    shipping_cost = request.session.get('shipping_cost', 0)
    
    if not product_id:
        return redirect('physical_investments')
    
    product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
    
    # For vault, shipping fee should be 0
    if delivery_method == 'vault':
        shipping_cost = 0
    
    subtotal = float(product.current_price) * quantity
    total = subtotal + shipping_cost
    
    context = {
        'product': product,
        'quantity': quantity,
        'subtotal': subtotal,
        'shipping_fee': shipping_cost,
        'total': total,
        'delivery_method': delivery_method,
        'delivery_method_display': 'Qubix Vault Storage' if delivery_method == 'vault' else 'Ship to Address',
    }
    return render(request, 'core/physical_payment.html', context)

@login_required
@user_passes_test(is_admin)
def physical_team_pending(request):
    """Support team view for pending orders (Payment Under Review)"""
    pending = PhysicalTransaction.objects.filter(status='under_review').order_by('-created_at')
    return render(request, 'core/team/pending_orders.html', {'pending': pending})

@login_required
@user_passes_test(is_admin)
def physical_team_verify(request, transaction_id):
    """Support team view to verify payment and confirm order - FIXED for delivery requests and sell requests"""
    transaction = get_object_or_404(PhysicalTransaction, id=transaction_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'confirm':
            if transaction.status == 'under_review':
                # Check if this is a delivery fee transaction (vault to shipping)
                if transaction.payment_method == 'delivery_fee' or transaction.delivery_method == 'shipping':
                    # Find the vault holding
                    holding = PhysicalHolding.objects.filter(
                        user=transaction.user,
                        product=transaction.product,
                        quantity=transaction.quantity,
                        service_type='vault',
                        delivery_status='pending_delivery'
                    ).first()
                    
                    if holding:
                        # Mark as ready for shipping (still in vault, but pending)
                        holding.delivery_status = 'confirmed'
                        holding.save()
                        
                        # Update transaction status
                        transaction.status = 'confirmed_processing'
                        transaction.confirmed_at = timezone.now()
                        transaction.save()
                        
                        # Notify user
                        Notification.objects.create(
                            user=transaction.user,
                            title="Delivery Request Confirmed",
                            message=f"Your delivery request for {transaction.quantity} x {transaction.product.name} has been confirmed. Our team will prepare your shipment.",
                            notification_type='transaction',
                            is_read=False
                        )
                        
                        messages.success(request, f"Delivery request #{transaction_id} confirmed.")
                    else:
                        messages.error(request, f"Holding not found for delivery request.")
                
                # Check if this is a sell fee transaction
                elif transaction.payment_method == 'sell_fee':
                    # This is a sell request
                    holding = PhysicalHolding.objects.filter(
                        user=transaction.user,
                        product=transaction.product,
                        quantity=transaction.quantity,
                        service_type='vault'
                    ).first()
                    
                    if holding:
                        # Delete the holding (asset sold)
                        holding.delete()
                        
                        # Update transaction status
                        transaction.status = 'completed'
                        transaction.confirmed_at = timezone.now()
                        transaction.save()
                        
                        # Get payout info from shipping_address JSON field
                        payout_info = transaction.shipping_address
                        crypto_currency = payout_info.get('crypto_currency', 'BTC')
                        wallet_address = payout_info.get('wallet_address', 'Not provided')
                        
                        # Notify user
                        Notification.objects.create(
                            user=transaction.user,
                            title="Sale Completed - Payout Initiated",
                            message=f"Your sale of {transaction.quantity} x {transaction.product.name} has been completed. ${transaction.total_amount:,.2f} will be sent to your {crypto_currency} wallet: {wallet_address[:10]}...",
                            notification_type='transaction',
                            is_read=False
                        )
                        
                        messages.success(request, f"Sell request #{transaction_id} completed. Holding removed from vault. Payout info saved.")
                
                # Regular vault order (new purchase)
                elif transaction.delivery_method == 'vault':
                    transaction.status = 'confirmed_vault'
                    transaction.confirmed_at = timezone.now()
                    transaction.save()
                    
                    import random
                    transaction.certificate_number = f"QUBIX-{transaction.id}-{random.randint(10000, 99999)}"
                    transaction.save()
                    
                    PhysicalHolding.objects.create(
                        user=transaction.user,
                        product=transaction.product,
                        quantity=transaction.quantity,
                        average_price=transaction.product.current_price,
                        service_type='vault',
                        transaction=transaction,
                        vault_location='Zurich, Switzerland',
                        delivery_status='confirmed'
                    )
                    
                    send_order_confirmation_email(transaction)
                    messages.success(request, f"Order #{transaction_id} confirmed and added to vault.")
                
                # Regular shipping order (new purchase)
                else:
                    transaction.status = 'confirmed_processing'
                    transaction.confirmed_at = timezone.now()
                    transaction.save()
                    
                    send_order_confirmation_email(transaction)
                    messages.success(request, f"Order #{transaction_id} confirmed and marked as processing.")
        
        elif action == 'mark_shipped':
            # For delivery requests from vault - THIS IS THE KEY PART
            if transaction.payment_method == 'delivery_fee' or transaction.delivery_method == 'shipping':
                # Find the vault holding that is ready for shipping
                holding = PhysicalHolding.objects.filter(
                    user=transaction.user,
                    product=transaction.product,
                    quantity=transaction.quantity,
                    service_type='vault',
                    delivery_status='confirmed'
                ).first()
                
                if holding:
                    # DELETE the vault holding (it's being shipped out)
                    holding.delete()
                    
                    # Update transaction status
                    transaction.status = 'shipped'
                    transaction.shipped_at = timezone.now()
                    
                    tracking_number = request.POST.get('tracking_number', '')
                    if tracking_number:
                        transaction.tracking_number = tracking_number
                    
                    from datetime import date, timedelta
                    transaction.estimated_delivery = date.today() + timedelta(days=10)
                    transaction.save()
                    
                    # Notify user
                    Notification.objects.create(
                        user=transaction.user,
                        title="Item Shipped from Vault",
                        message=f"Your item {transaction.product.name} has been shipped from the vault. Tracking: {tracking_number or 'Will be updated soon'}",
                        notification_type='transaction',
                        is_read=False
                    )
                    
                    send_order_shipped_email(transaction)
                    messages.success(request, f"Item #{transaction_id} marked as shipped and removed from vault.")
                else:
                    messages.warning(request, f"No vault holding found for this delivery request.")
            
            # Regular shipping order (new purchase)
            elif transaction.delivery_method == 'shipping' and transaction.status == 'confirmed_processing':
                transaction.status = 'shipped'
                transaction.shipped_at = timezone.now()
                
                tracking_number = request.POST.get('tracking_number', '')
                if tracking_number:
                    transaction.tracking_number = tracking_number
                
                from datetime import date, timedelta
                transaction.estimated_delivery = date.today() + timedelta(days=10)
                transaction.save()
                
                # Create shipping holding (not vault)
                PhysicalHolding.objects.create(
                    user=transaction.user,
                    product=transaction.product,
                    quantity=transaction.quantity,
                    average_price=transaction.product.current_price,
                    service_type='shipped',
                    transaction=transaction,
                    shipping_address=transaction.shipping_address,
                    tracking_number=transaction.tracking_number,
                    delivery_status='transit',
                    estimated_delivery=transaction.estimated_delivery
                )
                
                send_order_shipped_email(transaction)
                messages.success(request, f"Order #{transaction_id} marked as shipped.")
        
        elif action == 'mark_delivered':
            if transaction.status == 'shipped':
                transaction.status = 'delivered'
                transaction.delivered_at = timezone.now()
                transaction.save()
                
                # Find and update the shipped holding
                holding = PhysicalHolding.objects.filter(transaction=transaction, service_type='shipped').first()
                if holding:
                    holding.delivery_status = 'delivered'
                    holding.save()
                
                send_order_delivered_email(transaction)
                messages.success(request, f"Order #{transaction_id} marked as delivered.")
        
        return redirect('physical_team_pending')
    
    return render(request, 'core/team/verify_order.html', {'transaction': transaction})

@login_required
@require_POST
def physical_save_purchase_data(request):
    """Save purchase data to session before confirmation"""
    try:
        data = json.loads(request.body)
        request.session['pending_purchase'] = {
            'product_id': data['product_id'],
            'quantity': data['quantity'],
            'delivery_method': data['delivery_method'],
            'shipping_address': data.get('shipping_address', {})
        }
        # Also store quantity separately for easy access
        request.session['payment_quantity'] = data['quantity']
        print(f"Saved quantity: {data['quantity']}")  # Debug print
        return JsonResponse({'success': True})
    except Exception as e:
        print(f"Error saving purchase data: {e}")
        return JsonResponse({'error': str(e)}, status=400)    

@login_required
@require_POST
def physical_payment_process(request):
    """Show crypto payment QR code - order NOT created yet"""
    try:
        payment_method = request.POST.get('payment_method', 'BTC')
        
        print("=" * 60)
        print("PHYSICAL PAYMENT PROCESS CALLED")
        print(f"Payment Method: {payment_method}")
        print("=" * 60)
        
        # Get data from session (set in physical_payment redirect)
        product_id = request.session.get('payment_product_id')
        quantity = request.session.get('payment_quantity', 1)
        delivery_method = request.session.get('payment_delivery_method', 'vault')
        shipping_cost = request.session.get('shipping_cost', 0)
        
        # Check if this is from cart with multiple items
        cart_items = request.session.get('payment_cart_items', [])
        
        if cart_items:
            # MULTIPLE ITEMS FROM CART
            subtotal = request.session.get('payment_cart_total', 0)
            total = subtotal
            product = None
        else:
            # SINGLE PRODUCT
            if not product_id:
                messages.error(request, "No product selected. Please start over.")
                return redirect('physical_investments')
            
            product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
            subtotal = float(product.current_price) * quantity
            total = subtotal + shipping_cost
        
        # Generate crypto payment details
        crypto_rates = {'BTC': 63800, 'ETH': 3420, 'USDT': 1, 'LTC': 88}
        crypto_amount = total / crypto_rates.get(payment_method, 1)
        wallet_address = get_wallet_address_from_db(payment_method)
        
        # Store payment details in session (NOT create order yet)
        if cart_items:
            request.session['pending_payment_details'] = json.dumps({
                'cart_items': cart_items,
                'total': total,
                'payment_method': payment_method,
                'delivery_method': delivery_method,
                'shipping_cost': shipping_cost,
            })
        else:
            request.session['pending_payment_details'] = json.dumps({
                'product_id': product_id,
                'quantity': quantity,
                'subtotal': subtotal,
                'total': total,
                'payment_method': payment_method,
                'delivery_method': delivery_method,
                'shipping_cost': shipping_cost,
            })
        
        print(f"Redirecting to crypto payment page with amount: ${total}")
        
        return render(request, 'core/physical_payment_crypto.html', {
            'total': total,
            'payment_method': payment_method,
            'crypto_amount': crypto_amount,
            'crypto_currency': payment_method,
            'wallet_address': wallet_address,
            'product': product,
            'quantity': quantity,
            'cart_items': cart_items if cart_items else None,
            'is_cart_checkout': bool(cart_items),
        })
        
    except Exception as e:
        print(f"Error in physical_payment_process: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error processing payment: {str(e)}")
        return redirect('physical_investments')

@login_required
def physical_track_order(request, transaction_id):
    """Tracking page for shipped orders"""
    transaction = get_object_or_404(PhysicalTransaction, id=transaction_id, user=request.user)
    
    # Define timeline steps based on transaction status
    timeline_steps = {
        'order_confirmed': {
            'label': 'Order Confirmed',
            'description': 'Your order has been confirmed and is being processed.',
            'completed': transaction.status in ['confirmed_processing', 'shipped', 'delivered'],
            'current': transaction.status == 'confirmed_processing',
            'date': transaction.confirmed_at,
        },
        'processing': {
            'label': 'Processing',
            'description': 'Your order is being prepared for shipment.',
            'completed': transaction.status in ['shipped', 'delivered'],
            'current': False,
            'date': None,
        },
        'shipped': {
            'label': 'Shipped',
            'description': 'Your order has been shipped and is on its way.',
            'completed': transaction.status == 'delivered',
            'current': transaction.status == 'shipped',
            'date': transaction.shipped_at,
        },
        'delivered': {
            'label': 'Delivered',
            'description': 'Your order has been delivered.',
            'completed': transaction.status == 'delivered',
            'current': False,
            'date': transaction.delivered_at,
        },
    }
    
    # For vault orders, show different timeline
    if transaction.delivery_method == 'vault':
        timeline_steps = {
            'order_confirmed': {
                'label': 'Order Confirmed',
                'description': 'Your order has been confirmed.',
                'completed': transaction.status == 'confirmed_vault',
                'current': transaction.status == 'confirmed_vault',
                'date': transaction.confirmed_at,
            },
            'in_vault': {
                'label': 'In Vault',
                'description': f'Your item is securely stored in our {transaction.vault_location or "Zurich"} vault.',
                'completed': transaction.status == 'confirmed_vault',
                'current': transaction.status == 'confirmed_vault',
                'date': transaction.confirmed_at,
            },
        }
    
    # Get tracking updates if any (you'll need to create a ShippingTracking model)
    tracking_updates = []
    
    # Calculate estimated delivery
    from datetime import date, timedelta
    if not transaction.estimated_delivery:
        # Default 10 business days from order date
        business_days = 10
        current_date = transaction.created_at.date()
        while business_days > 0:
            current_date += timedelta(days=1)
            if current_date.weekday() < 5:  # Monday to Friday
                business_days -= 1
        estimated_delivery = current_date
    else:
        estimated_delivery = transaction.estimated_delivery
    
    context = {
        'transaction': transaction,
        'timeline_steps': timeline_steps,
        'tracking_updates': tracking_updates,
        'estimated_delivery': estimated_delivery,
    }
    return render(request, 'core/physical_tracking.html', context)

def generate_certificate_pdf(transaction, holding):
    """Generate PDF certificate for vault holdings"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.gold,
        alignment=TA_CENTER,
        spaceAfter=30,
    )
    
    content = []
    
    # Title
    content.append(Paragraph("QUBIX VAULT CERTIFICATE", title_style))
    content.append(Spacer(1, 20))
    
    # Certificate Number
    content.append(Paragraph(f"Certificate No: {transaction.certificate_number or f'QUBIX-{transaction.id}-{random.randint(10000, 99999)}'}", styles['Heading2']))
    content.append(Spacer(1, 20))
    
    # This certifies that
    content.append(Paragraph("This certifies that", styles['Normal']))
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"<b>{transaction.user.get_full_name or transaction.user.email}</b>", styles['Normal']))
    content.append(Spacer(1, 20))
    
    # Product details
    product_data = [
        ["Asset:", transaction.product.name],
        ["Quantity:", f"{transaction.quantity} {transaction.product.specification}"],
        ["Purity:", transaction.product.purity],
        ["Weight:", transaction.product.weight],
        ["Mint:", transaction.product.mint],
        ["Purchase Date:", holding.get_effective_purchase_date().strftime("%B %d, %Y")],
        ["Vault Location:", holding.vault_location or "Zurich, Switzerland"],
        ["Certificate Date:", transaction.get_effective_created_at().strftime("%B %d, %Y")],
    ]
    
    table = Table(product_data, colWidths=[2*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#111520')),
    ]))
    content.append(table)
    content.append(Spacer(1, 30))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )
    content.append(Paragraph("This certificate confirms ownership of the physical asset stored in Qubix's secure vault.", footer_style))
    content.append(Paragraph("© Qubix Investments - All rights reserved.", footer_style))
    
    doc.build(content)
    buffer.seek(0)
    return buffer


def send_order_email(user, subject, message, attachments=None):
    """Send email to user"""
    try:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        if attachments:
            for attachment in attachments:
                email.attach(attachment['filename'], attachment['content'], attachment['mimetype'])
        email.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

@login_required
def download_certificate(request, holding_id):
    """Download PDF certificate for vault holding WITH QR CODE"""
    import tempfile
    import os
    import qrcode
    from reportlab.platypus import Image as ReportLabImage
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user, service_type='vault')
    transaction = holding.transaction
    
    if not transaction:
        messages.error(request, "Certificate not available for this holding.")
        return redirect('physical_investments')
    
    # Generate verification URL
    verification_url = holding.get_verification_url()
    
    # Create QR code as PIL Image
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR to a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    qr_img.save(temp_file.name, 'PNG')
    temp_file.close()
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.gold,
        alignment=TA_CENTER,
        spaceAfter=30,
    )
    
    content = []
    
    content.append(Paragraph("QUBIX VAULT CERTIFICATE", title_style))
    content.append(Spacer(1, 20))
    content.append(Paragraph(f"Certificate No: {transaction.certificate_number or f'QUBIX-{transaction.id}-{random.randint(10000, 99999)}'}", styles['Heading2']))
    content.append(Spacer(1, 20))
    content.append(Paragraph("This certifies that", styles['Normal']))
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"<b>{transaction.user.get_full_name() or transaction.user.email}</b>", styles['Normal']))
    content.append(Spacer(1, 20))
    
    # USE EFFECTIVE METHODS
    effective_quantity = holding.get_effective_quantity()
    purchase_date = holding.get_effective_purchase_date()
    certificate_date = transaction.get_effective_created_at()
    
    product_data = [
        ["Asset:", transaction.product.name],
        ["Quantity:", f"{effective_quantity} {transaction.product.specification}"],
        ["Purity:", transaction.product.purity],
        ["Weight:", transaction.product.weight],
        ["Mint:", transaction.product.mint],
        ["Purchase Date:", purchase_date.strftime("%B %d, %Y")],
        ["Vault Location:", holding.vault_location or "Zurich, Switzerland"],
        ["Certificate Date:", certificate_date.strftime("%B %d, %Y")],
    ]
    
    table = Table(product_data, colWidths=[2*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#111520')),
    ]))
    content.append(table)
    content.append(Spacer(1, 20))
    
    # Add QR CODE from temp file
    qr_image = ReportLabImage(temp_file.name, width=1.2*inch, height=1.2*inch)
    
    qr_table_data = [
        [qr_image, Paragraph(f"<b>Scan to Verify</b><br/>Scan this QR code or visit:<br/><font color='blue' size='8'>{verification_url}</font><br/>to verify this certificate's authenticity.", styles['Normal'])]
    ]
    qr_table = Table(qr_table_data, colWidths=[1.5*inch, 4*inch])
    qr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
    ]))
    content.append(qr_table)
    content.append(Spacer(1, 20))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )
    content.append(Paragraph("This certificate confirms ownership of the physical asset stored in Qubix's secure vault.", footer_style))
    content.append(Paragraph("© Qubix Investments - All rights reserved.", footer_style))
    
    doc.build(content)
    buffer.seek(0)
    
    # Clean up temp file
    os.unlink(temp_file.name)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{transaction.id}.pdf"'
    return response

@login_required
@require_POST
def physical_request_delivery(request, holding_id):
    """Request delivery from vault"""
    from .utils.email_utils import send_physical_order_confirmation_email
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user, service_type='vault')
    
    # Create a delivery request transaction
    # This creates a new shipping order from the vault holding
    transaction = PhysicalTransaction.objects.create(
        user=request.user,
        product=holding.product,
        quantity=holding.quantity,
        total_amount=0,  # No charge for delivery from vault (or add shipping fee)
        delivery_method='shipping',
        payment_method='vault_delivery',
        shipping_address={},  # Will be filled by admin
        status='under_review',
    )
    
    # Mark holding as pending delivery
    holding.delivery_status = 'processing'
    holding.save()
    
    # ========== SEND EMAIL TO USER ==========
    send_physical_order_confirmation_email(request.user, transaction)
    # ========================================
    
    # ========== CREATE NOTIFICATION FOR USER ==========
    Notification.objects.create(
        user=request.user,
        title="Delivery Request Submitted",
        message=f"Your delivery request for {holding.quantity} x {holding.product.name} has been submitted. Our team will process it shortly.",
        notification_type='shop',
        is_read=False
    )
    # ===================================================
    
    # Notify admin
    Notification.objects.create(
        user=None,
        title="Vault Delivery Request",
        message=f"User {request.user.email} requested delivery of {holding.quantity} x {holding.product.name} from vault.",
        notification_type='admin_alert',
        is_read=False
    )
    
    return JsonResponse({'success': True, 'message': 'Delivery request submitted'})

@login_required
def physical_holding_detail(request, holding_id):
    """Get holding details for sell modal"""
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    data = {
        'id': holding.id,
        'product_name': holding.product.name,
        'quantity': float(holding.quantity),
        'current_value': holding.current_value(),
        'average_price': float(holding.average_price),
        'profit_loss': holding.profit_loss(),
        'profit_percent': holding.profit_percent(),
    }
    return JsonResponse(data)


@login_required
@require_POST
def physical_sell_holding(request, holding_id):
    """Sell vault holding - Store sell request in session before payment"""
    import json
    from decimal import Decimal
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user, service_type='vault')
    
    try:
        data = json.loads(request.body)
        wallet_address = data.get('wallet_address')
        crypto_currency = data.get('crypto_currency', 'BTC')
        
        if not wallet_address:
            return JsonResponse({'error': 'Wallet address required'}, status=400)
        
        # Calculate values - Convert everything to Decimal FIRST
        current_value = Decimal(str(holding.current_value()))
        purchase_cost = Decimal(str(holding.average_price)) * Decimal(str(holding.quantity))
        profit_loss = current_value - purchase_cost
        profit_percent = ((current_value / purchase_cost) - 1) * 100 if purchase_cost > 0 else 0
        
        # Calculate fees (5.5% total)
        fee_percentage = Decimal('5.5')
        fee_amount = current_value * (fee_percentage / Decimal('100'))
        net_payout = current_value - fee_amount
        
        # Store sell request in session (DO NOT create transaction yet)
        request.session['pending_sell_request'] = {
            'holding_id': holding_id,
            'wallet_address': wallet_address,
            'crypto_currency': crypto_currency,
            'current_value': float(current_value),
            'purchase_cost': float(purchase_cost),
            'profit_loss': float(profit_loss),
            'profit_percent': float(profit_percent),
            'fee_percentage': float(fee_percentage),
            'fee_amount': float(fee_amount),
            'net_payout': float(net_payout),
        }
        
        return JsonResponse({
            'success': True,
            'redirect_url': f'/physical/sell/confirm/{holding_id}/'
        })
        
    except Exception as e:
        print(f"Error in physical_sell_holding: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def download_invoice(request, transaction_id):
    """Download PDF invoice for transaction"""
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    
    transaction = get_object_or_404(PhysicalTransaction, id=transaction_id, user=request.user)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=20, alignment=TA_CENTER, spaceAfter=30)
    
    content = []
    
    # Title
    content.append(Paragraph("QUBIX INVESTMENTS - INVOICE", title_style))
    content.append(Spacer(1, 20))
    
    # Invoice details
    invoice_data = [
        ["Invoice #:", f"INV-{transaction.id}"],
        ["Date:", transaction.get_effective_created_at().strftime("%B %d, %Y")],
        ["Order #:", f"ORD-{transaction.id}"],
        ["Status:", transaction.get_status_display()],
    ]
    
    table = Table(invoice_data, colWidths=[2*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    content.append(table)
    content.append(Spacer(1, 20))
    
    # Customer details
    content.append(Paragraph("<b>Customer Information</b>", styles['Heading2']))
    content.append(Spacer(1, 10))
    customer_data = [
        ["Name:", transaction.user.get_full_name or transaction.user.email],
        ["Email:", transaction.user.email],
    ]
    if transaction.shipping_address:
        customer_data.append(["Address:", f"{transaction.shipping_address.get('address_line1', '')}, {transaction.shipping_address.get('city', '')}, {transaction.shipping_address.get('country', '')}"])
    
    table2 = Table(customer_data, colWidths=[1.5*inch, 4.5*inch])
    table2.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 10)]))
    content.append(table2)
    content.append(Spacer(1, 20))
    
    # Order details
    content.append(Paragraph("<b>Order Details</b>", styles['Heading2']))
    content.append(Spacer(1, 10))
    
    order_data = [
        ["Product", "Quantity", "Unit Price", "Total"],
        [transaction.product.name, f"{transaction.quantity}", f"${transaction.product.current_price:.2f}", f"${(transaction.product.current_price * transaction.quantity):.2f}"],
    ]
    
    if transaction.shipping_fee > 0:
        order_data.append(["Shipping Fee", "", "", f"+${transaction.shipping_fee:.2f}"])
    
    order_data.append(["", "", "<b>TOTAL</b>", f"<b>${transaction.total_amount:.2f}</b>"])
    
    table3 = Table(order_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    table3.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    content.append(table3)
    content.append(Spacer(1, 20))
    
    # Payment details
    content.append(Paragraph("<b>Payment Details</b>", styles['Heading2']))
    content.append(Spacer(1, 10))
    payment_data = [
        ["Payment Method:", transaction.get_payment_method_display()],
        ["Payment Status:", transaction.get_status_display()],
        ["Transaction ID:", transaction.transaction_hash or "Pending"],
    ]
    table4 = Table(payment_data, colWidths=[2*inch, 4*inch])
    table4.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 10)]))
    content.append(table4)
    
    doc.build(content)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{transaction.id}.pdf"'
    return response

@login_required
def physical_request_delivery_page(request, holding_id):
    """First page - Enter shipping address for vault delivery"""
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user, service_type='vault')
    transaction = holding.transaction
    
    # Calculate fees
    current_value = holding.current_value()
    
    # Fees breakdown
    asset_fee = current_value * Decimal('0.005')   # 0.5% asset maintenance fee
    withdrawal_fee = current_value * Decimal('0.05')  # 5% withdrawal/processing fee
    shipping_fee = Decimal('0')  # Will be calculated based on address
    
    subtotal = asset_fee + withdrawal_fee + shipping_fee
    
    if request.method == 'POST':
        shipping_address = {
            'full_name': request.POST.get('full_name'),
            'phone': request.POST.get('phone'),
            'address_line1': request.POST.get('address_line1'),
            'address_line2': request.POST.get('address_line2', ''),
            'city': request.POST.get('city'),
            'state': request.POST.get('state'),
            'postal_code': request.POST.get('postal_code'),
            'country': request.POST.get('country'),
        }
        
        # Calculate shipping cost based on country
        import re
        weight_str = holding.product.weight
        weight_match = re.search(r'(\d+(?:\.\d+)?)', weight_str)
        weight_value = float(weight_match.group(1)) if weight_match else 1
        weight_factor = weight_value * float(holding.quantity) * 0.5
        if weight_factor > 25:
            weight_factor = 25
        
        insurance = current_value * Decimal('0.01')  # 1% insurance
        
        country = shipping_address.get('country', '')
        rates = {
            'US': {'base': 8.99, 'surcharge': 0},
            'CA': {'base': 12.99, 'surcharge': 2},
            'GB': {'base': 14.99, 'surcharge': 3},
            'DE': {'base': 13.99, 'surcharge': 2},
            'FR': {'base': 13.99, 'surcharge': 2},
            'CH': {'base': 11.99, 'surcharge': 1},
            'AE': {'base': 16.99, 'surcharge': 4},
            'SG': {'base': 15.99, 'surcharge': 3},
            'AU': {'base': 19.99, 'surcharge': 6},
        }
        selected = rates.get(country, {'base': 24.99, 'surcharge': 10})
        base_shipping = selected['base']
        regional_surcharge = selected['surcharge']
        
        shipping_fee = base_shipping + weight_factor + regional_surcharge + float(insurance)
        
        # Recalculate total with shipping
        total_fees = asset_fee + withdrawal_fee + Decimal(str(shipping_fee))
        
        # Store in session
        request.session['delivery_request'] = {
            'holding_id': holding_id,
            'shipping_address': shipping_address,
            'asset_fee': float(asset_fee),
            'withdrawal_fee': float(withdrawal_fee),
            'shipping_fee': shipping_fee,
            'total_fees': float(total_fees),
            'current_value': float(current_value),
        }
        
        return redirect('physical_request_delivery_confirm', holding_id=holding_id)
    
    context = {
        'holding': holding,
        'transaction': transaction,
        'current_value': current_value,
        'asset_fee': asset_fee,
        'withdrawal_fee': withdrawal_fee,
        'shipping_fee': shipping_fee,
        'subtotal': subtotal,
        'countries': ['United States', 'Canada', 'United Kingdom', 'Germany', 'France', 'Switzerland', 'UAE', 'Singapore', 'Australia'],
    }
    return render(request, 'core/physical_request_delivery.html', context)

@login_required
def physical_request_delivery_confirm(request, holding_id):
    """Confirmation page showing fee breakdown"""
    delivery_data = request.session.get('delivery_request')
    
    if not delivery_data or delivery_data.get('holding_id') != holding_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('physical_investments')
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    context = {
        'holding': holding,
        'shipping_address': delivery_data['shipping_address'],
        'asset_fee': delivery_data['asset_fee'],
        'withdrawal_fee': delivery_data['withdrawal_fee'],
        'shipping_fee': delivery_data['shipping_fee'],
        'total_fees': delivery_data['total_fees'],
        'current_value': delivery_data['current_value'],
    }
    return render(request, 'core/physical_request_delivery_confirm.html', context)

@login_required
def physical_request_delivery_payment(request, holding_id):
    """Show crypto payment page - DO NOT create transaction yet"""
    delivery_data = request.session.get('delivery_request')
    
    if not delivery_data or delivery_data.get('holding_id') != holding_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('physical_investments')
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    # Check if already requested
    if holding.delivery_status in ['pending_delivery', 'processing', 'transit', 'shipped']:
        messages.error(request, "Delivery already requested for this item.")
        return redirect('physical_investments')
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'BTC')
        
        # Store payment details in session - DO NOT CREATE TRANSACTION YET
        request.session['pending_delivery_payment'] = {
            'holding_id': holding_id,
            'payment_method': payment_method,
            'total_fees': delivery_data['total_fees'],
            'shipping_fee': delivery_data['shipping_fee'],
            'shipping_address': delivery_data['shipping_address'],
            'asset_fee': delivery_data.get('asset_fee', 0),
            'withdrawal_fee': delivery_data.get('withdrawal_fee', 0),
        }
        
        # Generate crypto payment details
        crypto_rates = {'BTC': 63800, 'ETH': 3420, 'USDT': 1, 'LTC': 88}
        crypto_amount = delivery_data['total_fees'] / crypto_rates.get(payment_method, 1)
        
        return render(request, 'core/physical_payment_crypto.html', {
            'total': delivery_data['total_fees'],
            'payment_method': payment_method,
            'crypto_amount': crypto_amount,
            'crypto_currency': payment_method,
            'wallet_address': get_wallet_address_from_db(payment_method),
            'transaction_id': None,  # No transaction yet
            'is_delivery_fee': True,
            'holding_id': holding_id,
        })
    
    context = {
        'holding': holding,
        'total_fees': delivery_data['total_fees'],
        'shipping_fee': delivery_data['shipping_fee'],
        'shipping_address': delivery_data['shipping_address'],
        'asset_fee': delivery_data.get('asset_fee', 0),
        'withdrawal_fee': delivery_data.get('withdrawal_fee', 0),
    }
    return render(request, 'core/physical_request_delivery_payment.html', context)

@login_required
def physical_product_api_detail(request, product_id):
    """API endpoint for product details (for modal)"""
    try:
        product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
        data = {
            'id': product.id,
            'name': product.name,
            'current_price': float(product.current_price),
            'spot_price': float(product.spot_price),
            'price_change_24h': float(product.price_change_24h),
            'purity': product.purity,
            'weight': product.weight,
            'mint': product.mint,
            'category': product.category,
            'premium_percent': float(product.get_premium_percent()),
            'main_image': product.main_image.url if product.main_image else None,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def physical_update_cart(request, item_id):
    cart_item = get_object_or_404(PhysicalCartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity <= 0:
        cart_item.delete()
    else:
        cart_item.quantity = quantity
        cart_item.save()
    
    cart = cart_item.cart
    return JsonResponse({
        'success': True,
        'cart_count': cart.get_item_count(),
        'cart_total': float(cart.get_total()),
        'item_subtotal': float(cart_item.get_subtotal()) if cart_item.id else 0,
    })


@login_required
@require_POST
def physical_remove_from_cart(request, item_id):
    cart_item = get_object_or_404(PhysicalCartItem, id=item_id, cart__user=request.user)
    cart = cart_item.cart
    cart_item.delete()
    
    return JsonResponse({
        'success': True,
        'cart_count': cart.get_item_count(),
        'cart_total': float(cart.get_total()),
    })    
   

@login_required
def physical_checkout_vault_confirm_first(request):
    """Vault confirmation page for cart items - MULTIPLE ITEMS"""
    # Get cart items from session
    cart_items = request.session.get('checkout_cart_items', [])
    subtotal = request.session.get('checkout_subtotal', 0)
    
    if not cart_items:
        messages.error(request, "No items in cart")
        return redirect('physical_cart')
    
    # Store ALL items in session for payment page
    request.session['checkout_all_items'] = cart_items
    request.session['checkout_total_amount'] = float(subtotal)
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'total': subtotal,
        'item_count': len(cart_items),
    }
    return render(request, 'core/physical_checkout_vault_confirm.html', context)

@login_required
def physical_product_detail_page_new(request, product_id):
    """Brand new HTML page view - TEST"""
    print("="*50)
    print("NEW HTML PAGE VIEW CALLED!")
    print(f"Product ID: {product_id}")
    print("="*50)
    
    product = get_object_or_404(PhysicalProduct, id=product_id, is_active=True)
    
    cart, created = PhysicalCart.objects.get_or_create(user=request.user)
    cart_count = cart.get_item_count()
    
    # Return HTML directly
    return HttpResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{product.name} | Qubix</title>
        <style>
            body {{ font-family: Arial; background: #0a0c12; color: white; padding: 40px; }}
            .container {{ max-width: 800px; margin: 0 auto; background: #1a1e2a; padding: 30px; border-radius: 20px; }}
            h1 {{ color: #f0b90b; }}
            .price {{ font-size: 32px; color: #0ecb81; }}
            button {{ background: #f0b90b; color: black; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{product.name}</h1>
            <p><strong>Category:</strong> {product.category}</p>
            <p><strong>Specification:</strong> {product.specification}</p>
            <p><strong>Purity:</strong> {product.purity}</p>
            <p><strong>Weight:</strong> {product.weight}</p>
            <p><strong>Mint:</strong> {product.mint}</p>
            <p class="price">${product.current_price}</p>
            <button onclick="alert('Add to cart!')">Add to Cart</button>
            <br><br>
            <a href="/physical/" style="color: #f0b90b;">← Back to Shop</a>
        </div>
    </body>
    </html>
    """) 

@login_required
@require_POST
def physical_clear_session(request):
    """Clear all physical product session data"""
    keys_to_clear = [
        'shipping_product_id', 'shipping_quantity', 'shipping_cost', 
        'shipping_address', 'checkout_delivery_method', 'cart_subtotal',
        'checkout_cart_items', 'checkout_subtotal', 'payment_product_id',
        'payment_quantity', 'payment_delivery_method', 'pending_payment_details'
    ]
    for key in keys_to_clear:
        request.session.pop(key, None)
    return JsonResponse({'success': True})    
      
@login_required
def physical_sell_confirm(request, holding_id):
    """Show sell confirmation page with fee breakdown"""
    sell_data = request.session.get('pending_sell_request')
    
    if not sell_data or sell_data.get('holding_id') != holding_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('physical_investments')
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    context = {
        'holding': holding,
        'current_value': sell_data['current_value'],
        'purchase_cost': sell_data['purchase_cost'],
        'profit_loss': sell_data['profit_loss'],
        'profit_percent': sell_data['profit_percent'],
        'fee_percentage': sell_data['fee_percentage'],
        'fee_amount': sell_data['fee_amount'],
        'net_payout': sell_data['net_payout'],
        'wallet_address': sell_data['wallet_address'],
        'crypto_currency': sell_data['crypto_currency'],
    }
    return render(request, 'core/physical_sell_confirm.html', context)

@login_required
def physical_sell_payment(request, holding_id):
    """Show crypto payment page for sell fee - DO NOT create sell transaction yet"""
    sell_data = request.session.get('pending_sell_request')
    
    if not sell_data or sell_data.get('holding_id') != holding_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('physical_investments')
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'BTC')
        
        # Store payment details in session
        request.session['pending_sell_payment'] = {
            'holding_id': holding_id,
            'payment_method': payment_method,
            'fee_amount': sell_data['fee_amount'],
            'net_payout': sell_data['net_payout'],
            'wallet_address': sell_data['wallet_address'],
            'crypto_currency': sell_data['crypto_currency'],
            'current_value': sell_data['current_value'],
        }
        
        # Generate crypto payment details
        crypto_rates = {'BTC': 63800, 'ETH': 3420, 'USDT': 1, 'LTC': 88}
        crypto_amount = sell_data['fee_amount'] / crypto_rates.get(payment_method, 1)
        
        return render(request, 'core/physical_payment_crypto.html', {
            'total': sell_data['fee_amount'],
            'payment_method': payment_method,
            'crypto_amount': crypto_amount,
            'crypto_currency': payment_method,
            'wallet_address': get_wallet_address_from_db(payment_method),
            'transaction_id': None,
            'is_sell_fee': True,
            'holding_id': holding_id,
        })
    
    context = {
        'holding': holding,
        'fee_amount': sell_data['fee_amount'],
        'net_payout': sell_data['net_payout'],
    }
    return render(request, 'core/physical_sell_payment.html', context)     
def get_wkhtmltopdf_path():
    possible_paths = [
        r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
        r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

WKHTMLTOPDF_PATH = get_wkhtmltopdf_path()

def render_to_pdf(template_src, context_dict={}):
    """
    Renders a Django HTML template to PDF using Playwright + Chromium.
    Returns an HttpResponse with the PDF, or None on failure.
    
    Supports full modern CSS: variables, grid, flexbox, animations,
    Google Fonts, gradients — everything renders perfectly.
    """
    from django.template.loader import render_to_string
    from playwright.sync_api import sync_playwright
    
    # Render the Django template to an HTML string
    html_string = render_to_string(template_src, context_dict)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1200, 'height': 900})
            
            # Use set_content with networkidle so Google Fonts load
            page.set_content(html_string, wait_until='networkidle')
            
            pdf_bytes = page.pdf(
                format='A4',
                print_background=True,   # critical: renders backgrounds/colors
                margin={
                    'top': '0',
                    'right': '0',
                    'bottom': '0',
                    'left': '0'
                }
            )
            browser.close()
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        return response
    
    except Exception as e:
        print(f"PDF generation error: {e}")
        return None

@login_required
def download_vault_certificate_html(request, holding_id):
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user, service_type='vault')
    transaction = holding.transaction

    verification_url = holding.get_verification_url()
    qr_code_base64 = generate_qr_code_base64(verification_url)

    context = {
        'certificate_number': transaction.certificate_number or f"QUBIX-{holding.id}-{timezone.now().year}",
        # REMOVED the bad line: transaction = holding.transaction
        'issue_date': transaction.get_effective_created_at().strftime("%d %B %Y"),
        'user_name': request.user.get_full_name() or request.user.email,
        'product_name': holding.product.name,
        'quantity': f"{holding.quantity} {holding.product.specification}",
        'specification': holding.product.specification,
        'purity': holding.product.purity,
        'weight': holding.product.weight,
        'mint': holding.product.mint,
        'vault_location': holding.vault_location or "Zurich, Switzerland",
        'qr_code_base64': qr_code_base64,
    }

    # Use Playwright instead of WeasyPrint — preserves full CSS/fonts/layout
    pdf = render_to_pdf('core/documents/vault_certificate.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="vault_certificate_{holding.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_allocated_storage(request, holding_id):
    """Download Allocated Storage Confirmation PDF"""
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    transaction = holding.transaction
    if transaction and hasattr(transaction, 'created_at'):
        allocated_since = holding.get_effective_purchase_date().strftime("%d %B %Y")
    else:
        allocated_since = timezone.now().strftime("%d %B %Y")
    
    context = {
        'serial_number': f"ALLOC-{holding.id}-{timezone.now().year}",
        'user_name': request.user.get_full_name() or request.user.email,
        'allocated_since': allocated_since,
        'vault_location': holding.vault_location or "Zurich, Switzerland",
        'product_name': holding.product.name,
        'quantity': f"{holding.quantity} {holding.product.specification}",
        'auditor': "PricewaterhouseCoopers LLP (PwC)",
    }
    
    pdf = render_to_pdf('core/documents/allocated_storage.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="allocated_storage_{holding.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_authenticity_certificate(request, holding_id):
    """Download Authenticity Certificate PDF with effective dates"""
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    transaction = holding.transaction
    
    import hashlib
    from playwright.sync_api import sync_playwright
    from django.template.loader import render_to_string

    verification_code = hashlib.sha256(
        f"auth-{holding.id}-{holding.id}".encode()
    ).hexdigest()[:16].upper()
    
    verification_url = f"{request.scheme}://{request.get_host()}/verify/auth/{verification_code}/"
    qr_code_base64 = generate_qr_code_base64(verification_url)
    
    # USE EFFECTIVE METHODS
    issue_date = transaction.get_effective_created_at()
    purchase_date = holding.get_effective_purchase_date()
    effective_quantity = holding.get_effective_quantity()

    context = {
        'certificate_number': f"AUTH-{holding.id}-{timezone.now().year}",
        'issue_date': issue_date.strftime("%d %B %Y"),
        'purchase_date': purchase_date.strftime("%d %B %Y"),
        'user_name': request.user.get_full_name() or request.user.email,
        'product_name': holding.product.name,
        'quantity': f"{effective_quantity} {holding.product.specification}",
        'purity': holding.product.purity,
        'weight': holding.product.weight,
        'mint': holding.product.mint,
        'serial_number': f"SN-{holding.id}-{timezone.now().year}",
        'verification_url': verification_url,
        'qr_code_base64': qr_code_base64,
    }

    html_string = render_to_string('core/documents/authenticity_certificate.html', context)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1200, 'height': 900})
            page.set_content(html_string, wait_until='networkidle')
            
            page.wait_for_function("""
                () => {
                    const imgs = document.querySelectorAll('img');
                    return Array.from(imgs).every(img => img.complete && img.naturalWidth > 0);
                }
            """)
            
            pdf_bytes = page.pdf(
                format='A4',
                print_background=True,
                margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
            )
            browser.close()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="authenticity_{holding.id}.pdf"'
        return response

    except Exception as e:
        print(f"PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return HttpResponse("Error generating PDF", status=500)

@login_required
def download_delivery_receipt(request, transaction_id):
    """Download Delivery Receipt PDF with effective delivery date"""
    from datetime import timedelta
    
    transaction = get_object_or_404(PhysicalTransaction, id=transaction_id, user=request.user)
    
    # USE EFFECTIVE METHODS
    effective_quantity = transaction.get_effective_quantity() if hasattr(transaction, 'get_effective_quantity') else transaction.quantity
    
    # Get effective delivery date (admin can override this)
    delivery_date = None
    if hasattr(transaction, 'get_effective_delivered_at'):
        delivery_date = transaction.get_effective_delivered_at()
    elif transaction.delivered_at:
        delivery_date = transaction.delivered_at
    
    # If no delivery date, use estimated delivery or order date + 14 days
    if not delivery_date:
        if transaction.estimated_delivery:
            if isinstance(transaction.estimated_delivery, str):
                try:
                    from datetime import datetime
                    delivery_date = datetime.strptime(transaction.estimated_delivery, "%Y-%m-%d")
                except:
                    delivery_date = timezone.now()
            else:
                delivery_date = transaction.estimated_delivery
        else:
            order_date = transaction.get_effective_created_at()
            delivery_date = order_date + timedelta(days=14)
    
    if isinstance(delivery_date, str):
        delivery_date_str = delivery_date
    else:
        delivery_date_str = delivery_date.strftime("%d %B %Y")
    
    # Calculate days to deliver
    order_date = transaction.get_effective_created_at()
    if transaction.delivered_at or delivery_date:
        try:
            if isinstance(delivery_date, (timezone.datetime, datetime)):
                days_to_deliver = (delivery_date - order_date).days
            else:
                days_to_deliver = "N/A"
        except:
            days_to_deliver = "N/A"
    else:
        days_to_deliver = "Pending"
    
    context = {
        'order_number': f"ORD-{transaction.id}",
        'order_date': order_date.strftime("%d %B %Y"),
        'user_name': request.user.get_full_name() or request.user.email,
        'product_name': transaction.product.name,
        'quantity': f"{effective_quantity:,.3f}",
        'delivery_date': delivery_date_str,
        'days_to_deliver': days_to_deliver,
        'received_by': request.user.get_full_name() or request.user.email,
        'condition_verified': "Good Condition" if transaction.status == 'delivered' else "Pending Inspection",
        'signature': "Electronically Confirmed",
        'delivery_status': transaction.status,
    }
    
    pdf = render_to_pdf('core/documents/delivery_receipt.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="delivery_receipt_{transaction.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_insurance_certificate(request, holding_id):
    """Download Insurance Certificate PDF with effective dates"""
    from datetime import timedelta
    
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    transaction = holding.transaction
    
    # USE EFFECTIVE METHODS
    purchase_date = holding.get_effective_purchase_date()
    effective_value = holding.get_effective_current_value()
    effective_quantity = holding.get_effective_quantity()
    
    coverage_start = purchase_date
    coverage_end = coverage_start + timedelta(days=365)
    
    context = {
        'policy_number': f"INS-{holding.id}-{timezone.now().year}",
        'user_name': request.user.get_full_name() or request.user.email,
        'insured_value': f"${effective_value:,.2f}",
        'coverage_start': coverage_start.strftime("%d %B %Y"),
        'coverage_end': coverage_end.strftime("%d %B %Y"),
        'coverage_period': "365 days from purchase date",
        'carrier_name': "Lloyd's of London Syndicate",
        'product_name': holding.product.name,
        'product_quantity': f"{effective_quantity} {holding.product.specification}",
        'claim_phone': "+44 20 7000 0000",
        'claim_email': "claims@qubix.com",
    }
    
    pdf = render_to_pdf('core/documents/insurance_certificate.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="insurance_{holding.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_proof_of_ownership(request, holding_id):
    """Download Proof of Ownership PDF"""
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    # Use transaction.created_at instead of holding.created_at
    transaction = holding.transaction
    purchase_date = holding.get_effective_purchase_date().strftime("%d %B %Y")
    
    context = {
        'certificate_number': f"POO-{holding.id}",
        'purchase_date': purchase_date,
        'user_name': request.user.get_full_name() or request.user.email,
        'product_name': holding.product.name,
        'quantity': f"{holding.quantity} {holding.product.specification}",
        'purchase_price': f"${holding.current_value():,.2f}",
    }
    
    pdf = render_to_pdf('core/documents/proof_of_ownership.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="proof_of_ownership_{holding.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_purchase_invoice(request, transaction_id):
    """Download Purchase Invoice PDF with effective values"""
    transaction = get_object_or_404(PhysicalTransaction, id=transaction_id, user=request.user)
    product = transaction.product
    
    # USE EFFECTIVE METHODS
    invoice_date = transaction.get_effective_created_at()
    effective_quantity = transaction.get_effective_quantity() if hasattr(transaction, 'get_effective_quantity') else transaction.quantity
    effective_total = transaction.get_effective_total_amount()
    
    invoice_number = f"INV-PHYS-{transaction.id}"
    order_id = f"ORD-PHYS-{transaction.id}"
    
    context = {
        'invoice_number': invoice_number,
        'invoice_date': invoice_date.strftime("%B %d, %Y"),
        'order_id': order_id,
        'user_name': request.user.get_full_name() or request.user.email,
        'user_email': request.user.email,
        'product_name': f"{product.name} - {product.specification}",
        'quantity': f"{effective_quantity:,.3f}",
        'unit_price': f"${product.current_price:,.2f}",
        'total_amount': f"${effective_total:,.2f}",
        'payment_method': transaction.payment_method.upper(),
        'transaction_hash': transaction.transaction_hash or "Pending confirmation",
    }
    
    pdf = render_to_pdf('core/documents/purchase_invoice.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="purchase_invoice_{transaction.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_shipping_confirmation(request, transaction_id):
    """Download Shipping Confirmation PDF with effective dates"""
    from datetime import timedelta
    
    transaction = get_object_or_404(PhysicalTransaction, id=transaction_id, user=request.user)
    
    shipping_addr = ""
    if transaction.shipping_address:
        addr = transaction.shipping_address
        shipping_addr = f"{addr.get('full_name', '')}\n{addr.get('address_line1', '')}\n"
        if addr.get('address_line2'):
            shipping_addr += f"{addr.get('address_line2')}\n"
        shipping_addr += f"{addr.get('city', '')}, {addr.get('state', '')} {addr.get('postal_code', '')}\n{addr.get('country', '')}"
    
    # USE EFFECTIVE METHODS
    order_date = transaction.get_effective_created_at()
    effective_quantity = transaction.get_effective_quantity() if hasattr(transaction, 'get_effective_quantity') else transaction.quantity
    
    # Get effective shipped date
    shipped_date = None
    if hasattr(transaction, 'get_effective_shipped_at'):
        shipped_date = transaction.get_effective_shipped_at()
    elif transaction.shipped_at:
        shipped_date = transaction.shipped_at
    
    # Calculate estimated delivery based on effective shipped date
    if shipped_date:
        estimated_delivery_date = shipped_date + timedelta(days=10)
        shipped_date_str = shipped_date.strftime("%d %B %Y")
    elif transaction.estimated_delivery:
        estimated_delivery_date = transaction.estimated_delivery
        shipped_date_str = "Processing"
    else:
        estimated_delivery_date = order_date + timedelta(days=14)
        shipped_date_str = "Processing"
    
    if isinstance(estimated_delivery_date, str):
        estimated_delivery_str = estimated_delivery_date
    else:
        estimated_delivery_str = estimated_delivery_date.strftime("%d %B %Y")
    
    context = {
        'order_number': f"ORD-{transaction.id}",
        'order_date': order_date.strftime("%d %B %Y"),
        'user_name': request.user.get_full_name() or request.user.email,
        'product_name': transaction.product.name,
        'quantity': f"{effective_quantity:,.3f}",
        'shipped_date': shipped_date_str,
        'estimated_delivery': estimated_delivery_str,
        'carrier': "DHL Secure Courier",
        'tracking_number': transaction.tracking_number or "Pending",
        'shipping_address': shipping_addr,
    }
    
    pdf = render_to_pdf('core/documents/shipping_confirmation.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="shipping_confirmation_{transaction.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)


@login_required
def download_shipping_invoice(request, transaction_id):
    """Download Shipping Invoice PDF with effective values"""
    from datetime import timedelta
    
    transaction = get_object_or_404(PhysicalTransaction, id=transaction_id, user=request.user)
    
    shipping_addr = ""
    if transaction.shipping_address:
        addr = transaction.shipping_address
        shipping_addr = f"{addr.get('full_name', '')}\n{addr.get('address_line1', '')}\n"
        if addr.get('address_line2'):
            shipping_addr += f"{addr.get('address_line2')}\n"
        shipping_addr += f"{addr.get('city', '')}, {addr.get('state', '')} {addr.get('postal_code', '')}\n{addr.get('country', '')}"
    
    # USE EFFECTIVE METHODS
    invoice_date = transaction.get_effective_created_at()
    effective_quantity = transaction.get_effective_quantity() if hasattr(transaction, 'get_effective_quantity') else transaction.quantity
    effective_total = transaction.get_effective_total_amount()
    
    # Get effective shipped date (admin can override)
    shipped_date = None
    if hasattr(transaction, 'get_effective_shipped_at'):
        shipped_date = transaction.get_effective_shipped_at()
    elif transaction.shipped_at:
        shipped_date = transaction.shipped_at
    
    context = {
        'invoice_number': f"SHIP-INV-{transaction.id}",
        'invoice_date': invoice_date.strftime("%d %B %Y"),
        'order_id': f"ORD-{transaction.id}",
        'user_name': request.user.get_full_name() or request.user.email,
        'user_email': request.user.email,
        'product_name': transaction.product.name,
        'quantity': f"{effective_quantity:,.3f}",
        'unit_price': f"${transaction.product.current_price:,.2f}",
        'total_amount': f"${effective_total:,.2f}",
        'shipping_fee': f"${transaction.shipping_fee:,.2f}",
        'payment_method': transaction.payment_method,
        'transaction_hash': transaction.transaction_hash or "Pending",
        'tracking_number': transaction.tracking_number or "Pending",
        'shipping_address': shipping_addr,
        'shipped_date': shipped_date.strftime("%d %B %Y") if shipped_date else "Not yet shipped",
    }
    
    pdf = render_to_pdf('core/documents/shipping_invoice.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="shipping_invoice_{transaction.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_storage_agreement(request, holding_id):
    """Download Storage Agreement PDF"""
    holding = get_object_or_404(PhysicalHolding, id=holding_id, user=request.user)
    
    transaction = holding.transaction
    if transaction and hasattr(transaction, 'created_at'):
        agreement_date = holding.get_effective_purchase_date().strftime("%d %B %Y")
    else:
        agreement_date = timezone.now().strftime("%d %B %Y")
    
    context = {
        'agreement_date': agreement_date,
        'user_name': request.user.get_full_name() or request.user.email,
        'storage_fee_rate': "0.5% per annum",
        'insurance_coverage': "100% of market value",
        'vault_location': holding.vault_location or "Zurich, Switzerland",
    }
    
    pdf = render_to_pdf('core/documents/storage_agreement.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="storage_agreement_{holding.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

def generate_qr_code_base64(data, size=150):
    """Generate QR code as base64 string for embedding in PDF"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/png;base64,{img_base64}"    

# In views.py
def verify_document(request, code):
    """Public page to verify document authenticity"""
    try:
        holding = PhysicalHolding.objects.get(verification_code=code)
        transaction = holding.transaction
        
        context = {
            'is_valid': True,
            'certificate_number': transaction.certificate_number if transaction else f"CERT-{holding.id}",
            'user_email': holding.user.email,
            'issue_date': holding.created_at,
            'product_name': holding.product.name,
            'quantity': holding.quantity,
            'vault_location': holding.vault_location or "Zurich, Switzerland",
            'verification_time': timezone.now(),
        }
    except PhysicalHolding.DoesNotExist:
        context = {
            'is_valid': False,
            'error_message': "This certificate number does not exist in our records."
        }
    
    return render(request, 'core/verify_document.html', context)

def verify_authenticity_certificate(request, code):
    """Public page to verify Certificate of Authenticity"""
    import hashlib
    
    # Try to find the holding that matches this code
    matched_holding = None
    for holding in PhysicalHolding.objects.select_related('product', 'user').all():
        expected_code = hashlib.sha256(f"auth-{holding.id}-{holding.id}".encode()).hexdigest()[:16].upper()
        if expected_code == code:
            matched_holding = holding
            break
    
    if matched_holding:
        context = {
            'is_valid': True,
            'certificate_number': f"AUTH-{matched_holding.id}-{timezone.now().year}",
            'product_name': matched_holding.product.name,
            'purity': matched_holding.product.purity,
            'weight': matched_holding.product.weight,
            'mint': matched_holding.product.mint,
            'vault_location': matched_holding.vault_location or "Zurich, Switzerland",
            'verification_time': timezone.now(),
            'owner_initials': matched_holding.user.first_name[0] + matched_holding.user.last_name[0] if matched_holding.user.first_name and matched_holding.user.last_name else "Q",
        }
    else:
        context = {'is_valid': False}
    
    return render(request, 'core/verify_authenticity.html', context)    

@login_required
def real_estate_withdraw(request, property_id):
    """Handle withdrawal from a real estate investment after lock-in period"""
    from decimal import Decimal
    
    property_obj = get_object_or_404(RealEstateProperty, id=property_id)
    user_investment = get_object_or_404(RealEstateInvestment, user=request.user, property=property_obj)
    
    # Check if investment has matured
    if user_investment.maturity_date and user_investment.maturity_date > timezone.now():
        messages.error(request, f"Cannot withdraw before maturity date ({user_investment.maturity_date.strftime('%B %d, %Y')}). Early withdrawal penalty applies (15% of profits).")
        return redirect('real_estate_detail', property_id=property_id)
    
    # Calculate profit and penalty
    profit = user_investment.amount_invested * (Decimal(str(user_investment.expected_annual_return)) / 100) * (user_investment.investment_period_months / 12)
    penalty = profit * Decimal('0.15') if user_investment.maturity_date and user_investment.maturity_date > timezone.now() else Decimal('0')
    withdrawal_amount = user_investment.amount_invested + profit - penalty
    
    with transaction.atomic():
        # Return funds to user's portfolio
        portfolio = request.user.portfolio
        portfolio.cash_balance += withdrawal_amount
        portfolio.save()
        
        # Create transaction record
        Transaction.objects.create(
            user=request.user,
            transaction_type='withdraw',
            total_amount=withdrawal_amount,
            status='approved',
            notes=f"Real Estate withdrawal from {property_obj.name}. Profit: ${profit:.2f}, Penalty: ${penalty:.2f}"
        )
        
        # Delete the investment
        user_investment.delete()
        
        # Create notification
        Notification.objects.create(
            user=request.user,
            title="Real Estate Investment Withdrawn",
            message=f"You have withdrawn ${withdrawal_amount:,.2f} from {property_obj.name}.",
            notification_type='transaction'
        )
    
    messages.success(request, f"Successfully withdrawn ${withdrawal_amount:,.2f} from {property_obj.name}.")
    return redirect('real_estate_list')

@login_required
def news_detail(request, news_id):
    """Display a single news article in detail"""
    news_item = get_object_or_404(MarketNews, id=news_id, is_published=True)
    
    # Get related news (same category)
    related_news = MarketNews.objects.filter(
        is_published=True, 
        category=news_item.category
    ).exclude(id=news_id)[:3]
    
    context = {
        'news': news_item,
        'related_news': related_news,
    }
    return render(request, 'core/dashboard/news_detail.html', context)

# ============= NOTIFICATION API VIEWS =============

@login_required
def api_notifications(request):
    """API endpoint to get notifications for current user"""
    try:
        # Get ALL notifications (not just first 50)
        notifications = request.user.notifications.all().order_by('-created_at')
        
        print(f"DEBUG: User {request.user.email} has {notifications.count()} total notifications")
        
        notifications_list = []
        for n in notifications[:50]:  # Limit to 50 for response
            notifications_list.append({
                'id': n.id,
                'title': str(n.title),
                'message': str(n.message),
                'category': str(n.notification_type),
                'icon': 'fas fa-bell',
                'is_read': n.is_read,
                'time_ago': n.get_effective_created_at().strftime('%b %d, %Y'),
                'link': '#',
            })
            print(f"DEBUG: Added notification {n.id}: {n.title}")
        
        data = {
            'notifications': notifications_list,
            'unread_count': notifications.filter(is_read=False).count(),
            'debug_total': notifications.count()  # Add debug info
        }
        
        print(f"DEBUG: Returning {len(notifications_list)} notifications")
        
        return JsonResponse(data, safe=False)
        
    except Exception as e:
        print(f"ERROR in api_notifications: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'notifications': [],
            'unread_count': 0
        }, status=200)

@login_required
def api_notification_count(request):
    """API endpoint to get unread notification count"""
    notifications = request.user.notifications.all()
    
    category = request.GET.get('category')
    if category and category != 'dashboard':
        notifications = notifications.filter(notification_type=category)
    
    return JsonResponse({'unread_count': notifications.filter(is_read=False).count()})


@login_required
@require_POST
def api_mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def api_mark_all_read(request):
    """Mark all notifications as read (optionally filtered by category)"""
    notifications = request.user.notifications.filter(is_read=False)
    
    category = request.GET.get('category')
    if category and category != 'dashboard':
        notifications = notifications.filter(notification_type=category)
    
    count = notifications.count()
    notifications.update(is_read=True)
    return JsonResponse({'success': True, 'count': count})


def get_notification_icon(notification_type):
    """Return icon class for notification type"""
    icons = {
        'stock': 'fas fa-chart-line',
        'mineral': 'fas fa-gem',
        'real_estate': 'fas fa-building',
        'shop': 'fas fa-shopping-cart',
        'news': 'fas fa-newspaper',
        'deposit': 'fas fa-plus-circle',
        'withdraw': 'fas fa-minus-circle',
        'transaction': 'fas fa-exchange-alt',
        'system': 'fas fa-bell',
        'price_alert': 'fas fa-chart-simple',
        'admin_alert': 'fas fa-shield-alt',
    }
    return icons.get(notification_type, 'fas fa-bell')


def get_notification_link(notification):
    """Return link for notification based on type"""
    if notification.notification_type == 'stock':
        return '/stocks/'
    elif notification.notification_type == 'mineral':
        return '/minerals/'
    elif notification.notification_type == 'real_estate':
        return '/real-estate/'
    elif notification.notification_type == 'shop':
        return '/physical/'
    elif notification.notification_type == 'news':
        return '/news/'
    elif notification.notification_type == 'deposit':
        return '/deposit/'
    elif notification.notification_type == 'transaction':
        return '/transactions/'
    else:
        return '#'

# ============= CUSTOMER SUPPORT API VIEWS =============

# ============= CUSTOMER SUPPORT VIEWS =============

@login_required
def api_support_messages(request):
    """Get chat messages for the user's active ticket"""
    # Get ticket_id from request if provided
    ticket_id = request.GET.get('ticket_id')
    
    if ticket_id:
        # Admin viewing a specific ticket
        if request.user.is_staff:
            ticket = get_object_or_404(SupportTicket, id=ticket_id)
        else:
            ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    else:
        # Get or create active ticket for the user
        ticket = SupportTicket.objects.filter(
            user=request.user, 
            status__in=['open', 'in_progress']
        ).first()
        
        if not ticket:
            # Create a new ticket
            ticket = SupportTicket.objects.create(
                user=request.user,
                title=f"Support Chat - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                ticket_type='general',
                status='open'
            )
    
    # Mark messages as read (for admin viewing)
    if request.user.is_staff:
        ticket.messages.filter(is_user=True, is_read=False).update(is_read=True)
    else:
        ticket.messages.filter(is_user=False, is_read=False).update(is_read=True)
    
    messages_data = [{
        'id': msg.id,
        'message': msg.message,
        'is_user': msg.is_user,
        'created_at': msg.created_at.strftime('%H:%M %b %d'),
    } for msg in ticket.messages.all().order_by('created_at')]
    
    return JsonResponse({
        'messages': messages_data,
        'ticket_id': ticket.id,
        'ticket_status': ticket.status
    })


@login_required
@require_POST
def api_support_send_message(request):
    """Send a chat message"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        
        if not message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Get or create active ticket
        ticket = SupportTicket.objects.filter(
            user=request.user, 
            status__in=['open', 'in_progress']
        ).first()
        
        if not ticket:
            ticket = SupportTicket.objects.create(
                user=request.user,
                title=f"Support Chat - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                ticket_type='general',
                status='open'
            )
        
        # Save the message
        SupportMessage.objects.create(
            ticket=ticket,
            message=message,
            is_user=True,
            is_read=False
        )
        
        # Notify admins (create notification for staff)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        staff_users = User.objects.filter(is_staff=True)
        
        for staff in staff_users:
            Notification.objects.create(
                user=staff,
                title=f"New Support Message",
                message=f"User {request.user.email}: {message[:80]}...",
                notification_type='admin_alert',
                is_read=False
            )
        
        return JsonResponse({'success': True, 'ticket_id': ticket.id})
        
    except Exception as e:
        print(f"Error sending message: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def api_support_schedule_call(request):
    """Schedule a call with support"""
    import json
    from django.contrib.auth import get_user_model
    
    try:
        data = json.loads(request.body)
        
        phone_number = data.get('phone', '')
        date = data.get('date')
        time_slot = data.get('time')
        call_type = data.get('call_type', 'general')
        message = data.get('message', '')
        
        print(f"DEBUG: Scheduling call for {request.user.email}")
        print(f"  Phone: {phone_number}")
        print(f"  Date: {date}, Time: {time_slot}, Type: {call_type}")
        
        if not phone_number:
            return JsonResponse({'error': 'Phone number is required'}, status=400)
        if not date or not time_slot:
            return JsonResponse({'error': 'Date and time required'}, status=400)
        
        # Create the scheduled call
        scheduled_call = ScheduledCall.objects.create(
            user=request.user,
            phone_number=phone_number,
            scheduled_date=date,
            scheduled_time=time_slot,
            call_type=call_type,
            message=message,
            status='pending'
        )
        
        print(f"✅ Created call with ID: {scheduled_call.id}")
        
        # Notify all admins
        User = get_user_model()
        staff_users = User.objects.filter(is_staff=True)
        
        for staff in staff_users:
            Notification.objects.create(
                user=staff,
                title="📞 New Call Scheduled",
                message=f"User {request.user.email} (Phone: {phone_number}) scheduled a {call_type} call on {date} at {time_slot}",
                notification_type='admin_alert',
                is_read=False
            )
        
        # Notify user
        Notification.objects.create(
            user=request.user,
            title="Call Scheduled Successfully",
            message=f"Your {call_type} call has been scheduled for {date} at {time_slot}. We will call you at {phone_number}.",
            notification_type='system',
            is_read=False
        )
        
        return JsonResponse({'success': True, 'call_id': scheduled_call.id})
        
    except Exception as e:
        print(f"❌ ERROR scheduling call: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

def faq(request):
    """FAQ page"""
    return render(request, 'core/faq.html')     

@login_required
def api_search(request):
    query = request.GET.get('q', '').strip().lower()
    if not query:
        return JsonResponse({'results': []})
    
    results = []
    # Search stocks/minerals
    assets = Asset.objects.filter(name__icontains=query, is_active=True)[:10]
    for asset in assets:
        results.append({
            'title': f"{asset.symbol} - {asset.name}",
            'subtitle': f"${asset.current_price} · {asset.price_change_24h}%",
            'url': f"/asset/{asset.id}/",
            'icon': '📈' if asset.category == 'stock' else '💎',
            'category': asset.get_category_display()
        })
    
    # Search real estate
    properties = RealEstateProperty.objects.filter(name__icontains=query, status='funding')[:5]
    for prop in properties:
        results.append({
            'title': prop.name,
            'subtitle': f"{prop.location} · ${prop.price_per_share}/share",
            'url': f"/real-estate/{prop.id}/",
            'icon': '🏠',
            'category': 'Real Estate'
        })
    
    return JsonResponse({'results': results})

@login_required
@user_passes_test(is_admin)
@require_POST
def admin_reply_to_ticket(request, ticket_id):
    """Admin reply to a support ticket"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    message = request.POST.get('message', '').strip()
    
    if not message:
        messages.error(request, "Message cannot be empty")
        return redirect('admin_support_tickets')
    
    SupportMessage.objects.create(
        ticket=ticket,
        message=message,
        is_user=False,  # Admin reply
        is_read=False
    )
    
    # Notify user
    Notification.objects.create(
        user=ticket.user,
        title=f"Support Reply - Ticket #{ticket.id}",
        message=f"Support team has replied to your ticket: {message[:100]}...",
        notification_type='system',
        is_read=False
    )
    
    messages.success(request, "Reply sent successfully")
    return redirect('admin_support_tickets')

@login_required
@user_passes_test(is_admin)
def admin_support_tickets(request):
    """Admin view to manage support tickets"""
    tickets = SupportTicket.objects.all().order_by('-created_at')
    
    # ========== ADD EFFECTIVE DATES TO TICKETS ==========
    for ticket in tickets:
        ticket.effective_date = ticket.get_effective_created_at()
    # ====================================================
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        tickets = tickets.filter(status=status)
    
    # Get counts
    open_count = SupportTicket.objects.filter(status='open').count()
    in_progress_count = SupportTicket.objects.filter(status='in_progress').count()
    resolved_count = SupportTicket.objects.filter(status='resolved').count()
    
    # Get pending calls
    pending_calls = ScheduledCall.objects.filter(status='pending').order_by('scheduled_date', 'scheduled_time')
    
    # ========== ADD EFFECTIVE DATES TO PENDING CALLS ==========
    for call in pending_calls:
        call.effective_scheduled_date = call.get_effective_scheduled_date()
        call.effective_scheduled_time = call.get_effective_scheduled_time()
    # ===========================================================
    
    context = {
        'tickets': tickets,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'pending_calls': pending_calls,
        'current_status': status,
    }
    return render(request, 'core/admin/support_tickets.html', context)  


@login_required
def api_admin_notifications(request):
    """Get admin notifications (only for staff)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    notifications = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).order_by('-created_at')[:20]
    
    data = {
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'created_at': n.created_at.strftime('%H:%M %b %d'),
        } for n in notifications],
        'unread_count': notifications.count()
    }
    return JsonResponse(data)

@login_required
def support_tickets(request):
    """User view to see their own support tickets"""
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    # Add effective date to each ticket
    for ticket in tickets:
        ticket.effective_date = ticket.get_effective_created_at()
    
    context = {
        'tickets': tickets,
    }
    return render(request, 'core/support/user_tickets.html', context)


@login_required
def support_ticket_detail(request, ticket_id):
    """User view to see a specific ticket"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    
    # ========== ADD EFFECTIVE DATES ==========
    ticket.effective_date = ticket.get_effective_created_at()
    
    # Add effective dates to all messages in this ticket
    for msg in ticket.messages.all():
        msg.effective_date = msg.get_effective_created_at()
    # ==========================================
    
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        if message:
            SupportMessage.objects.create(
                ticket=ticket,
                message=message,
                is_user=True,
                is_read=False
            )
            # Notify admins
            from django.contrib.auth import get_user_model
            User = get_user_model()
            for staff in User.objects.filter(is_staff=True):
                Notification.objects.create(
                    user=staff,
                    title=f"New Reply from {request.user.email}",
                    message=f"Ticket #{ticket.id}: {message[:100]}...",
                    notification_type='admin_alert',
                    is_read=False
                )
            messages.success(request, "Message sent!")
            return redirect('support_ticket_detail', ticket_id=ticket.id)
    
    context = {
        'ticket': ticket,
    }
    return render(request, 'core/support/ticket_detail.html', context)    

@login_required
@user_passes_test(is_admin)
@require_POST
def admin_confirm_call(request, call_id):
    """Admin confirms a scheduled call"""
    call = get_object_or_404(ScheduledCall, id=call_id)
    call.status = 'confirmed'
    call.save()
    
    # Notify user
    Notification.objects.create(
        user=call.user,
        title="Call Confirmed",
        message=f"Your {call.get_call_type_display()} call on {call.scheduled_date} at {call.scheduled_time} has been confirmed.",
        notification_type='system',
        is_read=False
    )
    
    return JsonResponse({'success': True})    

@login_required
def api_unread_ticket_count(request):
    """Get count of unread support messages for the user"""
    # Get user's tickets with unread admin replies
    tickets = SupportTicket.objects.filter(user=request.user, status__in=['open', 'in_progress'])
    unread_count = 0
    
    for ticket in tickets:
        # Count messages that are not from user and not read
        unread_count += ticket.messages.filter(is_user=False, is_read=False).count()
    
    # Also check for pending scheduled calls
    pending_calls = ScheduledCall.objects.filter(user=request.user, status='pending').count()
    
    return JsonResponse({
        'unread_count': unread_count,
        'pending_calls': pending_calls,
        'total': unread_count + pending_calls
    })    

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import SupportTicket, SupportMessage, Notification
import json

@login_required
@user_passes_test(is_admin)
@csrf_exempt
def admin_reply_ticket(request, ticket_id):
    """API endpoint for admin to reply to support tickets"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        new_status = data.get('status', 'open')
        
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        
        # Create admin reply
        SupportMessage.objects.create(
            ticket=ticket,
            message=message,
            is_user=False,
            is_read=False
        )
        
        # Update ticket status
        ticket.status = new_status
        ticket.save()
        
        # Notify user
        Notification.objects.create(
            user=ticket.user,
            title=f"Support Reply - Ticket #{ticket.id}",
            message=f"Support team has replied to your ticket: {message[:100]}...",
            notification_type='system',
            is_read=False
        )
        
        return JsonResponse({'success': True, 'message': 'Reply sent successfully'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)   

from django.contrib import messages  # Add this import at the top of views.py

@login_required
@user_passes_test(is_admin)
def admin_reply_ticket_page(request, ticket_id):
    """Simple page for admin to reply to tickets"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    ticket_messages = ticket.messages.all().order_by('created_at')  # Renamed from 'messages' to 'ticket_messages'
    
    if request.method == 'POST':
        reply_text = request.POST.get('reply_text', '').strip()
        new_status = request.POST.get('status', ticket.status)
        
        if reply_text:
            SupportMessage.objects.create(
                ticket=ticket,
                message=reply_text,
                is_user=False,
                is_read=False
            )
            
            ticket.status = new_status
            ticket.save()
            
            # Notify user
            Notification.objects.create(
                user=ticket.user,
                title=f"Support Reply - Ticket #{ticket.id}",
                message=f"Support team has replied to your ticket.",
                notification_type='system',
                is_read=False
            )
            
            # This now works because 'messages' is Django's messages framework
            messages.success(request, "Reply sent successfully!")
            return redirect('admin_reply_ticket_page', ticket_id=ticket.id)
    
    context = {
        'ticket': ticket,
        'messages': ticket_messages,  # Updated variable name
    }
    return render(request, 'core/admin/reply_ticket.html', context)

# ============= REAL ESTATE DOCUMENT VIEWS =============

@login_required
def download_investment_certificate(request, investment_id):
    """Download Real Estate Investment Certificate PDF with effective dates"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    import qrcode
    from io import BytesIO
    import base64
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    # USE EFFECTIVE DATES AND VALUES
    issue_date = timezone.now()
    invested_date = investment.get_effective_invested_at()  # ← FIXED: Use effective date
    effective_amount = investment.get_effective_amount_invested()  # ← FIXED: Use effective amount
    effective_shares = investment.get_effective_shares()  # ← FIXED: Use effective shares
    
    # Calculate ownership percentage using effective shares
    total_shares = float(property_obj.total_shares) if property_obj.total_shares else 1
    ownership_percent = (float(effective_shares) / total_shares) * 100
    
    # Generate certificate number
    certificate_number = f"RE-CERT-{investment.id}-{datetime.now().year}-{investment.id:06d}"
    
    # Generate QR code for verification
    verification_url = f"https://qubix.com/verify/real-estate/{certificate_number}/"
    
    # Create QR code as base64
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert QR to base64
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    qr_data_url = f"data:image/png;base64,{qr_base64}"
    
    context = {
        'certificate_number': certificate_number,
        'issue_date': issue_date.strftime("%B %d, %Y"),
        'invested_date': invested_date.strftime("%B %d, %Y"),  # ← FIXED: Shows overridden date
        'user_name': request.user.get_full_name() or request.user.email,
        'property_name': property_obj.name,
        'location': property_obj.location,
        'number_of_shares': f"{int(effective_shares):,}",
        'ownership_percentage': f"{ownership_percent:.4f}%",
        'amount_invested': f"${effective_amount:,.2f}",
        'qr_verification_url': qr_data_url,
    }
    
    pdf = render_to_pdf('core/documents/real_estate/investment_certificate.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="investment_certificate_{investment.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_dividend_statement(request, dividend_id):
    """Download Dividend Statement PDF with effective dates"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    dividend = get_object_or_404(RealEstateDividend, id=dividend_id, investment__user=request.user)
    investment = dividend.investment
    property_obj = investment.property
    
    # USE EFFECTIVE DATES AND VALUES
    payment_date = dividend.get_effective_paid_at()
    dividend_period = dividend.get_effective_month()
    effective_amount = dividend.get_effective_amount()
    effective_shares = investment.get_effective_shares()
    
    # Calculate ownership percentage using effective shares
    total_shares = float(property_obj.total_shares) if property_obj.total_shares else 1
    ownership_percent = (float(effective_shares) / total_shares) * 100
    
    # FIX: Use Decimal for all calculations to avoid Decimal/float mixing
    management_fee_percent = Decimal('0.15')  # 15%
    operating_fees_percent = Decimal('0.10')  # 10%
    reserve_fee_percent = Decimal('0.05')     # 5%
    
    # Calculate total fee percentage
    total_fee_percent = management_fee_percent + operating_fees_percent + reserve_fee_percent
    
    # Calculate gross amount using Decimal division
    gross_amount = effective_amount / (Decimal('1') - total_fee_percent)
    management_fee = gross_amount * management_fee_percent
    operating_fees = gross_amount * operating_fees_percent
    reserve_fee = gross_amount * reserve_fee_percent
    
    # Generate transaction reference
    transaction_reference = f"DIV-{property_obj.id}-{dividend_period.strftime('%Y%m')}-{investment.id}"
    
    # Property performance data using effective values
    annual_cash_flow = property_obj.get_effective_annual_cash_flow() if hasattr(property_obj, 'get_effective_annual_cash_flow') else property_obj.annual_cash_flow
    purchase_price = property_obj.get_effective_purchase_price() if hasattr(property_obj, 'get_effective_purchase_price') else property_obj.purchase_price
    
    # Calculate gross yield (convert to float for display)
    gross_yield_percent = 0
    if purchase_price > 0:
        gross_yield_percent = float(annual_cash_flow) / float(purchase_price) * 100
    
    # Property value (assume 5% appreciation from purchase price)
    current_value = float(purchase_price) * 1.05
    value_change_percent = 5.0
    
    context = {
        # Basic info
        'transaction_reference': transaction_reference,
        'payment_date': payment_date.strftime("%B %d, %Y"),
        'dividend_period': dividend_period.strftime("%B %Y"),
        
        # Investor & Property
        'user_name': request.user.get_full_name() or request.user.email,
        'property_name': property_obj.name,
        'ownership_percentage': f"{ownership_percent:.2f}%",
        
        # Dividend amounts (convert Decimal to float for formatting)
        'net_paid': f"${float(effective_amount):,.2f}",
        'gross_amount': f"${float(gross_amount):,.2f}",
        'management_fee': f"${float(management_fee):,.2f}",
        'operating_fees': f"${float(operating_fees):,.2f}",
        'reserve_fee': f"${float(reserve_fee):,.2f}",
        
        # Property performance
        'occupancy_rate': "94%",
        'gross_yield': f"{gross_yield_percent:.1f}%",
        'property_value': f"${current_value:,.2f}",
        'value_change': f"+{value_change_percent:.1f}%",
    }
    
    pdf = render_to_pdf('core/documents/real_estate/dividend_statement.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="dividend_statement_{dividend.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)
    
@login_required
def download_purchase_invoice_real_estate(request, investment_id):
    """Download Real Estate Purchase Invoice PDF with effective dates"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    # USE EFFECTIVE DATES AND VALUES
    invoice_date = investment.get_effective_invested_at()
    effective_amount = investment.get_effective_amount_invested()
    effective_shares = investment.get_effective_shares()
    
    # Generate invoice number
    invoice_number = f"INV-RE-{investment.id}-{invoice_date.year}"
    
    # Generate order ID
    order_id = f"ORD-RE-{investment.id}-{invoice_date.strftime('%Y%m%d')}"
    
    # Calculate values
    shares_bought = f"{int(effective_shares):,}"
    price_per_share = f"${property_obj.price_per_share:,.2f}"
    total_amount = f"${effective_amount:,.2f}"
    
    context = {
        'invoice_number': invoice_number,
        'order_id': order_id,
        'invoice_date': invoice_date.strftime("%B %d, %Y"),
        'user_name': request.user.get_full_name() or request.user.email,
        'user_email': request.user.email,
        'property_name': property_obj.name,
        'property_location': property_obj.location,
        'shares_bought': shares_bought,
        'price_per_share': price_per_share,
        'total_amount': total_amount,
        'platform_fee': "Included",
        'payment_method': "Crypto / Bank Transfer",
        'transaction_hash': None,
    }
    
    pdf = render_to_pdf('core/documents/real_estate/purchase_invoice.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="purchase_invoice_{investment.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_property_prospectus(request, property_id):
    """Download Property Prospectus PDF"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    property_obj = get_object_or_404(RealEstateProperty, id=property_id)
    
    # Basic property info
    property_name = property_obj.name
    location = property_obj.location
    
    # Property type - FIXED: Check if is_fund attribute exists
    if hasattr(property_obj, 'is_fund') and property_obj.is_fund:
        property_type = "Real Estate Fund"
    else:
        property_type = "Single Family"
    
    # Investment term
    investment_term = "3-5 Year Hold"
    
    # Target APY (based on annual cash flow or default)
    if property_obj.annual_cash_flow and property_obj.purchase_price:
        target_apy = (float(property_obj.annual_cash_flow) / float(property_obj.purchase_price)) * 100
        target_apy_str = f"{target_apy:.1f}%"
    else:
        target_apy_str = "8.5%"
    
    # Property specifications
    bedrooms = property_obj.beds or "3"
    bathrooms = property_obj.baths or "2"
    sqft = f"{property_obj.sqft:,}" if property_obj.sqft else "1,850"
    year_built = property_obj.year_built or "2010"
    
    # Property description
    property_description = property_obj.property_description or f"{property_name} is a premium real estate asset located in {location}, offering stable rental income and long-term appreciation potential."
    
    # Financial projections
    purchase_price = float(property_obj.purchase_price) if property_obj.purchase_price else 500000
    annual_rental = float(property_obj.annual_cash_flow) if property_obj.annual_cash_flow else purchase_price * 0.08
    
    # Calculate projections
    y1_rental = annual_rental
    y2_rental = annual_rental * 1.03
    y3_rental = annual_rental * 1.06
    y5_rental = annual_rental * 1.12
    
    # Property value appreciation (assume 3-5% annually)
    y1_value = purchase_price * 1.04
    y2_value = purchase_price * 1.082
    y3_value = purchase_price * 1.125
    y5_value = purchase_price * 1.216
    
    # Returns and ROI
    y1_return = y1_rental
    y1_roi = (y1_return / purchase_price) * 100
    
    y2_return = y2_rental
    y2_roi = (y2_return / purchase_price) * 100
    
    y3_return = y3_rental
    y3_roi = (y3_return / purchase_price) * 100
    
    y5_return = y5_rental
    y5_roi = (y5_return / purchase_price) * 100
    
    # Market analysis
    market_trend = "Strong Growth"
    market_description = f"{location} has shown consistent population growth and job market expansion, driving demand for quality rental properties."
    area_yield = "7-9%"
    vacancy_rate = "4.2%"
    price_appreciation = "18.5%"
    
    # Rental yield
    rental_yield = f"{(annual_rental / purchase_price) * 100:.1f}%"
    capital_growth = "4-5%"
    total_investment = f"${purchase_price:,.2f}"
    
    # Management team
    fund_manager_name = "Alexander Chen"
    fund_manager_initials = "AC"
    fund_manager_bio = "15+ years in real estate private equity, former VP at Blackstone Real Estate"
    
    property_manager_name = "Sarah Williams"
    property_manager_initials = "SW"
    property_manager_bio = "10+ years property management experience, licensed real estate broker"
    
    legal_officer_name = "Michael Okonkwo"
    legal_officer_initials = "MO"
    legal_officer_bio = "Real estate attorney, compliance specialist, LLM in International Tax Law"
    
    context = {
        # Basic info
        'property_name': property_name,
        'location': location,
        'property_type': property_type,
        'investment_term': investment_term,
        'target_apy': target_apy_str,
        
        # Property specs
        'bedrooms': str(bedrooms),
        'bathrooms': str(bathrooms),
        'sqft': sqft,
        'year_built': str(year_built),
        'property_description': property_description,
        
        # Financial projections
        'rental_yield': rental_yield,
        'capital_growth': capital_growth,
        'total_investment': total_investment,
        
        # Year 1
        'y1_rental': f"${y1_rental:,.2f}",
        'y1_value': f"${y1_value:,.2f}",
        'y1_return': f"${y1_return:,.2f}",
        'y1_roi': f"+{y1_roi:.1f}%",
        
        # Year 2
        'y2_rental': f"${y2_rental:,.2f}",
        'y2_value': f"${y2_value:,.2f}",
        'y2_return': f"${y2_return:,.2f}",
        'y2_roi': f"+{y2_roi:.1f}%",
        
        # Year 3
        'y3_rental': f"${y3_rental:,.2f}",
        'y3_value': f"${y3_value:,.2f}",
        'y3_return': f"${y3_return:,.2f}",
        'y3_roi': f"+{y3_roi:.1f}%",
        
        # Year 5
        'y5_rental': f"${y5_rental:,.2f}",
        'y5_value': f"${y5_value:,.2f}",
        'y5_return': f"${y5_return:,.2f}",
        'y5_roi': f"+{y5_roi:.1f}%",
        
        # Market analysis
        'market_trend': market_trend,
        'market_description': market_description,
        'area_yield': area_yield,
        'vacancy_rate': vacancy_rate,
        'price_appreciation': price_appreciation,
        
        # Management team
        'fund_manager_initials': fund_manager_initials,
        'fund_manager_name': fund_manager_name,
        'fund_manager_bio': fund_manager_bio,
        'property_manager_initials': property_manager_initials,
        'property_manager_name': property_manager_name,
        'property_manager_bio': property_manager_bio,
        'legal_officer_initials': legal_officer_initials,
        'legal_officer_name': legal_officer_name,
        'legal_officer_bio': legal_officer_bio,
    }
    
    pdf = render_to_pdf('core/documents/real_estate/property_prospectus.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="prospectus_{property_obj.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_title_certificate(request, investment_id):
    """Download Fractional Title Certificate PDF with effective dates"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    import qrcode
    from io import BytesIO
    import base64
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    # USE EFFECTIVE VALUES
    effective_shares = investment.get_effective_shares()  # ← FIXED: Use effective shares
    effective_amount = investment.get_effective_amount_invested()  # ← FIXED: Use effective amount
    issue_date = timezone.now()
    
    # Calculate ownership percentage
    total_shares = float(property_obj.total_shares) if property_obj.total_shares else 1
    ownership_percent = (float(effective_shares) / total_shares) * 100
    
    # Generate title number
    title_number = f"TITLE-RE-{investment.id}-{datetime.now().year}-{investment.id:06d}"
    
    # Recording information
    recording_information = f"REC-{datetime.now().year}-{investment.id} · Book {investment.id % 1000} · Page {investment.id % 10000}"
    
    # Property legal description
    property_legal_description = f"All that certain parcel of land known as {property_obj.name}, located at {property_obj.address or property_obj.location}, County of {property_obj.location.split(',')[-1].strip() if ',' in property_obj.location else 'Registered'}, legally described in Deed Book {property_obj.id} at Page {property_obj.id * 10}, together with all improvements, easements, and appurtenances thereto belonging."
    
    # Generate QR code for verification
    verification_url = f"https://qubix.com/verify/title/{title_number}/"
    
    # Create QR code as base64
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert QR to base64
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    qr_data_url = f"data:image/png;base64,{qr_base64}"
    
    context = {
        'title_number': title_number,
        'issue_date': issue_date.strftime("%B %d, %Y"),
        'recording_information': recording_information,
        'owner_name': request.user.get_full_name() or request.user.email,
        'property_legal_description': property_legal_description,
        'ownership_percentage': f"{ownership_percent:.4f}%",
        'number_of_shares': f"{int(effective_shares):,}",
        'amount_invested': f"${effective_amount:,.2f}",  # ← FIXED: Added amount invested
        'verification_url': qr_data_url,
    }
    
    pdf = render_to_pdf('core/documents/real_estate/title_certificate.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="title_certificate_{investment.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_operating_agreement(request, investment_id):
    """Download Operating Agreement PDF"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    # Format dates
    effective_date_str = timezone.now().strftime("%B %d, %Y")
    
    # Generate agreement reference
    agreement_reference = f"OA-{property_obj.id}-{datetime.now().year}-{investment.id}"
    
    # Investor account ID
    investor_account = f"QUBIX-{request.user.id}-{request.user.id:06d}"
    
    # Qubix registration number
    qubix_reg_number = "QUBIX-RE-2024-001"
    
    # Fee rates (adjust as needed)
    management_fee_rate = "1.5% of gross rental income"
    reserve_rate = "5% of gross rental income"
    major_decision_threshold = "$50,000"
    lockup_period = "12 months"
    transfer_fee = "2.5%"
    performance_fee = "15%"
    hurdle_rate = "8%"
    distribution_frequency = "Monthly"
    
    context = {
        'agreement_reference': agreement_reference,
        'effective_date': effective_date_str,
        'qubix_reg_number': qubix_reg_number,
        'investor_name': request.user.get_full_name() or request.user.email,
        'investor_account': investor_account,
        'property_name': property_obj.name,
        'property_location': property_obj.location,
        'management_fee_rate': management_fee_rate,
        'distribution_frequency': distribution_frequency,
        'reserve_rate': reserve_rate,
        'major_decision_threshold': major_decision_threshold,
        'lockup_period': lockup_period,
        'transfer_fee': transfer_fee,
        'performance_fee': performance_fee,
        'hurdle_rate': hurdle_rate,
    }
    
    pdf = render_to_pdf('core/documents/real_estate/operating_agreement.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="operating_agreement_{investment.id}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_annual_report(request, investment_id):
    """Download Annual Report PDF"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    current_year = datetime.now().year
    
    # Get all dividends for this investment for the current year
    annual_dividends = sum(d.amount for d in investment.dividends.filter(month__year=current_year))
    
    # Convert Decimal values to float for calculations
    annual_cash_flow = float(property_obj.annual_cash_flow) if property_obj.annual_cash_flow else 0
    purchase_price = float(property_obj.purchase_price) if property_obj.purchase_price else 0
    amount_invested = float(investment.amount_invested)
    
    # Calculate annual rental yield
    annual_rental_yield = (annual_dividends / amount_invested * 100) if amount_invested > 0 else 0
    
    # Calculate property appreciation (assume 5% growth for demo)
    property_value_boy = purchase_price
    property_value_eoy = purchase_price * 1.05
    property_appreciation = property_value_eoy - property_value_boy
    
    # Calculate rental income (could come from property model or database)
    gross_rental_income = annual_cash_flow if annual_cash_flow > 0 else purchase_price * 0.08
    
    # Calculate expenses (percentages of gross rental income)
    mgmt_fee_total = gross_rental_income * 0.15
    maintenance_total = gross_rental_income * 0.10
    insurance_total = 2500.00
    property_tax = 3200.00
    platform_fee_total = 500.00
    reserve_total = 1000.00
    
    # Calculate net income
    total_expenses = mgmt_fee_total + maintenance_total + insurance_total + property_tax + platform_fee_total + reserve_total
    net_income = gross_rental_income - total_expenses
    
    # Occupancy data (you can calculate from actual data or use defaults)
    occupancy_rates = [92, 94, 96, 95]  # Q1, Q2, Q3, Q4
    
    # Calculate investor's share percentages (based on ownership)
    ownership_percent = investment.shares / property_obj.total_shares if property_obj.total_shares else 0
    investor_share = ownership_percent
    
    # Tax K-1 figures (investor's share)
    ordinary_income = net_income * investor_share * 0.70
    rental_income_k1 = net_income * investor_share * 0.30
    deductible_expenses = total_expenses * investor_share * 0.50
    
    context = {
        # Basic info
        'fiscal_year': current_year,
        'property_name': property_obj.name,
        
        # Performance KPIs
        'total_dividends_paid': f"${annual_dividends:,.2f}",
        'annual_rental_yield': f"{annual_rental_yield:.1f}%",
        'avg_occupancy': f"{sum(occupancy_rates)/len(occupancy_rates):.0f}%",
        'property_value_eoy': f"${property_value_eoy:,.2f}",
        
        # Income & Expenses
        'gross_rental_income': f"${gross_rental_income:,.2f}",
        'other_income': "$0.00",
        'mgmt_fee_total': f"${mgmt_fee_total:,.2f}",
        'maintenance_total': f"${maintenance_total:,.2f}",
        'insurance_total': f"${insurance_total:,.2f}",
        'property_tax': f"${property_tax:,.2f}",
        'platform_fee_total': f"${platform_fee_total:,.2f}",
        'reserve_total': f"${reserve_total:,.2f}",
        'net_income': f"${net_income:,.2f}",
        
        # Occupancy
        'q1_occupancy': f"{occupancy_rates[0]}%",
        'q2_occupancy': f"{occupancy_rates[1]}%",
        'q3_occupancy': f"{occupancy_rates[2]}%",
        'q4_occupancy': f"{occupancy_rates[3]}%",
        'q1_occupancy_pct': occupancy_rates[0],
        'q2_occupancy_pct': occupancy_rates[1],
        'q3_occupancy_pct': occupancy_rates[2],
        'q4_occupancy_pct': occupancy_rates[3],
        
        # Property Appreciation
        'property_value_boy': f"${property_value_boy:,.2f}",
        'property_appreciation': f"${property_appreciation:,.2f}",
        
        # Tax K-1 Summary
        'ordinary_income': f"${ordinary_income:,.2f}",
        'rental_income_k1': f"${rental_income_k1:,.2f}",
        'deductible_expenses': f"${deductible_expenses:,.2f}",
    }
    
    pdf = render_to_pdf('core/documents/real_estate/annual_report.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="annual_report_{investment.id}_{current_year}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)


@login_required
def download_capital_call(request, investment_id):
    """Download Capital Call Notice PDF"""
    from django.utils import timezone
    from datetime import datetime, timedelta
    from decimal import Decimal
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    # Current date
    notice_date = timezone.now()
    due_date = notice_date + timedelta(days=30)
    
    # Format dates
    notice_date_str = notice_date.strftime("%B %d, %Y")
    due_date_str = due_date.strftime("%B %d, %Y")
    
    # Calculate ownership percentage
    total_shares = float(property_obj.total_shares) if property_obj.total_shares else 1
    ownership_percent = (float(investment.shares) / total_shares) * 100
    
    # Generate notice reference
    notice_reference = f"CC-{property_obj.id}-{datetime.now().year}-{investment.id}"
    
    # Capital call amount (example: 5% of invested amount)
    # You can make this dynamic based on actual capital call needs
    amount_invested = float(investment.amount_invested)
    total_capital_call = amount_invested * 0.05  # 5% capital call
    amount_requested = total_capital_call
    
    # Investor name
    investor_name = request.user.get_full_name() or request.user.email
    
    # Capital call purpose items
    capital_call_items = [
        {'description': 'Property Renovation & Upgrades', 'amount': f'${total_capital_call * 0.40:,.2f}'},
        {'description': 'Legal & Closing Costs', 'amount': f'${total_capital_call * 0.15:,.2f}'},
        {'description': 'Reserve Fund Contribution', 'amount': f'${total_capital_call * 0.20:,.2f}'},
        {'description': 'Capital Expenditure Reserve', 'amount': f'${total_capital_call * 0.25:,.2f}'},
    ]
    
    purpose_description = f"Capital contribution for {property_obj.name} improvements and reserves"
    
    context = {
        'notice_reference': notice_reference,
        'notice_date': notice_date_str,
        'due_date': due_date_str,
        'property_name': property_obj.name,
        'investor_name': investor_name,
        'amount_requested': f"${amount_requested:,.2f}",
        'ownership_percentage': f"{ownership_percent:.2f}%",
        'total_capital_call': f"${total_capital_call:,.2f}",
        'capital_call_items': capital_call_items,
        'purpose_description': purpose_description,
        'payment_method': "Wire Transfer / Crypto (USDC/BTC)",
        'bank_account_details': "Contact support@qubix.io for wire instructions",
    }
    
    pdf = render_to_pdf('core/documents/real_estate/capital_call.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="capital_call_{investment.id}_{datetime.now().year}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_exit_statement(request, investment_id):
    """Download Exit Statement PDF"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    # Format dates
    closing_date = timezone.now()
    closing_date_str = closing_date.strftime("%B %d, %Y")
    
    # Calculate ownership percentage
    total_shares = float(property_obj.total_shares) if property_obj.total_shares else 1
    ownership_percent = (float(investment.shares) / total_shares) * 100
    
    # Generate exit reference
    exit_reference = f"EXIT-{property_obj.id}-{datetime.now().year}-{investment.id}"
    
    # Financial calculations
    original_investment = float(investment.amount_invested)
    
    # Assume property sold at 25% appreciation
    appreciation_rate = 0.25
    sale_price = (float(property_obj.purchase_price) if property_obj.purchase_price else 500000) * (1 + appreciation_rate)
    
    # Investor's share of sale
    investor_sale_share = sale_price * (ownership_percent / 100)
    
    # Calculate costs
    closing_costs = sale_price * 0.06  # 6% agent fees & closing
    outstanding_debt = 0  # Assume no debt for simplicity
    
    # Performance fee (15% of profit above original investment)
    gross_profit = investor_sale_share - original_investment
    performance_fee_rate = 0.15
    performance_fee = gross_profit * performance_fee_rate if gross_profit > 0 else 0
    
    # Net sale proceeds (total)
    net_sale_proceeds = sale_price - closing_costs - outstanding_debt
    
    # Investor's gross distribution
    gross_distribution = investor_sale_share - (closing_costs * (ownership_percent / 100)) - (outstanding_debt * (ownership_percent / 100))
    
    # Estimated capital gains tax (20% of profit)
    estimated_tax = (gross_distribution - original_investment) * 0.20 if gross_distribution > original_investment else 0
    
    # Net profit and total payout
    net_profit = gross_distribution - original_investment - estimated_tax - performance_fee
    total_payout = original_investment + net_profit
    
    # Total return percentage
    total_return_pct = ((total_payout - original_investment) / original_investment) * 100 if original_investment > 0 else 0
    
    context = {
        # Basic info
        'exit_reference': exit_reference,
        'closing_date': closing_date_str,
        
        # Investor & Property
        'investor_name': request.user.get_full_name() or request.user.email,
        'property_name': property_obj.name,
        
        # Sale information
        'sale_price': f"${sale_price:,.2f}",
        'ownership_percentage': f"{ownership_percent:.2f}%",
        'original_investment': f"${original_investment:,.2f}",
        'total_return_pct': f"+{total_return_pct:.1f}%",
        
        # Cost breakdown
        'closing_costs': f"${closing_costs:,.2f}",
        'outstanding_debt': f"${outstanding_debt:,.2f}",
        'performance_fee_rate': f"{performance_fee_rate * 100:.0f}%",
        'performance_fee': f"${performance_fee:,.2f}",
        
        # Distribution calculations
        'net_sale_proceeds': f"${net_sale_proceeds:,.2f}",
        'gross_distribution': f"${gross_distribution:,.2f}",
        'estimated_tax': f"${estimated_tax:,.2f}",
        'net_profit': f"${net_profit:,.2f}",
        'total_payout': f"${total_payout:,.2f}",
        
        # Payment details
        'payment_method': "Wire Transfer / ACH",
        'wire_reference': exit_reference,
    }
    
    pdf = render_to_pdf('core/documents/real_estate/exit_statement.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="exit_statement_{investment.id}_{datetime.now().year}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
def download_k1_tax_summary(request, investment_id):
    """Download K-1 Tax Summary PDF"""
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    investment = get_object_or_404(RealEstateInvestment, id=investment_id, user=request.user)
    property_obj = investment.property
    
    # Current tax year (previous year)
    current_year = datetime.now().year - 1
    tax_year_str = str(current_year)
    
    # Format dates
    issue_date_str = timezone.now().strftime("%B %d, %Y")
    
    # Calculate ownership percentage
    total_shares = float(property_obj.total_shares) if property_obj.total_shares else 1
    ownership_percent = (float(investment.shares) / total_shares) * 100
    
    # Generate K-1 reference
    k1_reference = f"K1-{property_obj.id}-{current_year}-{investment.id}"
    
    # Partnership name
    partnership_name = f"Qubix {property_obj.name} Holdings LLC"
    
    # Calculate annual dividends
    annual_dividends = sum(d.amount for d in investment.dividends.filter(month__year=current_year))
    dividend_amount = float(annual_dividends)
    
    # Calculate income figures based on investment amount and dividends
    amount_invested = float(investment.amount_invested)
    
    # Part I - Income figures
    ordinary_business_income = dividend_amount * 0.70
    rental_real_estate_income = dividend_amount * 0.30
    other_net_rental_income = 0.00
    guaranteed_payments = 0.00
    interest_income = 0.00
    ordinary_dividends = dividend_amount
    net_ltcg = dividend_amount * 0.10
    other_deductions = amount_invested * 0.02
    self_employment = 0.00
    
    # Part II - Deductions
    depreciation_deduction = amount_invested * 0.03
    operating_expense_deductions = dividend_amount * 0.15
    mortgage_interest_deduction = amount_invested * 0.02
    total_deductions = depreciation_deduction + operating_expense_deductions + mortgage_interest_deduction + other_deductions
    
    # Part III - Capital Account Analysis
    beginning_capital = amount_invested
    capital_contributed = 0.00
    current_year_income = dividend_amount
    distributions_paid = dividend_amount
    withdrawals = 0.00
    ending_capital = beginning_capital + capital_contributed + current_year_income - distributions_paid - withdrawals
    
    context = {
        # Basic info
        'tax_year': tax_year_str,
        'issue_date': issue_date_str,
        'k1_reference': k1_reference,
        
        # Partner & Entity
        'investor_name': request.user.get_full_name() or request.user.email,
        'partnership_name': partnership_name,
        'ownership_percentage': f"{ownership_percent:.4f}%",
        'property_name': property_obj.name,
        
        # Part I - Income
        'ordinary_business_income': f"${ordinary_business_income:,.2f}",
        'rental_real_estate_income': f"${rental_real_estate_income:,.2f}",
        'other_net_rental_income': f"${other_net_rental_income:,.2f}",
        'guaranteed_payments': f"${guaranteed_payments:,.2f}",
        'interest_income': f"${interest_income:,.2f}",
        'ordinary_dividends': f"${ordinary_dividends:,.2f}",
        'net_ltcg': f"${net_ltcg:,.2f}",
        'other_deductions': f"${other_deductions:,.2f}",
        'self_employment': f"${self_employment:,.2f}",
        
        # Part II - Deductions
        'depreciation_deduction': f"${depreciation_deduction:,.2f}",
        'operating_expense_deductions': f"${operating_expense_deductions:,.2f}",
        'mortgage_interest_deduction': f"${mortgage_interest_deduction:,.2f}",
        'total_deductions': f"${total_deductions:,.2f}",
        
        # Part III - Capital Account
        'beginning_capital': f"${beginning_capital:,.2f}",
        'capital_contributed': f"${capital_contributed:,.2f}",
        'current_year_income': f"${current_year_income:,.2f}",
        'distributions_paid': f"${distributions_paid:,.2f}",
        'withdrawals': f"${withdrawals:,.2f}",
        'ending_capital': f"${ending_capital:,.2f}",
    }
    
    pdf = render_to_pdf('core/documents/real_estate/k1_tax_summary.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="k1_tax_summary_{investment.id}_{current_year}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

# ============= PASSWORD RESET VIEWS =============

def password_reset_request(request):
    """Request password reset email"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Generate token and uid
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build reset URL
            reset_url = request.build_absolute_uri(
                f'/reset-password/{uid}/{token}/'
            )
            
            # Send password reset email using HTML template
            context = {
                'user_name': user.get_full_name() or user.username,
                'user_email': user.email,
                'reset_url': reset_url,
                'support_url': '/support/',
            }
            
            send_html_email(
                subject='Reset Your Qubix Password',
                template_name='core/emails/password_reset_email.html',
                context=context,
                to_email=user.email
            )
            
            messages.success(request, 
                "Password reset link sent! Check your email for instructions.")
            return redirect('login')
            
        except CustomUser.DoesNotExist:
            # Don't reveal if user exists or not for security
            messages.success(request, 
                "If an account exists with that email, we've sent a reset link.")
            return redirect('login')
    
    return render(request, 'core/auth/password_reset_request.html')


def password_reset_confirm(request, uidb64, token):
    """Confirm password reset and set new password"""
    User = get_user_model()
    
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            if password1 and password1 == password2:
                user.set_password(password1)
                user.save()
                
                # Send confirmation email
                context = {
                    'user_name': user.get_full_name() or user.username,
                    'login_url': '/login/',
                }
                send_html_email(
                    subject='Your Qubix Password Has Been Reset',
                    template_name='core/emails/password_reset_confirmation.html',
                    context=context,
                    to_email=user.email
                )
                
                messages.success(request, 
                    "Password reset successful! Please login with your new password.")
                return redirect('login')
            else:
                messages.error(request, "Passwords do not match.")
        
        return render(request, 'core/auth/password_reset_confirm.html', {'validlink': True})
    else:
        return render(request, 'core/auth/password_reset_confirm.html', {'validlink': False})

@login_required
def user_profile(request):
    """User profile page - view and edit personal information"""
    user = request.user
    portfolio = user.portfolio
    
    context = {
        'user': user,
        'portfolio': portfolio,
        'full_name': user.get_full_name(),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': getattr(user, 'phone', ''),
        'country': getattr(user, 'country', ''),
        'wallet_address': getattr(user, 'wallet_address', ''),
        'member_since': user.date_joined if hasattr(user, 'date_joined') else user.created_at,
        'total_invested': portfolio.total_value(),
        'total_dividends': portfolio.total_dividends,
        'total_deposits': portfolio.total_deposits,
        'total_withdrawals': portfolio.total_withdrawals,
        'cash_balance': portfolio.cash_balance,
    }
    return render(request, 'core/dashboard/profile.html', context)


@login_required
@require_POST
def update_profile(request):
    """Update user profile information"""
    user = request.user
    
    # Get form data
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    country = request.POST.get('country', '').strip()
    wallet_address = request.POST.get('wallet_address', '').strip()
    
    # Update user fields
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    if phone:
        user.phone = phone
    if country:
        user.country = country
    if wallet_address:
        user.wallet_address = wallet_address
    
    user.save()
    
    messages.success(request, "Profile updated successfully!")
    return redirect('user_profile')    