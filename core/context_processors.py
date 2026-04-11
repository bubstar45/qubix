# core/context_processors.py
from .models import PhysicalCart

def portfolio_data(request):
    if request.user.is_authenticated:
        try:
            portfolio = request.user.portfolio
            
            # Get cart count
            cart_count = 0
            try:
                cart = PhysicalCart.objects.get(user=request.user)
                cart_count = cart.get_item_count()
            except PhysicalCart.DoesNotExist:
                cart_count = 0
            
            return {
                'portfolio': portfolio,
                'total_value': portfolio.total_value(),
                'cash_balance': portfolio.cash_balance,
                'cart_count': cart_count,  # ← ADD THIS LINE
            }
        except:
            return {'cart_count': 0}  # ← ADD THIS
    return {'cart_count': 0}  # ← ADD THIS