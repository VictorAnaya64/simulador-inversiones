from django import forms


class FormularioOrden(forms.Form):
    cantidad = forms.IntegerField(
        min_value=1, label='Cantidad de titulos',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
    )
    clave_idempotencia = forms.CharField(widget=forms.HiddenInput())
