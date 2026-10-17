from decimal import Decimal

from django import forms

from .models import Sale


class CheckoutForm(forms.Form):
    customer_phone = forms.CharField(max_length=24, required=False)
    paid_amount = forms.DecimalField(min_value=Decimal("0"), decimal_places=2)
    payment_method = forms.ChoiceField(choices=Sale.PaymentMethod.choices)
    payment_reference = forms.CharField(max_length=120, required=False)
    discount_type = forms.ChoiceField(choices=Sale.DiscountType.choices)
    discount_value = forms.DecimalField(
        min_value=Decimal("0"), decimal_places=2, required=False, initial=Decimal("0")
    )


class DueCollectionForm(forms.Form):
    customer_id = forms.IntegerField(min_value=1)
    amount = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2)
    payment_method = forms.ChoiceField(choices=Sale.PaymentMethod.choices)
    reference = forms.CharField(max_length=120, required=False)
