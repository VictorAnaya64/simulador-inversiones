from django import forms

from apps.mercados.models import Moneda


class FormularioConversionDivisa(forms.Form):
    moneda_origen = forms.ChoiceField(choices=Moneda.choices, widget=forms.Select(attrs={'class': 'form-select'}))
    monto = forms.DecimalField(
        min_value=0.01, max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )

    def clean(self):
        datos = super().clean()
        if datos.get('moneda_origen') and 'monto' in datos:
            datos['moneda_destino'] = Moneda.USD if datos['moneda_origen'] == Moneda.MXN else Moneda.MXN
        return datos
