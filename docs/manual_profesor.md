# Manual del profesor

## Iniciar sesion

Entra a la URL de la plataforma con el usuario y contrasena que te dio
el administrador. Llegaras automaticamente a **Mis cursos**.

## Crear un curso

1. En **Mis cursos**, boton **Crear curso**.
2. Completa nombre, fechas de inicio/fin, capital inicial (en USD),
   tasa libre de riesgo anual y comision por operacion (puedes dejar
   los valores por defecto si no tienes una preferencia especifica).
3. En **Instrumentos permitidos**, selecciona que acciones/ETF (todos
   listados en NYSE/NASDAQ, en USD) pueden operar tus estudiantes. Si
   no seleccionas ninguno, se permiten **todos** los instrumentos
   activos del catalogo.
4. En **Benchmark principal**, elige el "Indice Sintetico EUA" (o el
   indice que corresponda) contra el cual se compararan los
   portafolios de tus estudiantes.
5. Guarda. El curso queda con operaciones activas por defecto.

## Dar de alta estudiantes

Desde el detalle del curso, boton **Dar de alta estudiantes**:

- **Alta individual**: llena usuario, nombre, apellidos y matricula.
  El sistema genera una contrasena temporal que se muestra **una sola
  vez** en pantalla — anotala y compartela de forma segura con el
  estudiante (por ejemplo, en persona o por un canal cifrado; evita
  mandarla por un medio inseguro).
- **Alta masiva por CSV**: sube un archivo con columnas
  `username,first_name,last_name,matricula,email` (las dos primeras y
  la tercera son obligatorias). Cada fila valida crea una cuenta y
  genera su propia contrasena temporal, mostradas todas juntas al
  final.

Cada estudiante dado de alta se inscribe automaticamente en el curso y
recibe su capital inicial de inmediato.

## Consultar y comparar a tus estudiantes

En el detalle del curso veras una tabla con, para cada estudiante:
efectivo disponible, rendimiento acumulado, volatilidad anualizada,
Sharpe y maximo drawdown (calculados desde el inicio del curso). Puedes
reordenar la tabla por **Rendimiento** o por **Sharpe** (ajustado por
riesgo) con los botones correspondientes.

**Importante**: el estudiante con mayor rendimiento absoluto no es
necesariamente el que tomo las mejores decisiones — pudo haber asumido
mucho mas riesgo. Usa el orden por Sharpe para una comparacion ajustada
por riesgo.

Si una fila dice "informacion insuficiente", significa que ese
estudiante no tiene todavia suficientes dias de historial para calcular
metricas confiables (se requieren varios dias de valuaciones).

## Exportar resultados

Desde el detalle del curso, botones **Exportar CSV** y **Exportar
Excel**: descargan una tabla con los mismos datos de la tabla en
pantalla, lista para análisis fuera de la plataforma o para entregar
una calificacion.

## Suspender o reactivar operaciones

El campo **Operaciones activas** del curso (editable desde el admin de
Django, `/admin/`, seccion Cursos) permite suspender temporalmente
todas las compras/ventas nuevas de tus estudiantes sin afectar las
posiciones ya existentes. Las ordenes ya pendientes antes de suspender
se siguen procesando normalmente por el cron.

## Reiniciar una simulacion

Esta primera version no incluye un boton de "reinicio" en la interfaz
(por disenio: borrar el historial de un curso destruiria la
trazabilidad que pide el proyecto). Si necesitas reiniciar la
simulacion de un curso conservando trazabilidad, la via recomendada es:
crear un **nuevo curso** (con un nombre que indique la nueva vuelta,
por ejemplo "Grupo A - Intento 2") e inscribir ahi a los estudiantes;
el curso anterior permanece intacto para auditoria. Contacta al
administrador si necesitas un procedimiento distinto.

## Revisar auditoria

El administrador general puede consultar el registro completo de
auditoria desde `/admin/` &rarr; Registros de auditoria (altas de
estudiantes, creacion de cursos, exportaciones, etc.).
