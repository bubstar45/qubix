from django.core.management.base import BaseCommand
from decimal import Decimal
from core.models import Asset

class Command(BaseCommand):
    help = 'Populate database with 50 stocks and 20 minerals'

    def safe_decimal(self, value):
        """Safely convert a value to Decimal"""
        if value is None:
            return None
        try:
            # Remove any commas or other non-numeric characters except decimal point
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '').replace('B', '').replace('T', '')
            return Decimal(str(value))
        except:
            return Decimal('0')

    def handle(self, *args, **options):
        self.stdout.write("Starting asset population...")
        
        # ============= TOP 50 STOCKS =============
        stocks = [
            # Tech Stocks
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'category': 'stock', 'current_price': 175.50, 'price_min': 165, 'price_max': 185, 'volatility': 0.8, 'market_cap': '3.41T', 'volume_24h': 52400000, 'dividend_yield': 0.52, 'pe_ratio': 32.5},
            {'symbol': 'MSFT', 'name': 'Microsoft Corp.', 'category': 'stock', 'current_price': 420.50, 'price_min': 400, 'price_max': 440, 'volatility': 0.7, 'market_cap': '3.12T', 'volume_24h': 22100000, 'dividend_yield': 0.74, 'pe_ratio': 35.0},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'category': 'stock', 'current_price': 140.25, 'price_min': 135, 'price_max': 150, 'volatility': 0.9, 'market_cap': '1.78T', 'volume_24h': 18200000, 'dividend_yield': 0, 'pe_ratio': 24.5},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'category': 'stock', 'current_price': 178.75, 'price_min': 165, 'price_max': 190, 'volatility': 1.1, 'market_cap': '1.85T', 'volume_24h': 32100000, 'dividend_yield': 0, 'pe_ratio': 45.2},
            {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'category': 'stock', 'current_price': 485.50, 'price_min': 450, 'price_max': 520, 'volatility': 1.3, 'market_cap': '1.23T', 'volume_24h': 15800000, 'dividend_yield': 0, 'pe_ratio': 28.0},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'category': 'stock', 'current_price': 248.50, 'price_min': 220, 'price_max': 280, 'volatility': 2.0, 'market_cap': '792B', 'volume_24h': 88500000, 'dividend_yield': 0, 'pe_ratio': 58.0},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corp.', 'category': 'stock', 'current_price': 895.60, 'price_min': 800, 'price_max': 950, 'volatility': 1.5, 'market_cap': '2.21T', 'volume_24h': 35200000, 'dividend_yield': 0.03, 'pe_ratio': 72.0},
            {'symbol': 'NKE', 'name': 'Nike Inc.', 'category': 'stock', 'current_price': 98.50, 'price_min': 90, 'price_max': 110, 'volatility': 0.9, 'market_cap': '150B', 'volume_24h': 8200000, 'dividend_yield': 1.42, 'pe_ratio': 26.0},
            {'symbol': 'KO', 'name': 'Coca-Cola Co.', 'category': 'stock', 'current_price': 60.88, 'price_min': 58, 'price_max': 64, 'volatility': 0.5, 'market_cap': '263B', 'volume_24h': 12500000, 'dividend_yield': 3.05, 'pe_ratio': 24.0},
            {'symbol': 'MCD', 'name': 'McDonald\'s Corp.', 'category': 'stock', 'current_price': 298.10, 'price_min': 280, 'price_max': 310, 'volatility': 0.6, 'market_cap': '215B', 'volume_24h': 3200000, 'dividend_yield': 2.32, 'pe_ratio': 24.5},
            {'symbol': 'SBUX', 'name': 'Starbucks Corp.', 'category': 'stock', 'current_price': 92.15, 'price_min': 85, 'price_max': 98, 'volatility': 0.8, 'market_cap': '105B', 'volume_24h': 6800000, 'dividend_yield': 2.45, 'pe_ratio': 23.0},
            {'symbol': 'JPM', 'name': 'JPMorgan Chase', 'category': 'stock', 'current_price': 198.62, 'price_min': 185, 'price_max': 210, 'volatility': 0.8, 'market_cap': '572B', 'volume_24h': 9100000, 'dividend_yield': 2.45, 'pe_ratio': 11.5},
            {'symbol': 'BAC', 'name': 'Bank of America', 'category': 'stock', 'current_price': 37.25, 'price_min': 35, 'price_max': 42, 'volatility': 0.9, 'market_cap': '295B', 'volume_24h': 38200000, 'dividend_yield': 2.85, 'pe_ratio': 10.0},
            {'symbol': 'V', 'name': 'Visa Inc.', 'category': 'stock', 'current_price': 278.45, 'price_min': 265, 'price_max': 290, 'volatility': 0.7, 'market_cap': '566B', 'volume_24h': 5200000, 'dividend_yield': 0.75, 'pe_ratio': 30.5},
            {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'category': 'stock', 'current_price': 158.30, 'price_min': 150, 'price_max': 165, 'volatility': 0.6, 'market_cap': '381B', 'volume_24h': 5800000, 'dividend_yield': 3.15, 'pe_ratio': 24.0},
            {'symbol': 'PFE', 'name': 'Pfizer Inc.', 'category': 'stock', 'current_price': 27.85, 'price_min': 26, 'price_max': 32, 'volatility': 0.8, 'market_cap': '158B', 'volume_24h': 32100000, 'dividend_yield': 5.85, 'pe_ratio': 15.0},
            {'symbol': 'XOM', 'name': 'Exxon Mobil', 'category': 'stock', 'current_price': 115.30, 'price_min': 105, 'price_max': 125, 'volatility': 1.0, 'market_cap': '462B', 'volume_24h': 14200000, 'dividend_yield': 3.45, 'pe_ratio': 12.0},
            {'symbol': 'CVX', 'name': 'Chevron Corp.', 'category': 'stock', 'current_price': 158.90, 'price_min': 145, 'price_max': 170, 'volatility': 0.9, 'market_cap': '298B', 'volume_24h': 6500000, 'dividend_yield': 4.05, 'pe_ratio': 11.5},
            {'symbol': 'BA', 'name': 'Boeing Co.', 'category': 'stock', 'current_price': 184.25, 'price_min': 170, 'price_max': 210, 'volatility': 1.4, 'market_cap': '113B', 'volume_24h': 7800000, 'dividend_yield': 0, 'pe_ratio': 0},
            {'symbol': 'CAT', 'name': 'Caterpillar Inc.', 'category': 'stock', 'current_price': 335.50, 'price_min': 310, 'price_max': 360, 'volatility': 0.9, 'market_cap': '168B', 'volume_24h': 2800000, 'dividend_yield': 1.55, 'pe_ratio': 16.0},
            {'symbol': 'VZ', 'name': 'Verizon Comm.', 'category': 'stock', 'current_price': 41.25, 'price_min': 38, 'price_max': 45, 'volatility': 0.7, 'market_cap': '173B', 'volume_24h': 18500000, 'dividend_yield': 6.55, 'pe_ratio': 8.5},
            {'symbol': 'T', 'name': 'AT&T Inc.', 'category': 'stock', 'current_price': 17.85, 'price_min': 16, 'price_max': 20, 'volatility': 0.8, 'market_cap': '128B', 'volume_24h': 32200000, 'dividend_yield': 6.85, 'pe_ratio': 9.0},
            {'symbol': 'ADBE', 'name': 'Adobe Inc.', 'category': 'stock', 'current_price': 485.20, 'price_min': 450, 'price_max': 520, 'volatility': 1.1, 'market_cap': '219B', 'volume_24h': 2500000, 'dividend_yield': 0, 'pe_ratio': 48.0},
            {'symbol': 'CRM', 'name': 'Salesforce Inc.', 'category': 'stock', 'current_price': 285.60, 'price_min': 265, 'price_max': 310, 'volatility': 1.0, 'market_cap': '277B', 'volume_24h': 4800000, 'dividend_yield': 0, 'pe_ratio': 65.0},
            {'symbol': 'ORCL', 'name': 'Oracle Corp.', 'category': 'stock', 'current_price': 125.80, 'price_min': 115, 'price_max': 135, 'volatility': 0.8, 'market_cap': '346B', 'volume_24h': 6200000, 'dividend_yield': 1.25, 'pe_ratio': 28.0},
            {'symbol': 'IBM', 'name': 'IBM Corp.', 'category': 'stock', 'current_price': 188.25, 'price_min': 175, 'price_max': 200, 'volatility': 0.8, 'market_cap': '172B', 'volume_24h': 3500000, 'dividend_yield': 3.65, 'pe_ratio': 22.0},
            {'symbol': 'INTC', 'name': 'Intel Corp.', 'category': 'stock', 'current_price': 42.50, 'price_min': 38, 'price_max': 48, 'volatility': 1.2, 'market_cap': '179B', 'volume_24h': 28500000, 'dividend_yield': 1.45, 'pe_ratio': 28.0},
            {'symbol': 'AMD', 'name': 'AMD Inc.', 'category': 'stock', 'current_price': 165.30, 'price_min': 150, 'price_max': 185, 'volatility': 1.5, 'market_cap': '267B', 'volume_24h': 42200000, 'dividend_yield': 0, 'pe_ratio': 185.0},
            {'symbol': 'QCOM', 'name': 'Qualcomm Inc.', 'category': 'stock', 'current_price': 165.80, 'price_min': 150, 'price_max': 180, 'volatility': 1.1, 'market_cap': '185B', 'volume_24h': 6800000, 'dividend_yield': 2.05, 'pe_ratio': 20.0},
            {'symbol': 'TXN', 'name': 'Texas Instruments', 'category': 'stock', 'current_price': 185.40, 'price_min': 170, 'price_max': 200, 'volatility': 0.9, 'market_cap': '168B', 'volume_24h': 3200000, 'dividend_yield': 2.85, 'pe_ratio': 24.0},
            {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'category': 'stock', 'current_price': 625.30, 'price_min': 580, 'price_max': 670, 'volatility': 1.3, 'market_cap': '268B', 'volume_24h': 2800000, 'dividend_yield': 0, 'pe_ratio': 45.0},
            {'symbol': 'DIS', 'name': 'Walt Disney Co.', 'category': 'stock', 'current_price': 112.50, 'price_min': 105, 'price_max': 125, 'volatility': 1.0, 'market_cap': '205B', 'volume_24h': 10200000, 'dividend_yield': 0.35, 'pe_ratio': 72.0},
            {'symbol': 'HD', 'name': 'Home Depot Inc.', 'category': 'stock', 'current_price': 348.20, 'price_min': 330, 'price_max': 370, 'volatility': 0.8, 'market_cap': '345B', 'volume_24h': 3500000, 'dividend_yield': 2.35, 'pe_ratio': 22.0},
            {'symbol': 'WMT', 'name': 'Walmart Inc.', 'category': 'stock', 'current_price': 62.50, 'price_min': 58, 'price_max': 68, 'volatility': 0.6, 'market_cap': '503B', 'volume_24h': 6800000, 'dividend_yield': 1.45, 'pe_ratio': 28.0},
            {'symbol': 'PG', 'name': 'Procter & Gamble', 'category': 'stock', 'current_price': 162.30, 'price_min': 155, 'price_max': 170, 'volatility': 0.5, 'market_cap': '382B', 'volume_24h': 4200000, 'dividend_yield': 2.55, 'pe_ratio': 24.0},
            {'symbol': 'MA', 'name': 'Mastercard Inc.', 'category': 'stock', 'current_price': 468.50, 'price_min': 445, 'price_max': 490, 'volatility': 0.8, 'market_cap': '435B', 'volume_24h': 2200000, 'dividend_yield': 0.55, 'pe_ratio': 38.0},
            {'symbol': 'UNH', 'name': 'UnitedHealth Group', 'category': 'stock', 'current_price': 518.20, 'price_min': 495, 'price_max': 540, 'volatility': 0.7, 'market_cap': '476B', 'volume_24h': 2800000, 'dividend_yield': 1.35, 'pe_ratio': 21.0},
            {'symbol': 'ABBV', 'name': 'AbbVie Inc.', 'category': 'stock', 'current_price': 168.75, 'price_min': 160, 'price_max': 178, 'volatility': 0.7, 'market_cap': '298B', 'volume_24h': 4500000, 'dividend_yield': 3.85, 'pe_ratio': 25.0},
            {'symbol': 'MRK', 'name': 'Merck & Co.', 'category': 'stock', 'current_price': 128.40, 'price_min': 120, 'price_max': 135, 'volatility': 0.7, 'market_cap': '325B', 'volume_24h': 6200000, 'dividend_yield': 2.95, 'pe_ratio': 22.0},
            {'symbol': 'PEP', 'name': 'PepsiCo Inc.', 'category': 'stock', 'current_price': 172.30, 'price_min': 165, 'price_max': 180, 'volatility': 0.6, 'market_cap': '237B', 'volume_24h': 4200000, 'dividend_yield': 2.95, 'pe_ratio': 25.0},
            {'symbol': 'COST', 'name': 'Costco Wholesale', 'category': 'stock', 'current_price': 725.50, 'price_min': 680, 'price_max': 760, 'volatility': 0.9, 'market_cap': '322B', 'volume_24h': 1800000, 'dividend_yield': 0.65, 'pe_ratio': 45.0},
            {'symbol': 'CVS', 'name': 'CVS Health Corp.', 'category': 'stock', 'current_price': 75.25, 'price_min': 70, 'price_max': 82, 'volatility': 0.9, 'market_cap': '95B', 'volume_24h': 7200000, 'dividend_yield': 4.15, 'pe_ratio': 11.0},
            {'symbol': 'HON', 'name': 'Honeywell Intl.', 'category': 'stock', 'current_price': 202.30, 'price_min': 190, 'price_max': 215, 'volatility': 0.8, 'market_cap': '132B', 'volume_24h': 2500000, 'dividend_yield': 2.15, 'pe_ratio': 23.0},
            {'symbol': 'UPS', 'name': 'United Parcel Service', 'category': 'stock', 'current_price': 148.60, 'price_min': 140, 'price_max': 160, 'volatility': 0.9, 'market_cap': '127B', 'volume_24h': 3200000, 'dividend_yield': 4.35, 'pe_ratio': 16.0},
            {'symbol': 'GS', 'name': 'Goldman Sachs Group', 'category': 'stock', 'current_price': 395.20, 'price_min': 370, 'price_max': 420, 'volatility': 1.0, 'market_cap': '128B', 'volume_24h': 1800000, 'dividend_yield': 2.55, 'pe_ratio': 12.0},
            {'symbol': 'C', 'name': 'Citigroup Inc.', 'category': 'stock', 'current_price': 58.90, 'price_min': 55, 'price_max': 65, 'volatility': 1.0, 'market_cap': '112B', 'volume_24h': 14200000, 'dividend_yield': 3.85, 'pe_ratio': 10.0},
            {'symbol': 'GM', 'name': 'General Motors', 'category': 'stock', 'current_price': 42.50, 'price_min': 38, 'price_max': 48, 'volatility': 1.2, 'market_cap': '58B', 'volume_24h': 12500000, 'dividend_yield': 0.85, 'pe_ratio': 5.5},
            {'symbol': 'F', 'name': 'Ford Motor Co.', 'category': 'stock', 'current_price': 12.85, 'price_min': 11.5, 'price_max': 14.5, 'volatility': 1.1, 'market_cap': '51B', 'volume_24h': 48500000, 'dividend_yield': 4.85, 'pe_ratio': 7.0},
        ]
        
        # ============= TOP 20 MINERALS =============
        minerals = [
            {'symbol': 'GOLD', 'name': 'Gold', 'category': 'mineral', 'current_price': 2150.50, 'price_min': 2100, 'price_max': 2250, 'volatility': 0.8, 'market_cap': 'N/A', 'volume_24h': 1200000},
            {'symbol': 'SILV', 'name': 'Silver', 'category': 'mineral', 'current_price': 24.85, 'price_min': 23.5, 'price_max': 26.5, 'volatility': 1.0, 'market_cap': 'N/A', 'volume_24h': 2500000},
            {'symbol': 'PLAT', 'name': 'Platinum', 'category': 'mineral', 'current_price': 980.30, 'price_min': 950, 'price_max': 1050, 'volatility': 0.9, 'market_cap': 'N/A', 'volume_24h': 800000},
            {'symbol': 'PALL', 'name': 'Palladium', 'category': 'mineral', 'current_price': 1025.50, 'price_min': 980, 'price_max': 1100, 'volatility': 1.1, 'market_cap': 'N/A', 'volume_24h': 500000},
            {'symbol': 'COPP', 'name': 'Copper', 'category': 'mineral', 'current_price': 4.25, 'price_min': 3.9, 'price_max': 4.6, 'volatility': 0.8, 'market_cap': 'N/A', 'volume_24h': 5200000},
            {'symbol': 'LITH', 'name': 'Lithium', 'category': 'mineral', 'current_price': 15.25, 'price_min': 14, 'price_max': 18, 'volatility': 1.3, 'market_cap': 'N/A', 'volume_24h': 1800000},
            {'symbol': 'NICK', 'name': 'Nickel', 'category': 'mineral', 'current_price': 9.85, 'price_min': 9, 'price_max': 10.8, 'volatility': 1.0, 'market_cap': 'N/A', 'volume_24h': 2200000},
            {'symbol': 'ALU', 'name': 'Aluminum', 'category': 'mineral', 'current_price': 1.25, 'price_min': 1.15, 'price_max': 1.4, 'volatility': 0.7, 'market_cap': 'N/A', 'volume_24h': 8500000},
            {'symbol': 'ZINC', 'name': 'Zinc', 'category': 'mineral', 'current_price': 1.35, 'price_min': 1.25, 'price_max': 1.5, 'volatility': 0.7, 'market_cap': 'N/A', 'volume_24h': 3200000},
            {'symbol': 'URAN', 'name': 'Uranium', 'category': 'mineral', 'current_price': 52.50, 'price_min': 48, 'price_max': 58, 'volatility': 1.2, 'market_cap': 'N/A', 'volume_24h': 900000},
            {'symbol': 'DIAM', 'name': 'Diamond', 'category': 'mineral', 'current_price': 1240.00, 'price_min': 1180, 'price_max': 1320, 'volatility': 0.9, 'market_cap': 'N/A', 'volume_24h': 300000},
            {'symbol': 'BAUX', 'name': 'Bauxite', 'category': 'mineral', 'current_price': 89.40, 'price_min': 82, 'price_max': 95, 'volatility': 1.0, 'market_cap': 'N/A', 'volume_24h': 1500000},
            {'symbol': 'IRON', 'name': 'Iron Ore', 'category': 'mineral', 'current_price': 112.50, 'price_min': 105, 'price_max': 125, 'volatility': 0.9, 'market_cap': 'N/A', 'volume_24h': 4200000},
            {'symbol': 'COAL', 'name': 'Coal', 'category': 'mineral', 'current_price': 78.25, 'price_min': 72, 'price_max': 88, 'volatility': 1.1, 'market_cap': 'N/A', 'volume_24h': 3800000},
            {'symbol': 'RARE', 'name': 'Rare Earth', 'category': 'mineral', 'current_price': 45.80, 'price_min': 42, 'price_max': 52, 'volatility': 1.2, 'market_cap': 'N/A', 'volume_24h': 700000},
            {'symbol': 'MANG', 'name': 'Manganese', 'category': 'mineral', 'current_price': 3.25, 'price_min': 2.9, 'price_max': 3.6, 'volatility': 0.8, 'market_cap': 'N/A', 'volume_24h': 1200000},
            {'symbol': 'COBA', 'name': 'Cobalt', 'category': 'mineral', 'current_price': 32.50, 'price_min': 30, 'price_max': 36, 'volatility': 1.0, 'market_cap': 'N/A', 'volume_24h': 900000},
            {'symbol': 'GRAPH', 'name': 'Graphite', 'category': 'mineral', 'current_price': 12.80, 'price_min': 11.5, 'price_max': 14, 'volatility': 0.9, 'market_cap': 'N/A', 'volume_24h': 1000000},
            {'symbol': 'PHOS', 'name': 'Phosphate', 'category': 'mineral', 'current_price': 85.30, 'price_min': 80, 'price_max': 92, 'volatility': 0.7, 'market_cap': 'N/A', 'volume_24h': 600000},
            {'symbol': 'POTA', 'name': 'Potash', 'category': 'mineral', 'current_price': 45.25, 'price_min': 42, 'price_max': 50, 'volatility': 0.8, 'market_cap': 'N/A', 'volume_24h': 800000},
        ]
        
        created_count = 0
        
        # Delete existing assets first (optional)
        # Asset.objects.all().delete()
        
        # Create stocks
        for stock in stocks:
            try:
                obj, created = Asset.objects.get_or_create(
                    symbol=stock['symbol'],
                    defaults={
                        'name': stock['name'],
                        'category': stock['category'],
                        'current_price': Decimal(str(stock['current_price'])),
                        'price_change_24h': Decimal('0'),
                        'price_min': Decimal(str(stock['price_min'])),
                        'price_max': Decimal(str(stock['price_max'])),
                        'volatility': Decimal(str(stock['volatility'])),
                        'price_update_enabled': True,
                        'market_cap': stock.get('market_cap', ''),
                        'volume_24h': Decimal(str(stock['volume_24h'])),
                        'dividend_yield': Decimal(str(stock.get('dividend_yield', 0))) if stock.get('dividend_yield') else None,
                        'pe_ratio': Decimal(str(stock.get('pe_ratio', 0))) if stock.get('pe_ratio') else None,
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f"Created: {stock['symbol']}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating {stock['symbol']}: {e}"))
        
        # Create minerals
        for mineral in minerals:
            try:
                obj, created = Asset.objects.get_or_create(
                    symbol=mineral['symbol'],
                    defaults={
                        'name': mineral['name'],
                        'category': mineral['category'],
                        'current_price': Decimal(str(mineral['current_price'])),
                        'price_change_24h': Decimal('0'),
                        'price_min': Decimal(str(mineral['price_min'])),
                        'price_max': Decimal(str(mineral['price_max'])),
                        'volatility': Decimal(str(mineral['volatility'])),
                        'price_update_enabled': True,
                        'market_cap': mineral.get('market_cap', ''),
                        'volume_24h': Decimal(str(mineral['volume_24h'])),
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f"Created: {mineral['symbol']}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating {mineral['symbol']}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Total assets created: {created_count}"))
        self.stdout.write(self.style.SUCCESS(f"   - Stocks: {len(stocks)}"))
        self.stdout.write(self.style.SUCCESS(f"   - Minerals: {len(minerals)}"))