from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from decimal import Decimal
from .models import SupportTicket, SupportMessage, ScheduledCall
from django.utils import timezone
from .models import (
    CustomUser, Asset, Portfolio, Holding, Transaction, WithdrawalRequest,
    PriceCandle, MarketNews, Notification, PriceAlert,
    RealEstateProperty, RealEstateInvestment, RealEstateDividend,
    CryptoCurrency, CryptoDeposit,
    PhysicalProduct, PhysicalHolding, PhysicalTransaction
)
from .utils.email_utils import (
    send_deposit_approved_email, 
    send_withdrawal_approved_email, 
    send_withdrawal_rejected_email,
    send_physical_order_confirmation_email,
    send_physical_order_shipped_email,
    send_physical_order_delivered_email,
)
# ============= CUSTOM USER ADMIN =============
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'effective_created_at', 'email_verified', 'is_staff', 'impersonate_button')
    list_filter = ('email_verified', 'is_staff', 'is_active', 'country')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Verification', {'fields': ('email_verified', 'verification_code', 'verification_code_expires')}),
        ('Contact Info', {'fields': ('phone', 'country', 'wallet_address')}),
        ('Admin Override Settings', {
            'fields': ('override_created_at', 'override_updated_at'),
            'description': '⚠️ Override account creation dates. Leave blank to use original values.'
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('email', 'email_verified', 'phone', 'country')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def effective_created_at(self, obj):
        effective = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', effective.strftime('%Y-%m-%d %H:%M'))
        return effective.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Created At (Effective)'
    
    def impersonate_button(self, obj):
        if obj.id == getattr(self, '_current_user_id', None):
            return "Current User"
        return format_html(
            '<a class="button" href="{}" style="background: #f59e0b; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">'
            '<i class="fas fa-mask"></i> Impersonate</a>',
            reverse('admin_impersonate_start', args=[obj.id])
        )
    impersonate_button.short_description = 'Impersonate'
    impersonate_button.allow_tags = True
    
    def get_queryset(self, request):
        self._current_user_id = request.user.id
        return super().get_queryset(request)


# ============= ASSET ADMIN =============
class AssetAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'category', 'current_price_display', 'price_change_display', 'price_range_display', 'price_update_enabled', 'is_active')
    list_filter = ('category', 'is_active', 'price_update_enabled')
    search_fields = ('symbol', 'name', 'description')
    list_editable = ('price_update_enabled', 'is_active')
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {'fields': ('symbol', 'name', 'category', 'description', 'image', 'is_active')}),
        ('Current Pricing', {'fields': ('current_price', 'price_change_24h', 'volume_24h')}),
        ('Market Data', {'fields': ('market_cap', 'dividend_yield', 'pe_ratio', 'revenue_ttm', 'net_income_ttm', 'shares_outstanding', 'beta'), 'classes': ('collapse',)}),
        ('Price Simulation', {'fields': ('price_min', 'price_max', 'volatility', 'price_update_enabled', 'last_price_update'), 'description': 'Set min/max price range for automatic price fluctuations.', 'classes': ('wide',)}),
        ('24-Hour Tracking', {'fields': ('price_24h_ago', 'volume_24h_ago'), 'classes': ('collapse',)}),
        ('Additional Info', {'fields': ('website',), 'classes': ('collapse',)}),
    )
    
    readonly_fields = ('last_price_update', 'created_at', 'updated_at')
    
    def current_price_display(self, obj):
        color = 'green' if obj.price_change_24h >= 0 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">${}</span>', color, obj.current_price)
    current_price_display.short_description = 'Current Price'
    
    def price_change_display(self, obj):
        color = 'green' if obj.price_change_24h >= 0 else 'red'
        arrow = '▲' if obj.price_change_24h >= 0 else '▼'
        return format_html('<span style="color: {};">{} {}%</span>', color, arrow, abs(obj.price_change_24h))
    price_change_display.short_description = '24h Change'
    
    def price_range_display(self, obj):
        if obj.price_min and obj.price_max:
            return f"${obj.price_min} - ${obj.price_max}"
        return "Not set"
    price_range_display.short_description = 'Price Range'
    
    actions = ['enable_price_updates', 'disable_price_updates']
    
    def enable_price_updates(self, request, queryset):
        queryset.update(price_update_enabled=True)
        self.message_user(request, f"{queryset.count()} assets enabled for price updates.")
    enable_price_updates.short_description = "Enable price updates"
    
    def disable_price_updates(self, request, queryset):
        queryset.update(price_update_enabled=False)
        self.message_user(request, f"{queryset.count()} assets disabled for price updates.")
    disable_price_updates.short_description = "Disable price updates"


# ============= PRICE CANDLE ADMIN =============
class PriceCandleAdmin(admin.ModelAdmin):
    list_display = ('asset', 'open', 'high', 'low', 'close', 'volume', 'timestamp')
    list_filter = ('asset', 'timestamp')
    search_fields = ('asset__symbol', 'asset__name')
    readonly_fields = ('asset', 'open', 'high', 'low', 'close', 'volume', 'timestamp')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# ============= PORTFOLIO ADMIN =============
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'cash_balance', 'total_value', 'unrealized_pl', 'holdings_count', 'real_estate_count', 'created_at')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Info', {'fields': ('user',)}),
        ('Balances', {'fields': ('cash_balance', 'total_deposits', 'total_withdrawals', 'total_dividends')}),
        ('Performance', {'fields': ('ytd_performance',), 'classes': ('collapse',)}),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def total_value(self, obj):
        return f"${obj.total_value():,.2f}"
    total_value.short_description = 'Total Value'
    
    def unrealized_pl(self, obj):
        pl = obj.unrealized_pl()
        return f"${pl:,.2f}"
    unrealized_pl.short_description = 'Unrealized P&L'
    
    def holdings_count(self, obj):
        return obj.holdings.count()
    holdings_count.short_description = 'Stocks/Minerals'
    
    def real_estate_count(self, obj):
        try:
            return obj.user.real_estate_investments.count()
        except:
            return 0
    real_estate_count.short_description = 'Real Estate'


# ============= HOLDING ADMIN =============
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('id_link', 'user_email', 'asset_symbol', 'effective_quantity', 'effective_average_price', 'current_value', 'profit_loss', 'has_override')
    list_filter = ('asset__category',)
    search_fields = ('portfolio__user__email', 'asset__symbol', 'asset__name')
    
    fieldsets = (
        ('Portfolio Information', {'fields': ('portfolio',)}),
        ('Asset Information', {'fields': ('asset',)}),
        ('Position Details', {'fields': ('quantity', 'average_price')}),
        ('Admin Override Settings', {
            'fields': ('override_quantity', 'override_average_price', 'override_purchase_date'),
            'description': '⚠️ Override quantity, average price, or purchase date. Leave blank to use original values.'
        }),
    )
    
    def id_link(self, obj):
        url = reverse('admin:core_holding_change', args=[obj.id])
        return format_html('<a href="{}" style="color: #f59e0b; font-weight: bold;">#{}</a>', url, obj.id)
    id_link.short_description = 'ID'
    
    def user_email(self, obj):
        return obj.portfolio.user.email
    user_email.short_description = 'User'
    
    def asset_symbol(self, obj):
        return obj.asset.symbol
    asset_symbol.short_description = 'Asset'
    
    def effective_quantity(self, obj):
        qty = obj.get_effective_quantity()
        if obj.override_quantity:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', qty)
        return qty
    effective_quantity.short_description = 'Quantity (Effective)'
    
    def effective_average_price(self, obj):
        price = obj.get_effective_average_price()
        if obj.override_average_price:
            return format_html('<span style="color: #f59e0b;">🔧 ${}</span>', price)
        return f"${price}"
    effective_average_price.short_description = 'Avg Price (Effective)'
    
    def current_value(self, obj):
        try:
            value = obj.current_value()
            return f"${value:,.2f}"
        except:
            return "$0.00"
    current_value.short_description = 'Current Value'
    
    def profit_loss(self, obj):
        try:
            pl = obj.unrealized_pl()
            color = 'green' if pl >= 0 else 'red'
            return format_html('<span style="color: {};">${:,.2f}</span>', color, pl)
        except:
            return "$0.00"
    profit_loss.short_description = 'Profit/Loss'
    
    def has_override(self, obj):
        return obj.override_quantity is not None or obj.override_average_price is not None or obj.override_purchase_date is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'


# ============= TRANSACTION ADMIN =============
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id_link', 'user_email', 'transaction_type', 'asset_symbol', 'quantity', 'effective_total', 'status', 'effective_created_at', 'has_override')
    list_filter = ('transaction_type', 'status')
    search_fields = ('user__email', 'asset__symbol', 'asset__name')
    
    fieldsets = (
        ('Transaction Info', {'fields': ('user', 'transaction_type', 'status')}),
        ('Asset Details', {'fields': ('asset',)}),
        ('Amount Details', {'fields': ('quantity', 'total_amount')}),
        ('Admin Override Settings', {
            'fields': ('override_total_amount', 'override_created_at'),
            'description': '⚠️ Override transaction amount or date. Leave blank to use original values.'
        }),
    )
    
    def id_link(self, obj):
        url = reverse('admin:core_transaction_change', args=[obj.id])
        return format_html('<a href="{}" style="color: #f59e0b; font-weight: bold;">#{}</a>', url, obj.id)
    id_link.short_description = 'ID'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def asset_symbol(self, obj):
        return obj.asset.symbol if obj.asset else '-'
    asset_symbol.short_description = 'Asset'
    
    def effective_total(self, obj):
        total = obj.get_effective_total_amount()
        if obj.override_total_amount:
            return format_html('<span style="color: #f59e0b;">🔧 ${}</span>', total)
        return f"${total}"
    effective_total.short_description = 'Total (Effective)'
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Date (Effective)'
    
    def has_override(self, obj):
        return obj.override_total_amount is not None or obj.override_created_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    actions = ['approve_transactions', 'reject_transactions']
    
    def approve_transactions(self, request, queryset):
        for transaction in queryset:
            if transaction.status == 'pending':
                transaction.status = 'approved'
                transaction.approved_at = timezone.now()
                transaction.save()
                
                if transaction.transaction_type == 'buy' and transaction.asset:
                    holding, created = Holding.objects.get_or_create(
                        portfolio=transaction.user.portfolio,
                        asset=transaction.asset,
                        defaults={'quantity': Decimal('0'), 'average_price': Decimal('0')}
                    )
                    new_quantity = holding.quantity + transaction.quantity
                    if holding.quantity == 0:
                        holding.average_price = transaction.total_amount / transaction.quantity
                    else:
                        holding.average_price = ((holding.average_price * holding.quantity) + transaction.total_amount) / new_quantity
                    holding.quantity = new_quantity
                    holding.save()
                    portfolio = transaction.user.portfolio
                    portfolio.cash_balance -= transaction.total_amount
                    portfolio.save()
                    
                elif transaction.transaction_type == 'sell' and transaction.asset:
                    holding = Holding.objects.filter(portfolio=transaction.user.portfolio, asset=transaction.asset).first()
                    if holding:
                        holding.quantity -= transaction.quantity
                        if holding.quantity <= 0:
                            holding.delete()
                        else:
                            holding.save()
                    portfolio = transaction.user.portfolio
                    portfolio.cash_balance += transaction.total_amount
                    portfolio.save()
                    
                elif transaction.transaction_type == 'deposit':
                    portfolio = transaction.user.portfolio
                    portfolio.cash_balance += transaction.total_amount
                    portfolio.total_deposits += transaction.total_amount
                    portfolio.save()
                    
                elif transaction.transaction_type == 'withdraw':
                    portfolio = transaction.user.portfolio
                    portfolio.cash_balance -= transaction.total_amount
                    portfolio.total_withdrawals += transaction.total_amount
                    portfolio.save()
                    
        self.message_user(request, f"{queryset.count()} transactions approved.")
    approve_transactions.short_description = "Approve selected transactions"
    
    def reject_transactions(self, request, queryset):
        count = 0
        for transaction in queryset:
            if transaction.status == 'pending':
                transaction.status = 'rejected'
                transaction.save()
                count += 1
        self.message_user(request, f"{count} transactions rejected.")
    reject_transactions.short_description = "Reject selected transactions"


class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'amount', 'effective_created_at', 'status', 'has_override')
    list_filter = ('status',)
    search_fields = ('user__email',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('User Info', {'fields': ('user',)}),
        ('Withdrawal Details', {'fields': ('amount',)}),
        ('Status', {'fields': ('status',)}),
        ('Admin Override Settings', {
            'fields': ('override_created_at', 'override_approved_at'),
            'description': '⚠️ Override request date or approval date. Leave blank to use original values.',
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Created At (Effective)'
    
    def has_override(self, obj):
        return obj.override_created_at is not None or obj.override_approved_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    actions = ['approve_withdrawals', 'reject_withdrawals']
    
    def approve_withdrawals(self, request, queryset):
        from .utils.email_utils import send_withdrawal_approved_email
        from .models import Notification, Transaction
        
        for withdrawal in queryset:
            if withdrawal.status == 'pending':
                withdrawal.status = 'approved'
                withdrawal.processed_at = timezone.now()
                withdrawal.save()
                
                send_withdrawal_approved_email(withdrawal.user, withdrawal)
                
                Notification.objects.create(
                    user=withdrawal.user,
                    title="Withdrawal Approved ✅",
                    message=f"Your withdrawal request of ${withdrawal.amount:,.2f} has been approved. Funds will be sent to your wallet shortly.",
                    notification_type='withdraw',
                    is_read=False
                )    

                Transaction.objects.create(
                    user=withdrawal.user,
                    transaction_type='withdraw',
                    total_amount=withdrawal.amount,
                    status='approved'
                )
        self.message_user(request, f"{queryset.count()} withdrawal requests approved.")
    approve_withdrawals.short_description = "Approve selected withdrawals"
    
    def reject_withdrawals(self, request, queryset):
        from .utils.email_utils import send_withdrawal_rejected_email
        from .models import Notification, Transaction
        
        for withdrawal in queryset:
            if withdrawal.status == 'pending':
                withdrawal.status = 'rejected'
                withdrawal.processed_at = timezone.now()
                withdrawal.save()
                
                # Send rejection email
                try:
                    send_withdrawal_rejected_email(withdrawal.user, withdrawal)
                except Exception as e:
                    print(f"Email error: {e}")
                
                # Send notification
                Notification.objects.create(
                    user=withdrawal.user,
                    title="Withdrawal Rejected ❌",
                    message=f"Your withdrawal request of ${withdrawal.amount:,.2f} has been rejected. Please contact support for details.",
                    notification_type='withdraw',
                    is_read=False
                )
                
                # Return money to user's balance
                portfolio = withdrawal.user.portfolio
                portfolio.cash_balance += withdrawal.amount
                portfolio.total_withdrawals -= withdrawal.amount
                portfolio.save()
                
                # Update or create rejected transaction
                pending_transaction = Transaction.objects.filter(
                    user=withdrawal.user,
                    transaction_type='withdraw',
                    total_amount=withdrawal.amount,
                    status='pending'
                ).first()
                
                if pending_transaction:
                    pending_transaction.status = 'rejected'
                    pending_transaction.save()
                else:
                    Transaction.objects.create(
                        user=withdrawal.user,
                        transaction_type='withdraw',
                        total_amount=withdrawal.amount,
                        status='rejected',
                        notes=f"Withdrawal rejected. Original request #{withdrawal.id}"
                    )
                
        self.message_user(request, f"{queryset.count()} withdrawal requests rejected. Funds returned to user balances.")
    reject_withdrawals.short_description = "Reject selected withdrawals"


# ============= MARKET NEWS ADMIN =============
class MarketNewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_published', 'published_at', 'created_at')
    list_filter = ('category', 'is_published')
    search_fields = ('title', 'content', 'summary')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Content', {'fields': ('title', 'summary', 'content')}),
        ('Media', {'fields': ('image',)}),
        ('Metadata', {'fields': ('category',)}),
        ('Publication', {'fields': ('is_published', 'published_at')}),
    )
    
    actions = ['publish_news', 'unpublish_news']
    
    def publish_news(self, request, queryset):
        count = 0
        for news in queryset:
            if not news.is_published:
                news.is_published = True
                news.published_at = timezone.now()
                news.save()
                count += 1
        self.message_user(request, f"{count} news articles published.")
    publish_news.short_description = "Publish selected news"
    
    def unpublish_news(self, request, queryset):
        count = 0
        for news in queryset:
            if news.is_published:
                news.is_published = False
                news.save()
                count += 1
        self.message_user(request, f"{count} news articles unpublished.")
    unpublish_news.short_description = "Unpublish selected news"


# ============= NOTIFICATION ADMIN =============
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'title', 'notification_type', 'effective_date', 'is_read', 'created_at', 'has_override')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('user__email', 'title', 'message')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Recipient', {'fields': ('user',)}),
        ('Notification', {'fields': ('title', 'message', 'notification_type')}),
        ('Status', {'fields': ('is_read',)}),
        ('Admin Override Settings', {
            'fields': ('override_created_at',),
            'description': '⚠️ Override notification date. Leave blank to use original date.',
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email if obj.user else 'System'
    user_email.short_description = 'User'
    
    def effective_date(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_date.short_description = 'Effective Date'
    
    def has_override(self, obj):
        return obj.override_created_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        count = queryset.update(is_read=True)
        self.message_user(request, f"{count} notifications marked as read.")
    mark_as_read.short_description = "Mark as read"
    
    def mark_as_unread(self, request, queryset):
        count = queryset.update(is_read=False)
        self.message_user(request, f"{count} notifications marked as unread.")
    mark_as_unread.short_description = "Mark as unread"


# ============= PRICE ALERT ADMIN =============
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'asset_symbol', 'target_price', 'alert_type', 'is_triggered', 'effective_created_at', 'effective_triggered_at', 'has_override')
    list_filter = ('alert_type', 'is_triggered')
    search_fields = ('user__email', 'asset__symbol')
    readonly_fields = ('created_at', 'triggered_at')
    
    fieldsets = (
        ('User & Asset', {'fields': ('user', 'asset')}),
        ('Alert Conditions', {'fields': ('target_price', 'alert_type')}),
        ('Status', {'fields': ('is_triggered', 'triggered_at')}),
        ('Admin Override Settings', {
            'fields': ('override_created_at', 'override_triggered_at'),
            'description': '⚠️ Override creation date or triggered date. Leave blank to use original values.',
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def asset_symbol(self, obj):
        return obj.asset.symbol if obj.asset else '-'
    asset_symbol.short_description = 'Asset'
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Created At (Effective)'
    
    def effective_triggered_at(self, obj):
        if obj.triggered_at:
            date = obj.get_effective_triggered_at()
            if obj.override_triggered_at:
                return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
            return date.strftime('%Y-%m-%d %H:%M')
        return '-'
    effective_triggered_at.short_description = 'Triggered At (Effective)'
    
    def has_override(self, obj):
        return obj.override_created_at is not None or obj.override_triggered_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    actions = ['reset_alerts']
    
    def reset_alerts(self, request, queryset):
        count = queryset.update(is_triggered=False, triggered_at=None)
        self.message_user(request, f"{count} alerts reset.")
    reset_alerts.short_description = "Reset selected alerts"


# ============= REAL ESTATE ADMINS =============
class RealEstatePropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'status', 'total_available', 'funded_percent', 'investor_count', 'created_at')
    list_filter = ('status', 'location')
    search_fields = ('name', 'location', 'address')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'location', 'address', 'status', 'badge')}),
        ('Specifications', {'fields': ('beds', 'baths', 'sqft', 'year_built')}),
        ('Financials', {'fields': ('purchase_price', 'total_available', 'monthly_rent', 'annual_cash_flow', 'appreciation_rate')}),
        ('Funding', {'fields': ('funded_percent', 'investor_count', 'total_shares', 'price_per_share')}),
        ('Content', {'fields': ('market_description', 'property_description')}),
        ('Documents', {'fields': ('series_overview', 'use_of_proceeds', 'risk_factors', 'offering_circular'), 'classes': ('collapse',)}),
        ('Media', {'fields': ('main_image', 'gallery_images'), 'classes': ('collapse',)}),
        ('Timeline', {'fields': ('timeline_updates',), 'classes': ('collapse',)}),
        ('Map Location', {'fields': ('latitude', 'longitude'), 'description': 'Enter coordinates for the property location.', 'classes': ('wide',)}),
    )


class RealEstateInvestmentAdmin(admin.ModelAdmin):
    list_display = ('id_link', 'user', 'property', 'shares', 'effective_amount', 'effective_invested_at', 'has_override')
    list_filter = ('property',)
    search_fields = ('user__email', 'property__name')
    
    fieldsets = (
        ('Investment Info', {'fields': ('user', 'property', 'shares', 'amount_invested')}),
        ('Investment Terms', {'fields': ('investment_period_months', 'maturity_date', 'expected_annual_return', 'expected_value_at_maturity')}),
        ('Personal Metrics', {'fields': ('personal_remaining', 'personal_funded_percent', 'personal_investor_count')}),
        ('Admin Override Settings', {
            'fields': ('override_invested_at', 'override_amount_invested'),
            'description': '⚠️ Override investment date or amount. Leave blank to use original values.'
        }),
    )
    
    def id_link(self, obj):
        url = reverse('admin:core_realestateinvestment_change', args=[obj.id])
        return format_html('<a href="{}" style="color: #f59e0b; font-weight: bold;">#{}</a>', url, obj.id)
    id_link.short_description = 'ID'
    
    def effective_amount(self, obj):
        amount = obj.get_effective_amount_invested()
        if obj.override_amount_invested:
            return format_html('<span style="color: #f59e0b;">🔧 ${}</span>', amount)
        return f"${amount}"
    effective_amount.short_description = 'Amount (Effective)'
    
    def effective_invested_at(self, obj):
        date = obj.get_effective_invested_at()
        if obj.override_invested_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_invested_at.short_description = 'Invested At (Effective)'
    
    def has_override(self, obj):
        return obj.override_invested_at is not None or obj.override_amount_invested is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'


class RealEstateDividendAdmin(admin.ModelAdmin):
    list_display = ('investment', 'amount', 'month', 'paid_at')
    list_filter = ('month',)
    search_fields = ('investment__user__email', 'investment__property__name')


# ============= CRYPTO ADMINS =============
@admin.register(CryptoCurrency)
class CryptoCurrencyAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'rate_usd', 'wallet_address', 'is_active', 'sort_order']
    list_editable = ['rate_usd', 'is_active', 'sort_order']
    search_fields = ['symbol', 'name']
    list_filter = ['is_active']
    
    fieldsets = (
        ('Basic Info', {'fields': ('symbol', 'name', 'is_active', 'sort_order')}),
        ('Exchange Rate', {'fields': ('rate_usd',)}),
        ('Wallet Details', {'fields': ('wallet_address', 'network')}),
        ('Limits', {'fields': ('min_deposit_usd', 'max_deposit_usd')}),
    )


@admin.register(CryptoDeposit)
class CryptoDepositAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'crypto', 'usd_amount', 'crypto_amount', 'status', 'effective_created_at', 'expires_at', 'has_override']
    list_filter = ['status', 'crypto']
    search_fields = ['user__email', 'transaction_hash']
    readonly_fields = ['qr_code', 'get_time_remaining_display', 'created_at', 'confirmed_at']
    
    fieldsets = (
        ('Deposit Info', {'fields': ('user', 'crypto', 'usd_amount', 'crypto_amount', 'rate_used', 'wallet_address')}),
        ('Status Tracking', {'fields': ('status', 'expires_at', 'confirmed_at', 'completed_at')}),
        ('Admin Override Settings', {
            'fields': ('override_created_at', 'override_confirmed_at'),
            'description': '⚠️ Override creation date or confirmation date. Leave blank to use original values.',
            'classes': ('collapse',),
        }),
    )
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Created At (Effective)'
    
    def has_override(self, obj):
        return obj.override_created_at is not None or obj.override_confirmed_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    actions = ['mark_as_paid', 'mark_as_completed']
    
    def mark_as_paid(self, request, queryset):
        from .utils.email_utils import send_deposit_approved_email
        
        for deposit in queryset:
            if deposit.status == 'pending':
                deposit.status = 'paid'
                deposit.confirmed_at = timezone.now()
                deposit.save()
                # ========== ADD EMAIL ==========
                send_deposit_approved_email(deposit.user, deposit)
                # ==============================
        self.message_user(request, f"{queryset.count()} deposits marked as paid.")
    mark_as_paid.short_description = "Mark as Paid"
    
    def mark_as_completed(self, request, queryset):
        from .utils.email_utils import send_deposit_approved_email
        
        for deposit in queryset:
            if deposit.status == 'paid':
                deposit.status = 'completed'
                deposit.completed_at = timezone.now()
                deposit.save()
                
                # ========== ADD EMAIL ==========
                send_deposit_approved_email(deposit.user, deposit)
                # ==============================
                
                Notification.objects.create(
                    user=deposit.user,
                     title="Deposit Completed ✅",
                     message=f"Your deposit of ${deposit.usd_amount:,.2f} has been approved and added to your balance.",
                     notification_type='deposit',
                     is_read=False
                )     
                portfolio = deposit.user.portfolio
                portfolio.cash_balance += Decimal(str(deposit.usd_amount))
                portfolio.total_deposits += Decimal(str(deposit.usd_amount))
                portfolio.save()
                
                transaction = Transaction.objects.filter(
                    user=deposit.user,
                    transaction_type='deposit',
                    total_amount=deposit.usd_amount,
                    status='pending'
                ).first()
                
                if transaction:
                    transaction.status = 'approved'
                    transaction.approved_at = timezone.now()
                    transaction.save()
                else:
                    Transaction.objects.create(
                        user=deposit.user,
                        transaction_type='deposit',
                        total_amount=deposit.usd_amount,
                        status='approved'
                    )
        self.message_user(request, f"{queryset.count()} deposits marked as completed.")
    mark_as_completed.short_description = "Mark as Completed"
    
    def get_time_remaining_display(self, obj):
        return obj.get_time_remaining()
    get_time_remaining_display.short_description = "Time Remaining"


# ============= PHYSICAL PRODUCTS ADMINS =============
class PhysicalProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'current_price', 'spot_price', 'stock_quantity', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'mint')
    list_editable = ('current_price', 'spot_price', 'stock_quantity', 'is_active')
    
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'year', 'category', 'is_active')}),
        ('Specifications', {'fields': ('specification', 'purity', 'weight', 'mint', 'dimensions')}),
        ('Pricing', {'fields': ('current_price', 'spot_price', 'price_change_24h', 'shipping_fee')}),
        ('Inventory', {'fields': ('stock_quantity',)}),
        ('Media', {'fields': ('main_image', 'gallery_images')}),
    )


class PhysicalHoldingAdmin(admin.ModelAdmin):
    list_display = ('id_link', 'user_email', 'product', 'effective_quantity', 'service_type', 'effective_value', 'effective_purchase_date', 'has_override')
    list_filter = ('service_type', 'delivery_status')
    search_fields = ('user__email', 'product__name')
    
    fieldsets = (
        ('Holding Info', {'fields': ('user', 'product', 'quantity', 'average_price', 'service_type')}),
        ('Location & Status', {'fields': ('vault_location', 'delivery_status', 'tracking_number', 'shipping_address')}),
        ('Admin Override Settings', {
            'fields': ('override_quantity', 'override_current_value', 'override_purchase_date'),
            'description': '⚠️ Override quantity, value, or purchase date. Leave blank to use original values.'
        }),
    )
    
    def id_link(self, obj):
        url = reverse('admin:core_physicalholding_change', args=[obj.id])
        return format_html('<a href="{}" style="color: #f59e0b; font-weight: bold;">#{}</a>', url, obj.id)
    id_link.short_description = 'ID'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def effective_quantity(self, obj):
        qty = obj.get_effective_quantity()
        if obj.override_quantity:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', qty)
        return qty
    effective_quantity.short_description = 'Quantity (Effective)'
    
    def effective_value(self, obj):
        val = obj.get_effective_current_value()
        if obj.override_current_value:
            return format_html('<span style="color: #f59e0b;">🔧 ${:,.2f}</span>', val)
        return f"${val:,.2f}"
    effective_value.short_description = 'Current Value (Effective)'
    
    def effective_purchase_date(self, obj):
        date = obj.get_effective_purchase_date()
        if obj.override_purchase_date:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_purchase_date.short_description = 'Purchase Date (Effective)'
    
    def has_override(self, obj):
        return obj.override_quantity is not None or obj.override_current_value is not None or obj.override_purchase_date is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'


class PhysicalTransactionAdmin(admin.ModelAdmin):
    list_display = ('id_link', 'user_email', 'product', 'quantity', 'effective_total', 'payment_method', 'delivery_method', 'status_colored', 'effective_created_at', 'has_override')
    list_filter = ('status', 'delivery_method', 'payment_method')
    search_fields = ('user__email', 'product__name', 'transaction_hash')
    
    fieldsets = (
        ('Order Information', {'fields': ('user', 'product', 'quantity', 'total_amount', 'shipping_fee', 'delivery_method', 'status')}),
        ('Payment Details', {'fields': ('payment_method', 'transaction_hash', 'crypto_amount', 'payment_confirmed_at')}),
        ('Shipping Details', {'fields': ('shipping_address', 'tracking_number', 'estimated_delivery'), 'classes': ('collapse',)}),
        ('Vault Details', {'fields': ('vault_location', 'vault_slot', 'certificate_number'), 'classes': ('collapse',)}),
        ('Admin Override Settings', {
            'fields': ('override_total_amount', 'override_created_at'),
            'description': '⚠️ Override transaction amount or date. Leave blank to use original values.'
        }),
    )
    
    def id_link(self, obj):
        url = reverse('admin:core_physicaltransaction_change', args=[obj.id])
        return format_html('<a href="{}" style="color: #f59e0b; font-weight: bold;">#{}</a>', url, obj.id)
    id_link.short_description = 'ID'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def effective_total(self, obj):
        total = obj.get_effective_total_amount()
        if obj.override_total_amount:
            return format_html('<span style="color: #f59e0b;">🔧 ${}</span>', total)
        return f"${total}"
    effective_total.short_description = 'Total (Effective)'
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Date (Effective)'
    
    def has_override(self, obj):
        return obj.override_total_amount is not None or obj.override_created_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    def status_colored(self, obj):
        colors = {
            'under_review': '#f0b90b',
            'confirmed_processing': '#3d7eff',
            'confirmed_vault': '#0ecb81',
            'shipped': '#0ecb81',
            'delivered': '#0ecb81',
            'cancelled': '#f6465d',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{}20; color:{}; padding:4px 8px; border-radius:6px;">{}</span>', 
                          color, color, obj.get_status_display())
    status_colored.short_description = 'Status'
    
    actions = ['confirm_payment_action', 'mark_as_shipped_action', 'mark_as_delivered_action', 'reject_order_action']
    
    def confirm_payment_action(self, request, queryset):
        import random
        from .utils.email_utils import send_physical_order_confirmation_email
        
        updated = 0
        for transaction in queryset:
            if transaction.status == 'under_review':
                transaction.status = 'confirmed_processing' if transaction.delivery_method == 'shipping' else 'confirmed_vault'
                transaction.confirmed_at = timezone.now()
                
                if transaction.delivery_method == 'vault':
                    transaction.certificate_number = f"QUBIX-{transaction.id}-{random.randint(10000, 99999)}"
                    
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
                
                transaction.save()
                
                # ========== ADD EMAIL ==========
                send_physical_order_confirmation_email(transaction.user, transaction)
                # ===============================
                
                Notification.objects.create(
                    user=transaction.user,
                    title="Order Confirmed",
                    message=f"Your order for {transaction.quantity} x {transaction.product.name} has been confirmed.",
                    notification_type='transaction',
                    is_read=False
                )
                updated += 1
        
        self.message_user(request, f"{updated} order(s) confirmed.")
    confirm_payment_action.short_description = "✅ Confirm Payment"
    
    def mark_as_shipped_action(self, request, queryset):
        from .utils.email_utils import send_physical_order_shipped_email
        
        updated = 0
        for transaction in queryset:
            if transaction.delivery_method == 'shipping' and transaction.status == 'confirmed_processing':
                transaction.status = 'shipped'
                transaction.shipped_at = timezone.now()
                transaction.save()
                
                PhysicalHolding.objects.create(
                    user=transaction.user,
                    product=transaction.product,
                    quantity=transaction.quantity,
                    average_price=transaction.product.current_price,
                    service_type='shipped',
                    transaction=transaction,
                    shipping_address=transaction.shipping_address,
                    tracking_number=transaction.tracking_number,
                    delivery_status='transit'
                )
                
                # ========== ADD EMAIL ==========
                send_physical_order_shipped_email(transaction.user, transaction)
                # ===============================
                
                Notification.objects.create(
                    user=transaction.user,
                    title="Order Shipped!",
                    message=f"Your order for {transaction.quantity} x {transaction.product.name} has been shipped.",
                    notification_type='transaction',
                    is_read=False
                )
                updated += 1
        
        self.message_user(request, f"{updated} order(s) marked as shipped.")
    mark_as_shipped_action.short_description = "📦 Mark as Shipped"
    
    def mark_as_delivered_action(self, request, queryset):
        from .utils.email_utils import send_physical_order_delivered_email
        
        updated = 0
        for transaction in queryset:
            if transaction.status == 'shipped':
                transaction.status = 'delivered'
                transaction.delivered_at = timezone.now()
                transaction.save()
                
                holding = PhysicalHolding.objects.filter(transaction=transaction).first()
                if holding:
                    holding.delivery_status = 'delivered'
                    holding.save()
                
                # ========== ADD EMAIL ==========
                send_physical_order_delivered_email(transaction.user, transaction)
                # ===============================
                
                Notification.objects.create(
                    user=transaction.user,
                    title="Order Delivered!",
                    message=f"Your order for {transaction.quantity} x {transaction.product.name} has been delivered.",
                    notification_type='transaction',
                    is_read=False
                )
                updated += 1
        
        self.message_user(request, f"{updated} order(s) marked as delivered.")
    mark_as_delivered_action.short_description = "✅ Mark as Delivered"
    
    def reject_order_action(self, request, queryset):
        from .utils.email_utils import send_physical_order_confirmation_email  # Or create a rejection email
        
        updated = 0
        for transaction in queryset:
            if transaction.status == 'under_review':
                transaction.status = 'cancelled'
                transaction.save()
                
                # Optional: Send rejection email
                # send_physical_order_cancelled_email(transaction.user, transaction)
                
                Notification.objects.create(
                    user=transaction.user,
                    title="Order Cancelled",
                    message=f"Your order for {transaction.quantity} x {transaction.product.name} has been cancelled.",
                    notification_type='transaction',
                    is_read=False
                )
                updated += 1
        
        self.message_user(request, f"{updated} order(s) cancelled.")
    reject_order_action.short_description = "❌ Reject Order"

# ============= CUSTOMER SUPPORT ADMINS =============
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'ticket_type', 'status', 'effective_created_at', 'view_ticket_link', 'has_override']
    list_filter = ['status', 'ticket_type']
    search_fields = ['user__email', 'title', 'messages__message']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Ticket Info', {'fields': ('user', 'title', 'ticket_type', 'status')}),
        ('View & Reply', {'fields': ('view_ticket_link',)}),
        ('Admin Override Settings', {
            'fields': ('override_created_at', 'override_updated_at'),
            'description': '⚠️ Override ticket creation date or last update date. Leave blank to use original values.',
            'classes': ('collapse',),
        }),
    )
    
    def view_ticket_link(self, obj):
        url = f'/support/reply/{obj.id}/'
        return format_html(
            '<a href="{}" target="_blank" style="background: #f0b90b; color: #000; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">'
            '✉️ Click Here to View & Reply to this Ticket</a><br><br>'
            '<span style="font-size: 11px; color: #888;">⬆️ Click the button above to open reply page in new tab</span>',
            url
        )
    view_ticket_link.short_description = 'Reply to User'
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Created At (Effective)'
    
    def has_override(self, obj):
        return obj.override_created_at is not None or obj.override_updated_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'ticket', 'message_preview', 'is_user', 'is_read', 'effective_created_at', 'has_override']
    list_filter = ['is_user', 'is_read']
    search_fields = ['message', 'ticket__user__email']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Message Info', {'fields': ('ticket', 'message', 'is_user', 'is_read')}),
        ('Admin Override Settings', {
            'fields': ('override_created_at',),
            'description': '⚠️ Override message timestamp. Leave blank to use original value.',
            'classes': ('collapse',),
        }),
    )
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Created At (Effective)'
    
    def has_override(self, obj):
        return obj.override_created_at is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'


class ScheduledCallAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'phone_number', 'effective_scheduled_date', 'effective_scheduled_time', 'call_type', 'status', 'effective_created_at', 'has_override']
    list_filter = ['status', 'call_type']
    search_fields = ['user__email', 'phone_number', 'message']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Call Info', {'fields': ('user', 'phone_number', 'call_type', 'message', 'status')}),
        ('Schedule', {'fields': ('scheduled_date', 'scheduled_time')}),
        ('Admin Override Settings', {
            'fields': ('override_created_at', 'override_scheduled_date', 'override_scheduled_time'),
            'description': '⚠️ Override call request date, scheduled date, or scheduled time. Leave blank to use original values.',
            'classes': ('collapse',),
        }),
    )
    
    def effective_scheduled_date(self, obj):
        date = obj.get_effective_scheduled_date()
        if obj.override_scheduled_date:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date)
        return date
    effective_scheduled_date.short_description = 'Scheduled Date (Effective)'
    
    def effective_scheduled_time(self, obj):
        time = obj.get_effective_scheduled_time()
        if obj.override_scheduled_time:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', time)
        return time
    effective_scheduled_time.short_description = 'Scheduled Time (Effective)'
    
    def effective_created_at(self, obj):
        date = obj.get_effective_created_at()
        if obj.override_created_at:
            return format_html('<span style="color: #f59e0b;">🔧 {}</span>', date.strftime('%Y-%m-%d %H:%M'))
        return date.strftime('%Y-%m-%d %H:%M')
    effective_created_at.short_description = 'Created At (Effective)'
    
    def has_override(self, obj):
        return obj.override_created_at is not None or obj.override_scheduled_date is not None or obj.override_scheduled_time is not None
    has_override.boolean = True
    has_override.short_description = 'Overridden'
    
    actions = ['mark_confirmed', 'mark_completed', 'mark_cancelled']
    
    def mark_confirmed(self, request, queryset):
        for call in queryset:
            call.status = 'confirmed'
            call.save()
            Notification.objects.create(
                user=call.user,
                title="Call Confirmed",
                message=f"Your {call.get_call_type_display()} call on {call.get_effective_scheduled_date()} at {call.get_effective_scheduled_time()} has been confirmed. We will call you at {call.phone_number}.",
                notification_type='system',
                is_read=False
            )
        self.message_user(request, f"{queryset.count()} calls marked as confirmed.")
    mark_confirmed.short_description = "Mark as Confirmed"
    
    def mark_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"{queryset.count()} calls marked as completed.")
    mark_completed.short_description = "Mark as Completed"
    
    def mark_cancelled(self, request, queryset):
        for call in queryset:
            call.status = 'cancelled'
            call.save()
            Notification.objects.create(
                user=call.user,
                title="Call Cancelled",
                message=f"Your scheduled call on {call.get_effective_scheduled_date()} at {call.get_effective_scheduled_time()} has been cancelled.",
                notification_type='system',
                is_read=False
            )
        self.message_user(request, f"{queryset.count()} calls marked as cancelled.")
    mark_cancelled.short_description = "Mark as Cancelled"


# ============= REGISTER ALL MODELS =============
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Asset, AssetAdmin)
admin.site.register(PriceCandle, PriceCandleAdmin)
admin.site.register(Portfolio, PortfolioAdmin)
admin.site.register(Holding, HoldingAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(WithdrawalRequest, WithdrawalRequestAdmin)
admin.site.register(MarketNews, MarketNewsAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(PriceAlert, PriceAlertAdmin)
admin.site.register(RealEstateProperty, RealEstatePropertyAdmin)
admin.site.register(RealEstateInvestment, RealEstateInvestmentAdmin)
admin.site.register(RealEstateDividend, RealEstateDividendAdmin)
admin.site.register(PhysicalProduct, PhysicalProductAdmin)
admin.site.register(PhysicalHolding, PhysicalHoldingAdmin)
admin.site.register(PhysicalTransaction, PhysicalTransactionAdmin)
admin.site.register(SupportTicket, SupportTicketAdmin)
admin.site.register(SupportMessage, SupportMessageAdmin)
admin.site.register(ScheduledCall, ScheduledCallAdmin)

# Customize admin site
admin.site.site_header = 'Qubix Investment Platform Admin'
admin.site.site_title = 'Qubix Admin'
admin.site.index_title = 'Welcome to Qubix Admin Dashboard'