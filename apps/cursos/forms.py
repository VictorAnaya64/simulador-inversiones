import csv
import io

from django import forms
from django.contrib.auth import get_user_model

from apps.mercados.models import Instrumento

from .models import Curso

Usuario = get_user_model()


class FormularioCurso(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            'nombre', 'descripcion', 'fecha_inicio', 'fecha_fin', 'capital_inicial_mxn',
            'tasa_libre_riesgo_anual', 'spread_conversion_divisas', 'comision_operacion',
            'instrumentos_permitidos', 'benchmark_principal', 'operaciones_activas',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'capital_inicial_mxn': forms.NumberInput(attrs={'class': 'form-control'}),
            'tasa_libre_riesgo_anual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'spread_conversion_divisas': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'comision_operacion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'instrumentos_permitidos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
            'benchmark_principal': forms.Select(attrs={'class': 'form-select'}),
            'operaciones_activas': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['instrumentos_permitidos'].queryset = Instrumento.objects.filter(
            activo=True,
        ).exclude(tipo_instrumento='INDICE').order_by('bolsa', 'ticker')
        self.fields['benchmark_principal'].queryset = Instrumento.objects.filter(tipo_instrumento='INDICE')
        self.fields['instrumentos_permitidos'].required = False
        self.fields['benchmark_principal'].required = False


class FormularioAltaEstudiante(forms.Form):
    username = forms.CharField(max_length=150, label='Usuario', widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=150, label='Nombre(s)', widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, label='Apellidos', widget=forms.TextInput(attrs={'class': 'form-control'}))
    matricula = forms.CharField(max_length=30, required=False, label='Matricula', widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, label='Correo', widget=forms.EmailInput(attrs={'class': 'form-control'}))

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if Usuario.objects.filter(username=username).exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre de usuario.')
        return username


class FormularioAltaEstudiantesCSV(forms.Form):
    archivo_csv = forms.FileField(
        label='Archivo CSV (columnas: username,first_name,last_name,matricula,email)',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
    )

    def limpiar_filas(self):
        archivo = self.cleaned_data['archivo_csv']
        contenido = archivo.read().decode('utf-8-sig')
        lector = csv.DictReader(io.StringIO(contenido))
        filas_validas, errores = [], []
        columnas_requeridas = {'username', 'first_name', 'last_name'}
        if not columnas_requeridas.issubset(set(lector.fieldnames or [])):
            errores.append(f'El CSV debe incluir al menos las columnas: {", ".join(columnas_requeridas)}.')
            return [], errores
        for numero_fila, fila in enumerate(lector, start=2):
            username = (fila.get('username') or '').strip()
            if not username:
                errores.append(f'Fila {numero_fila}: username vacio, se omite.')
                continue
            if Usuario.objects.filter(username=username).exists():
                errores.append(f'Fila {numero_fila}: el usuario "{username}" ya existe, se omite.')
                continue
            filas_validas.append({
                'username': username,
                'first_name': (fila.get('first_name') or '').strip(),
                'last_name': (fila.get('last_name') or '').strip(),
                'matricula': (fila.get('matricula') or '').strip(),
                'email': (fila.get('email') or '').strip(),
            })
        return filas_validas, errores
