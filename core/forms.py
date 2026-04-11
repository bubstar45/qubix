from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Asset

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone = forms.CharField(required=False)
    country = forms.CharField(initial='United State', required=False)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'country', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

class VerificationForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6)

class BuyAssetForm(forms.Form):
    quantity = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=4)
    
    def __init__(self, *args, **kwargs):
        self.asset = kwargs.pop('asset', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than 0")
        
        total = quantity * self.asset.price
        if self.user.portfolio.cash_balance < total:
            raise forms.ValidationError(f"Insufficient funds. Need ${total:,.2f}")
        
        return quantity

class DepositForm(forms.Form):
    amount = forms.DecimalField(min_value=10, max_digits=12, decimal_places=2)
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than 0")
        return amount

class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(min_value=10, max_digits=12, decimal_places=2)
    wallet_address = forms.CharField(max_length=255)
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than 0")
        
        if self.user.portfolio.cash_balance < amount:
            raise forms.ValidationError(f"Insufficient funds. Available: ${self.user.portfolio.cash_balance:,.2f}")
        
        return amount