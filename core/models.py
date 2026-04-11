from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import random
import uuid
from decimal import Decimal

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_code_expires = models.DateTimeField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    country = models.CharField(max_length=100, default='Ghana')
    wallet_address = models.CharField(max_length=255, blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC', blank=True, null=True)  # ← ADD THIS LINE
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override account creation date")
    override_updated_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override last update date")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    def get_effective_created_at(self):
        return self.override_created_at or self.created_at

    def get_effective_updated_at(self):
        return self.override_updated_at or self.updated_at

    def generate_verification_code(self):
        code = str(random.randint(100000, 999999))
        self.verification_code = code
        self.verification_code_expires = timezone.now() + timezone.timedelta(minutes=10)
        self.save()
        return code

    def verify_email(self, code):
        if (self.verification_code == code and 
            self.verification_code_expires and 
            self.verification_code_expires > timezone.now()):
            self.email_verified = True
            self.verification_code = None
            self.verification_code_expires = None
            self.save()
            return True
        return False

class Asset(models.Model):
    CATEGORY_CHOICES = [
        ('stock', 'Stock'),
        ('mineral', 'Mineral'),
        ('crypto', 'Cryptocurrency'),
        ('etf', 'ETF'),
    ]
    
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='stock')
    
    current_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price_change_24h = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    volume_24h = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    market_cap = models.CharField(max_length=50, blank=True, null=True)
    dividend_yield = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    pe_ratio = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    revenue_ttm = models.CharField(max_length=50, blank=True, null=True)
    net_income_ttm = models.CharField(max_length=50, blank=True, null=True)
    shares_outstanding = models.CharField(max_length=50, blank=True, null=True)
    beta = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    
    price_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    volatility = models.DecimalField(max_digits=5, decimal_places=2, default=0.5)
    price_update_enabled = models.BooleanField(default=True)
    last_price_update = models.DateTimeField(null=True, blank=True)
    
    price_24h_ago = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    volume_24h_ago = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    description = models.TextField(blank=True)
    website = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='assets/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['symbol']
    
    def __str__(self):
        return f"{self.symbol} - {self.name}"
    
    def update_price(self):
        if not self.price_update_enabled or not self.price_min or not self.price_max:
            return False
        try:
            import random
            current_price = float(self.current_price)
            min_price = float(self.price_min)
            max_price = float(self.price_max)
            vol = float(self.volatility) / 100
            change_percent = random.uniform(-vol, vol)
            new_price = current_price * (1 + change_percent)
            if new_price < min_price:
                new_price = min_price
            elif new_price > max_price:
                new_price = max_price
            if current_price > 0:
                actual_change = ((new_price - current_price) / current_price) * 100
            else:
                actual_change = 0
            self.current_price = Decimal(str(round(new_price, 2)))
            self.price_change_24h = Decimal(str(round(actual_change, 2)))
            self.last_price_update = timezone.now()
            self.save()
            try:
                from .models import PriceCandle
                PriceCandle.add_price_point(self, self.current_price, Decimal(str(random.uniform(10000, 1000000))))
            except:
                pass
            return True
        except Exception as e:
            print(f"Price update error for {self.symbol}: {e}")
            return False
    
    def update_24h_stats(self):
        from datetime import timedelta
        yesterday = timezone.now() - timedelta(hours=24)
        candles = self.candles.filter(timestamp__gte=yesterday).order_by('timestamp')
        if candles.exists():
            oldest = candles.first()
            self.price_change_24h = ((self.current_price - oldest.open) / oldest.open) * 100
            self.volume_24h = sum(c.volume for c in candles)
            self.save()
    
    def get_historical_prices(self, period='1W'):
        from datetime import timedelta
        period_map = {
            '1D': timedelta(days=1), '1W': timedelta(days=7), '1M': timedelta(days=30),
            '3M': timedelta(days=90), '1Y': timedelta(days=365), '5Y': timedelta(days=1825),
        }
        delta = period_map.get(period, timedelta(days=7))
        cutoff = timezone.now() - delta
        candles = self.candles.filter(timestamp__gte=cutoff).order_by('timestamp')
        if candles.exists():
            return [float(candle.close) for candle in candles]
        else:
            return self._generate_historical_data(period)
    
    def get_historical_data_with_dates(self, period='1W'):
        from datetime import timedelta
        period_map = {
            '1D': timedelta(days=1), '1W': timedelta(days=7), '1M': timedelta(days=30),
            '3M': timedelta(days=90), '1Y': timedelta(days=365),
        }
        delta = period_map.get(period, timedelta(days=7))
        cutoff = timezone.now() - delta
        candles = self.candles.filter(timestamp__gte=cutoff).order_by('timestamp')
        if candles.exists():
            return [{'date': candle.timestamp.strftime('%Y-%m-%d %H:%M'), 'open': float(candle.open),
                    'high': float(candle.high), 'low': float(candle.low), 'close': float(candle.close),
                    'volume': float(candle.volume)} for candle in candles]
        else:
            return self._generate_historical_data_with_dates(period)
    
    def _generate_historical_data(self, period):
        import random
        points_map = {'1D': 24, '1W': 7*24, '1M': 30, '3M': 90, '1Y': 365, '5Y': 1825}
        points = points_map.get(period, 30)
        data = []
        current_price = float(self.current_price)
        volatility = float(self.volatility) / 100 if self.volatility else 0.01
        if period == '5Y':
            base_price = current_price * 0.3
        elif period == '1Y':
            base_price = current_price * 0.6
        elif period == '3M':
            base_price = current_price * 0.8
        else:
            base_price = current_price * 0.85
        for i in range(points):
            trend = (i / points) * (current_price - base_price)
            random_walk = 0
            for _ in range(3):
                random_walk += (random.random() - 0.5) * (base_price * volatility)
            random_walk /= 3
            price = base_price + trend + random_walk
            min_price = float(self.price_min) if self.price_min else base_price * 0.5
            max_price = float(self.price_max) if self.price_max else base_price * 1.5
            price = max(min_price, min(max_price, price))
            data.append(round(price, 2))
        return data
    
    def _generate_historical_data_with_dates(self, period):
        import random
        from datetime import timedelta
        if period == '1D':
            points, interval = 96, timedelta(minutes=15)
        elif period == '1W':
            points, interval = 7*96, timedelta(minutes=15)
        elif period == '1M':
            points, interval = 30, timedelta(days=1)
        elif period == '3M':
            points, interval = 90, timedelta(days=1)
        else:
            points, interval = 52, timedelta(days=7)
        data = []
        current_price = float(self.current_price)
        volatility = float(self.volatility) / 100 if self.volatility else 0.01
        base_price = current_price * 0.85
        now = timezone.now()
        for i in range(points - 1, -1, -1):
            timestamp = now - (interval * i)
            progress = (points - i) / points
            trend = progress * (current_price - base_price)
            random_walk = 0
            for _ in range(3):
                random_walk += (random.random() - 0.5) * (base_price * volatility)
            random_walk /= 3
            price = base_price + trend + random_walk
            if interval < timedelta(days=1):
                hour_variation = random.random() * (base_price * 0.02)
                price += hour_variation
            min_price = float(self.price_min) if self.price_min else base_price * 0.5
            max_price = float(self.price_max) if self.price_max else base_price * 1.5
            price = max(min_price, min(max_price, price))
            data.append({'date': timestamp.strftime('%Y-%m-%d %H:%M'), 'open': round(price * (1 - random.random() * 0.02), 2),
                        'high': round(price * (1 + random.random() * 0.03), 2), 'low': round(price * (1 - random.random() * 0.03), 2),
                        'close': round(price, 2), 'volume': round(random.uniform(10000, 1000000), 0)})
        return data
    
    def get_price_for_period(self, period='1W'):
        from datetime import timedelta
        period_map = {
            '1D': timedelta(days=1), '1W': timedelta(days=7), '1M': timedelta(days=30),
            '3M': timedelta(days=90), '1Y': timedelta(days=365), '5Y': timedelta(days=1825),
        }
        delta = period_map.get(period, timedelta(days=7))
        cutoff = timezone.now() - delta
        first_candle = self.candles.filter(timestamp__gte=cutoff).order_by('timestamp').first()
        if first_candle:
            return float(first_candle.open)
        multipliers = {'1D': 0.98, '1W': 0.95, '1M': 0.9, '3M': 0.85, '1Y': 0.7, '5Y': 0.4}
        return float(self.current_price) * multipliers.get(period, 0.95)
    
    def period_return(self, period='1W'):
        start_price = self.get_price_for_period(period)
        current = float(self.current_price)
        if start_price > 0:
            return ((current - start_price) / start_price) * 100
        return 0


class PriceCandle(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='candles')
    open = models.DecimalField(max_digits=12, decimal_places=2)
    high = models.DecimalField(max_digits=12, decimal_places=2)
    low = models.DecimalField(max_digits=12, decimal_places=2)
    close = models.DecimalField(max_digits=12, decimal_places=2)
    volume = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    timestamp = models.DateTimeField()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['asset', 'timestamp']), models.Index(fields=['timestamp'])]
        unique_together = ['asset', 'timestamp']
    
    def __str__(self):
        return f"{self.asset.symbol} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def add_price_point(cls, asset, price, volume=0):
        now = timezone.now()
        candle_minute = (now.minute // 15) * 15
        candle_time = now.replace(minute=candle_minute, second=0, microsecond=0)
        candle, created = cls.objects.get_or_create(asset=asset, timestamp=candle_time,
            defaults={'open': price, 'high': price, 'low': price, 'close': price, 'volume': volume})
        if not created:
            candle.high = max(candle.high, price)
            candle.low = min(candle.low, price)
            candle.close = price
            candle.volume += volume
            candle.save()
        return candle
    
    @classmethod
    def cleanup_old_candles(cls):
        cutoff = timezone.now() - timezone.timedelta(days=90)
        deleted = cls.objects.filter(timestamp__lt=cutoff).delete()
        print(f"Deleted {deleted[0]} old candles")


class MarketNews(models.Model):
    CATEGORY_CHOICES = [
        ('stock', 'Stock'), ('mineral', 'Mineral'), ('crypto', 'Cryptocurrency'),
        ('economy', 'Economy'), ('company', 'Company'),
    ]
    
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField(blank=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name='news')
    image = models.ImageField(upload_to='news/', blank=True, null=True)
    source = models.CharField(max_length=100, default='Qubix News')
    url = models.URLField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-published_at']
        verbose_name_plural = "Market News"
    
    def __str__(self):
        return self.title


class Portfolio(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='portfolio')
    cash_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deposits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawals = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_dividends = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ytd_performance = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email}'s Portfolio"
    
    def total_value(self):
        holdings_total = sum(float(h.current_value()) for h in self.holdings.all())
        real_estate_total = 0
        try:
            real_estate_total = sum(float(inv.amount_invested) for inv in self.user.real_estate_investments.all())
        except AttributeError:
            pass
        return float(self.cash_balance) + holdings_total + real_estate_total
    
    def unrealized_pl(self):
        holdings = self.holdings.all()
        total_pl = 0
        for holding in holdings:
            total_pl += float(holding.unrealized_pl())
        return total_pl
    
    def get_asset_allocation(self):
        total = self.total_value()
        if total == 0:
            return {}
        stocks_value = sum(float(h.current_value()) for h in self.holdings.filter(asset__category='stock'))
        minerals_value = sum(float(h.current_value()) for h in self.holdings.filter(asset__category='mineral'))
        real_estate_value = 0
        try:
            real_estate_value = sum(float(inv.amount_invested) for inv in self.user.real_estate_investments.all())
        except AttributeError:
            pass
        other_value = sum(float(h.current_value()) for h in self.holdings.exclude(asset__category__in=['stock', 'mineral']))
        allocation = {}
        if stocks_value > 0:
            allocation['Stocks'] = (stocks_value / total) * 100
        if minerals_value > 0:
            allocation['Minerals'] = (minerals_value / total) * 100
        if real_estate_value > 0:
            allocation['Real Estate'] = (real_estate_value / total) * 100
        if other_value > 0:
            allocation['Other'] = (other_value / total) * 100
        if float(self.cash_balance) > 0:
            allocation['Cash'] = (float(self.cash_balance) / total) * 100
        return allocation


class Holding(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    average_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    override_purchase_date = models.DateTimeField(null=True, blank=True, help_text="Admin can override purchase date")
    override_average_price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, help_text="Admin can override average price")
    override_quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, help_text="Admin can override quantity")
    
    class Meta:
        unique_together = ['portfolio', 'asset']
    
    def __str__(self):
        return f"{self.portfolio.user.email} - {self.asset.symbol}"
    
    def get_effective_quantity(self):
        return self.override_quantity or self.quantity
    
    def get_effective_average_price(self):
        return self.override_average_price or self.average_price
    
    def get_effective_purchase_date(self):
        return self.override_purchase_date or self.created_at
    
    def current_value(self):
        return self.get_effective_quantity() * self.asset.current_price
    
    def unrealized_pl(self):
        return self.current_value() - (self.get_effective_quantity() * self.get_effective_average_price())
    
    def profit_percent(self):
        avg_price = self.get_effective_average_price()
        if avg_price > 0:
            return ((self.asset.current_price - avg_price) / avg_price) * 100
        return 0


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('buy', 'Buy'), ('sell', 'Sell'), ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'), ('dividend', 'Dividend'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'),
        ('completed', 'Completed'), ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='transactions')
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    price_at_time = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    auto_approve_at = models.DateTimeField(null=True, blank=True)
    is_auto_approve = models.BooleanField(default=False)
    
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transactions')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override transaction date")
    override_total_amount = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, help_text="Admin can override transaction amount")
    
    def __str__(self):
        return f"{self.user.email} - {self.transaction_type} - ${self.total_amount}"
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def get_effective_total_amount(self):
        return self.override_total_amount or self.total_amount
    
    def approve(self, admin_user=None):
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            self.status = 'approved'
            if admin_user:
                self.approved_by = admin_user
            self.approved_at = timezone.now()
            self.save()
            if self.transaction_type == 'buy':
                portfolio = self.user.portfolio
                holding, created = Holding.objects.get_or_create(portfolio=portfolio, asset=self.asset,
                    defaults={'average_price': self.price_at_time})
                if not created:
                    total_quantity = holding.quantity + self.quantity
                    total_cost = (holding.quantity * holding.average_price) + (self.quantity * self.price_at_time)
                    holding.average_price = total_cost / total_quantity
                    holding.quantity = total_quantity
                else:
                    holding.quantity = self.quantity
                    holding.average_price = self.price_at_time
                holding.save()
                portfolio.cash_balance -= self.total_amount
                portfolio.save()
            elif self.transaction_type == 'sell':
                portfolio = self.user.portfolio
                holding = Holding.objects.get(portfolio=portfolio, asset=self.asset)
                holding.quantity -= self.quantity
                if holding.quantity <= 0:
                    holding.delete()
                else:
                    holding.save()
                portfolio.cash_balance += self.total_amount
                portfolio.save()
            elif self.transaction_type == 'deposit':
                portfolio = self.user.portfolio
                portfolio.cash_balance += self.total_amount
                portfolio.total_deposits += self.total_amount
                portfolio.save()
            elif self.transaction_type == 'withdraw':
                portfolio = self.user.portfolio
                portfolio.cash_balance -= self.total_amount
                portfolio.total_withdrawals += self.total_amount
                portfolio.save()
            elif self.transaction_type == 'dividend':
                portfolio = self.user.portfolio
                portfolio.cash_balance += self.total_amount
                portfolio.total_dividends += self.total_amount
                portfolio.save()
    
    def reject(self, admin_user, reason=''):
        self.status = 'rejected'
        self.notes = reason
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.save()
    
    def schedule_auto_approve(self, minutes=30):
        from datetime import timedelta
        self.auto_approve_at = timezone.now() + timedelta(minutes=minutes)
        self.is_auto_approve = True
        self.save()


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'),
        ('processing', 'Processing'), ('completed', 'Completed'),
    ]
    
    PAYMENT_METHODS = [('crypto', 'Cryptocurrency')]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    crypto_currency = models.ForeignKey('CryptoCurrency', on_delete=models.SET_NULL, null=True, blank=True)
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    rate_used = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    wallet_address = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='crypto')
    
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fee_crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    fee_paid = models.BooleanField(default=False)
    fee_paid_at = models.DateTimeField(null=True, blank=True)
    fee_transaction_hash = models.CharField(max_length=255, blank=True, null=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_withdrawals')
    approved_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override request date")
    override_approved_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override approval date")
    
    def __str__(self):
        return f"{self.user.email} - ${self.amount} - {self.status}"
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def get_effective_approved_at(self):
        return self.override_approved_at or self.approved_at
    
    def get_fee_amount(self):
        return self.amount * (self.fee_percentage / 100)
    
    def get_net_amount(self):
        return self.amount - self.get_fee_amount()
    
    def approve(self, admin_user):
        from django.db import transaction as db_transaction
        from decimal import Decimal
        with db_transaction.atomic():
            self.status = 'approved'
            self.approved_by = admin_user
            self.approved_at = timezone.now()
            self.save()
            transaction = Transaction.objects.filter(user=self.user, transaction_type='withdraw',
                total_amount=self.amount, status='pending').first()
            if transaction:
                transaction.status = 'approved'
                transaction.approved_by = admin_user
                transaction.approved_at = timezone.now()
                transaction.notes = f"Withdrawal approved - Fee: ${self.fee_amount:,.2f} paid | Net: ${self.get_net_amount():,.2f}"
                transaction.save()
    
    def reject(self, admin_user, reason=''):
        from decimal import Decimal
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            self.status = 'rejected'
            self.notes = reason
            self.approved_by = admin_user
            self.approved_at = timezone.now()
            self.save()
            portfolio = self.user.portfolio
            portfolio.cash_balance += Decimal(str(self.amount))
            portfolio.save()
            transaction = Transaction.objects.filter(user=self.user, transaction_type='withdraw',
                total_amount=self.amount, status='pending').first()
            if transaction:
                transaction.status = 'rejected'
                transaction.notes = f"Withdrawal rejected: {reason}"
                transaction.save()
            Notification.objects.create(user=self.user, title="Withdrawal Rejected",
                message=f"Your withdrawal request for ${self.amount:,.2f} was rejected. Reason: {reason}",
                notification_type='withdrawal')


class PriceAlert(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='price_alerts')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='alerts')
    target_price = models.DecimalField(max_digits=12, decimal_places=2)
    alert_type = models.CharField(max_length=10, choices=[('above', 'Above'), ('below', 'Below')])
    is_triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override creation date")
    override_triggered_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override triggered date")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.asset.symbol} {self.alert_type} ${self.target_price}"
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def get_effective_triggered_at(self):
        return self.override_triggered_at or self.triggered_at
    
    def check_alert(self):
        if not self.is_triggered:
            if self.alert_type == 'above' and self.asset.current_price >= self.target_price:
                self.trigger()
                return True
            elif self.alert_type == 'below' and self.asset.current_price <= self.target_price:
                self.trigger()
                return True
        return False
    
    def trigger(self):
        self.is_triggered = True
        self.triggered_at = timezone.now()
        self.save()
        Notification.objects.create(user=self.user, title=f"Price Alert: {self.asset.symbol}",
            message=f"{self.asset.symbol} has reached ${self.asset.current_price}",
            notification_type='price_alert', related_object_id=self.id)


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('price_alert', 'Price Alert'), ('transaction', 'Transaction'), ('withdrawal', 'Withdrawal'),
        ('deposit', 'Deposit'), ('dividend', 'Dividend'), ('system', 'System'), ('admin_alert', 'Admin Alert'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=100)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    related_object_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override notification date")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email if self.user else 'System'} - {self.title}"
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def mark_as_read(self):
        self.is_read = True
        self.save()


# ============= REAL ESTATE MODELS =============

class RealEstateProperty(models.Model):
    PROPERTY_STATUS = [
        ('funding', 'Funding'), ('funded', 'Fully Funded'),
        ('leased', 'Leased'), ('rented', 'Rented'),
    ]
    
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    address = models.TextField()
    beds = models.IntegerField()
    baths = models.DecimalField(max_digits=3, decimal_places=1)
    sqft = models.IntegerField()
    year_built = models.IntegerField()
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_available = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    annual_cash_flow = models.DecimalField(max_digits=12, decimal_places=2)
    appreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=4.5)
    funded_percent = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    investor_count = models.IntegerField(default=0)
    total_shares = models.IntegerField()
    price_per_share = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    status = models.CharField(max_length=10, choices=PROPERTY_STATUS, default='funding')
    badge = models.CharField(max_length=50, blank=True)
    main_image = models.ImageField(upload_to='realestate/', blank=True, null=True)
    gallery_images = models.JSONField(default=list)
    market_description = models.TextField()
    property_description = models.TextField()
    series_overview = models.FileField(upload_to='documents/', blank=True)
    use_of_proceeds = models.FileField(upload_to='documents/', blank=True)
    risk_factors = models.FileField(upload_to='documents/', blank=True)
    offering_circular = models.FileField(upload_to='documents/', blank=True)
    timeline_updates = models.JSONField(default=list)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ========== ADD OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override creation date")
    override_purchase_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Admin can override purchase price")
    override_annual_cash_flow = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Admin can override annual cash flow")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Real Estate Property"
        verbose_name_plural = "Real Estate Properties"
    
    def __str__(self):
        return self.name
    
    # ========== EFFECTIVE METHODS ==========
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def get_effective_purchase_price(self):
        return self.override_purchase_price or self.purchase_price
    
    def get_effective_annual_cash_flow(self):
        return self.override_annual_cash_flow or self.annual_cash_flow

class RealEstateInvestment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='real_estate_investments')
    property = models.ForeignKey(RealEstateProperty, on_delete=models.CASCADE, related_name='investments')
    shares = models.IntegerField()
    amount_invested = models.DecimalField(max_digits=12, decimal_places=2)
    personal_remaining = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    personal_funded_percent = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    personal_investor_count = models.IntegerField(default=1)
    investment_period_months = models.IntegerField(default=12)
    maturity_date = models.DateTimeField(null=True, blank=True)
    expected_annual_return = models.DecimalField(max_digits=5, decimal_places=2, default=8.50)
    expected_value_at_maturity = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # ========== EXISTING OVERRIDE FIELDS ==========
    override_invested_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override investment date")
    override_amount_invested = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Admin can override amount")
    
    # ========== ADD THESE MISSING OVERRIDE FIELDS ==========
    override_shares = models.IntegerField(null=True, blank=True, help_text="Admin can override number of shares")
    override_maturity_date = models.DateTimeField(null=True, blank=True, help_text="Admin can override maturity date")
    override_expected_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Admin can override expected value at maturity")
    
    invested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.property.name} - {self.shares} shares"
    
    # ========== EFFECTIVE METHODS ==========
    def get_effective_invested_at(self):
        """Return admin-overridden invested_at if exists, otherwise original"""
        return self.override_invested_at or self.invested_at
    
    def get_effective_amount_invested(self):
        """Return admin-overridden amount_invested if exists, otherwise original"""
        return self.override_amount_invested or self.amount_invested
    
    def get_effective_shares(self):
        """Return admin-overridden shares if exists, otherwise original"""
        return self.override_shares or self.shares
    
    def get_effective_maturity_date(self):
        """Return admin-overridden maturity_date if exists, otherwise original"""
        return self.override_maturity_date or self.maturity_date
    
    def get_effective_expected_value(self):
        """Return admin-overridden expected_value_at_maturity if exists, otherwise original"""
        return self.override_expected_value or self.expected_value_at_maturity
    
    def calculate_personal_metrics(self):
        if self.personal_remaining is None:
            self.personal_remaining = self.property.total_available - self.amount_invested
        else:
            self.personal_remaining -= self.amount_invested
        if self.property.total_available > 0:
            invested_amount = self.property.total_available - self.personal_remaining
            self.personal_funded_percent = (invested_amount / self.property.total_available) * 100
        self.personal_investor_count = 1
        self.save()
        return True
    
    def add_investment(self, additional_amount):
        self.amount_invested += additional_amount
        shares_to_add = int(additional_amount / self.property.price_per_share)
        self.shares += shares_to_add
        self.personal_remaining -= additional_amount
        self.calculate_personal_metrics()
        self.save()
        return True
    
    class Meta:
        ordering = ['-invested_at']
        unique_together = ['user', 'property']


class RealEstateDividend(models.Model):
    investment = models.ForeignKey(RealEstateInvestment, on_delete=models.CASCADE, related_name='dividends')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.DateField()
    paid_at = models.DateTimeField(auto_now_add=True)
    
    # ========== ADD OVERRIDE FIELDS ==========
    override_paid_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override payment date")
    override_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Admin can override dividend amount")
    override_month = models.DateField(null=True, blank=True, help_text="Admin can override month")
    
    class Meta:
        ordering = ['-month']
    
    def __str__(self):
        return f"{self.investment.property.name} - {self.month} - ${self.amount}"
    
    # ========== EFFECTIVE METHODS ==========
    def get_effective_paid_at(self):
        """Return admin-overridden paid_at if exists, otherwise original"""
        return self.override_paid_at or self.paid_at
    
    def get_effective_amount(self):
        """Return admin-overridden amount if exists, otherwise original"""
        return self.override_amount or self.amount
    
    def get_effective_month(self):
        """Return admin-overridden month if exists, otherwise original"""
        return self.override_month or self.month


# ============= CRYPTO DEPOSIT MODELS =============

class CryptoCurrency(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)
    rate_usd = models.DecimalField(max_digits=20, decimal_places=8)
    wallet_address = models.CharField(max_length=255)
    network = models.CharField(max_length=50, blank=True)
    min_deposit_usd = models.DecimalField(max_digits=12, decimal_places=2, default=10)
    max_deposit_usd = models.DecimalField(max_digits=12, decimal_places=2, default=10000)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=10, default="💰")
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'symbol']
        verbose_name_plural = "Cryptocurrencies"
    
    def __str__(self):
        return f"{self.symbol} - 1 = ${self.rate_usd}"
    
    def get_icon(self):
        icons = {'BTC': '₿', 'ETH': 'Ξ', 'USDT': '₮', 'USDC': '💵', 'BNB': '🟡',
                 'SOL': '◎', 'XRP': '✕', 'DOGE': '🐕', 'ADA': '⬜', 'TRX': '🔴'}
        return icons.get(self.symbol, self.icon)


class CryptoDeposit(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'), ('paid', 'Payment Confirmed - Pending Admin'),
        ('completed', 'Completed'), ('expired', 'Expired'), ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='crypto_deposits')
    crypto = models.ForeignKey(CryptoCurrency, on_delete=models.SET_NULL, null=True)
    usd_amount = models.DecimalField(max_digits=12, decimal_places=2)
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8)
    rate_used = models.DecimalField(max_digits=20, decimal_places=8)
    wallet_address = models.CharField(max_length=255)
    transaction_hash = models.CharField(max_length=255, blank=True, null=True)
    qr_code = models.ImageField(upload_to='deposit_qrcodes/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override creation date")
    override_confirmed_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override confirmation date")
    
    def __str__(self):
        return f"{self.user.email} - {self.crypto_amount} {self.crypto.symbol} (${self.usd_amount})"
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def get_effective_confirmed_at(self):
        return self.override_confirmed_at or self.confirmed_at
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(minutes=20)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def get_time_remaining(self):
        remaining = self.expires_at - timezone.now()
        if remaining.total_seconds() <= 0:
            return "Expired"
        minutes = int(remaining.total_seconds() // 60)
        seconds = int(remaining.total_seconds() % 60)
        return f"{minutes}:{seconds:02d}"
    
    def generate_qr_code(self):
        try:
            import qrcode
            from io import BytesIO
            from django.core.files.base import ContentFile
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(self.wallet_address)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            filename = f"deposit_{self.id}_{self.crypto.symbol}.png"
            self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)
            buffer.close()
        except Exception as e:
            print(f"QR generation error: {e}")


# ============= PHYSICAL PRODUCTS MODELS =============

class PhysicalProduct(models.Model):
    CATEGORY_CHOICES = [
        ('gold', 'Gold'), ('silver', 'Silver'), ('platinum', 'Platinum'),
        ('copper', 'Copper'), ('accessories', 'Accessories'),
    ]
    
    name = models.CharField(max_length=200)
    year = models.CharField(max_length=4, blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='gold')
    main_image = models.ImageField(upload_to='physical_products/main/', blank=True, null=True)
    gallery_images = models.JSONField(default=list, blank=True)
    specification = models.CharField(max_length=200)
    purity = models.CharField(max_length=50)
    weight = models.CharField(max_length=100)
    mint = models.CharField(max_length=100)
    dimensions = models.CharField(max_length=100, blank=True, null=True)
    current_price = models.DecimalField(max_digits=20, decimal_places=2)
    spot_price = models.DecimalField(max_digits=20, decimal_places=2)
    price_change_24h = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    stock_quantity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    three_d_model = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.category})"
    
    def get_premium_percent(self):
        return ((self.current_price / self.spot_price) - 1) * 100


class PhysicalHolding(models.Model):
    SERVICE_CHOICES = [('vault', 'Qubix Vault'), ('shipped', 'Shipped to Address')]
    DELIVERY_STATUS_CHOICES = [
        ('processing', 'Processing'), ('confirmed', 'Confirmed'), ('packaged', 'Packaged'),
        ('transit', 'In Transit'), ('out_for_delivery', 'Out for Delivery'), ('delivered', 'Delivered'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='physical_holdings')
    transaction = models.ForeignKey('PhysicalTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='holdings')
    product = models.ForeignKey(PhysicalProduct, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    average_price = models.DecimalField(max_digits=20, decimal_places=2)
    service_type = models.CharField(max_length=10, choices=SERVICE_CHOICES, default='vault')
    vault_location = models.CharField(max_length=100, default='Zurich, Switzerland')
    is_insured = models.BooleanField(default=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    shipping_address = models.JSONField(default=dict, blank=True)
    delivery_status = models.CharField(max_length=50, default='processing', choices=DELIVERY_STATUS_CHOICES)
    estimated_delivery = models.DateField(blank=True, null=True)
    verification_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    
    override_purchase_date = models.DateTimeField(null=True, blank=True, help_text="Admin can override purchase date")
    override_quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, help_text="Admin can override quantity")
    override_current_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Admin can override current value")
    
    purchased_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-purchased_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name} x{self.quantity}"
    
    def get_effective_purchase_date(self):
        return self.override_purchase_date or self.purchased_at
    
    def get_effective_quantity(self):
        return self.override_quantity or self.quantity
    
    def get_effective_current_value(self):
        if self.override_current_value:
            return self.override_current_value
        return self.quantity * self.product.current_price
    
    def save(self, *args, **kwargs):
        if not self.verification_code:
            import uuid
            self.verification_code = f"QUBIX-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
    
    def get_verification_url(self):
        return f"http://127.0.0.1:8000/verify/{self.verification_code}/"
    
    def current_value(self):
        return self.get_effective_current_value()
    
    def profit_loss(self):
        return (self.product.current_price - self.average_price) * self.get_effective_quantity()
    
    def profit_percent(self):
        if self.average_price > 0:
            return ((self.product.current_price / self.average_price) - 1) * 100
        return 0


class PhysicalTransaction(models.Model):
    PAYMENT_METHODS = [
        ('BTC', 'Bitcoin'), ('ETH', 'Ethereum'), ('USDT', 'USDT'),
        ('LTC', 'Litecoin'), ('delivery_fee', 'Delivery Fee'), ('sell_fee', 'Sell Fee'),
    ]
    
    STATUS_CHOICES = [
        ('under_review', 'Payment Under Review'), ('confirmed_processing', 'Confirmed - Processing'),
        ('confirmed_vault', 'Confirmed - In Vault'), ('shipped', 'Shipped'),
        ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('completed', 'Completed'),
    ]
    
    DELIVERY_CHOICES = [('vault', 'Qubix Vault Storage'), ('shipping', 'Ship to Address'), ('sell', 'Sell Order')]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='physical_transactions')
    product = models.ForeignKey(PhysicalProduct, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    total_amount = models.DecimalField(max_digits=20, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    crypto_currency_used = models.CharField(max_length=10, blank=True, null=True)
    transaction_hash = models.CharField(max_length=200, blank=True, null=True)
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, blank=True, null=True)
    shipping_address = models.JSONField(default=dict, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    estimated_delivery = models.DateField(blank=True, null=True)
    vault_location = models.CharField(max_length=100, default='Zurich, Switzerland', blank=True)
    vault_slot = models.CharField(max_length=50, blank=True, null=True)
    certificate_number = models.CharField(max_length=100, blank=True, null=True)
    certificate_pdf = models.FileField(upload_to='certificates/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='under_review')
    payment_confirmed_at = models.DateTimeField(blank=True, null=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    documents_sent_to = models.EmailField(blank=True, null=True)
    documents_sent_at = models.DateTimeField(blank=True, null=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override transaction date")
    override_total_amount = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, help_text="Admin can override total amount")
    override_shipped_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override shipped date")
    override_delivered_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override delivered date")
    override_quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, help_text="Admin can override quantity")
    override_shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Admin can override shipping fee")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name} x{self.quantity}"
    
    # ========== EFFECTIVE DATE METHODS ==========
    def get_effective_created_at(self):
        """Return admin-overridden created_at if exists, otherwise original"""
        return self.override_created_at or self.created_at
    
    def get_effective_total_amount(self):
        """Return admin-overridden total_amount if exists, otherwise original"""
        return self.override_total_amount or self.total_amount
    
    def get_effective_shipped_at(self):
        """Return admin-overridden shipped_at if exists, otherwise original"""
        return self.override_shipped_at or self.shipped_at
    
    def get_effective_delivered_at(self):
        """Return admin-overridden delivered_at if exists, otherwise original"""
        return self.override_delivered_at or self.delivered_at
    
    def get_effective_quantity(self):
        """Return admin-overridden quantity if exists, otherwise original"""
        return self.override_quantity or self.quantity
    
    def get_effective_shipping_fee(self):
        """Return admin-overridden shipping_fee if exists, otherwise original"""
        return self.override_shipping_fee or self.shipping_fee
    
    # ========== HELPER METHODS ==========
    def get_status_display_html(self):
        status_info = {
            'under_review': {'color': '#f0b90b', 'icon': '⏳', 'text': 'Payment Under Review'},
            'confirmed_processing': {'color': '#3d7eff', 'icon': '🔄', 'text': 'Confirmed - Processing'},
            'confirmed_vault': {'color': '#0ecb81', 'icon': '🔒', 'text': 'In Vault'},
            'shipped': {'color': '#0ecb81', 'icon': '📦', 'text': 'Shipped'},
            'delivered': {'color': '#0ecb81', 'icon': '✅', 'text': 'Delivered'},
            'cancelled': {'color': '#f6465d', 'icon': '❌', 'text': 'Cancelled'},
            'completed': {'color': '#0ecb81', 'icon': '✅', 'text': 'Completed'},
        }
        info = status_info.get(self.status, {'color': '#6b7280', 'icon': '📋', 'text': self.get_status_display()})
        return f'<span style="background:{info["color"]}20; color:{info["color"]}; padding:4px 8px; border-radius:6px;">{info["icon"]} {info["text"]}</span>'
    
    def get_delivery_timeline(self):
        """Calculate delivery timeline based on effective dates"""
        from datetime import timedelta
        
        order_date = self.get_effective_created_at()
        shipped_date = self.get_effective_shipped_at()
        delivered_date = self.get_effective_delivered_at()
        
        timeline = {
            'order_date': order_date,
            'shipped_date': shipped_date,
            'delivered_date': delivered_date,
        }
        
        if shipped_date:
            timeline['days_to_ship'] = (shipped_date - order_date).days
        else:
            timeline['days_to_ship'] = None
            
        if delivered_date and shipped_date:
            timeline['days_in_transit'] = (delivered_date - shipped_date).days
        else:
            timeline['days_in_transit'] = None
            
        if delivered_date:
            timeline['total_days'] = (delivered_date - order_date).days
        else:
            timeline['total_days'] = None
            
        return timeline

class PhysicalCart(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='physical_cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Cart for {self.user.email}"
    
    def get_total(self):
        return sum(item.get_subtotal() for item in self.items.all())
    
    def get_item_count(self):
        return sum(item.quantity for item in self.items.all())


class PhysicalCartItem(models.Model):
    cart = models.ForeignKey(PhysicalCart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(PhysicalProduct, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
    
    def get_subtotal(self):
        return self.quantity * self.product.current_price


class ShippingTracking(models.Model):
    STATUS_CHOICES = [
        ('order_confirmed', 'Order Confirmed'), ('processing', 'Processing'), ('packaged', 'Packaged'),
        ('transit', 'In Transit'), ('out_for_delivery', 'Out for Delivery'), ('delivered', 'Delivered'),
    ]
    
    transaction = models.ForeignKey(PhysicalTransaction, on_delete=models.CASCADE, related_name='tracking_updates')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    location = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.transaction.id} - {self.status} at {self.timestamp}"


# ============= CUSTOMER SUPPORT MODELS =============

class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved'), ('closed', 'Closed'),
    ]
    
    TYPE_CHOICES = [
        ('general', 'General Inquiry'), ('investment', 'Investment Advice'), ('portfolio', 'Portfolio Review'),
        ('technical', 'Technical Support'), ('withdrawal', 'Withdrawal Help'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='support_tickets')
    title = models.CharField(max_length=200)
    ticket_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override ticket creation date")
    override_updated_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override last update date")
    
    def __str__(self):
        return f"Ticket #{self.id} - {self.user.email}"
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def get_effective_updated_at(self):
        return self.override_updated_at or self.updated_at


class SupportMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    message = models.TextField()
    is_user = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override message timestamp")
    
    class Meta:
        ordering = ['created_at']
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at


class ScheduledCall(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('confirmed', 'Confirmed'), ('completed', 'Completed'), ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='scheduled_calls')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    scheduled_date = models.DateField()
    scheduled_time = models.CharField(max_length=10)
    call_type = models.CharField(max_length=20, choices=SupportTicket.TYPE_CHOICES, default='general')
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ========== ADMIN OVERRIDE FIELDS ==========
    override_created_at = models.DateTimeField(null=True, blank=True, help_text="Admin can override call request date")
    override_scheduled_date = models.DateField(null=True, blank=True, help_text="Admin can override scheduled date")
    override_scheduled_time = models.CharField(max_length=10, null=True, blank=True, help_text="Admin can override scheduled time")
    
    def __str__(self):
        return f"Call with {self.user.email} on {self.scheduled_date} at {self.scheduled_time}"
    
    def get_effective_created_at(self):
        return self.override_created_at or self.created_at
    
    def get_effective_scheduled_date(self):
        return self.override_scheduled_date or self.scheduled_date
    
    def get_effective_scheduled_time(self):
        return self.override_scheduled_time or self.scheduled_time