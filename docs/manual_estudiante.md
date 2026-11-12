# Manual del estudiante

## Iniciar sesion

Usa el usuario y la contrasena temporal que te dio tu profesor. Al
entrar, llegas directo a tu **Panel**.

## Tu panel principal

Muestra: valor total de tu portafolio (en USD), rendimiento acumulado,
efectivo disponible (y cuanto de ese efectivo esta "reservado" por
ordenes pendientes), la evolucion historica de tu portafolio y la
distribucion de tu inversion por instrumento.

## Buscar instrumentos

En **Mercado**, busca por ticker o nombre. Todos los instrumentos
cotizan en NYSE o NASDAQ y estan denominados en USD. Cada instrumento
muestra su bolsa, tipo, ultimo precio conocido y una grafica de precio
historico (ajustado por splits y dividendos). Desde ahi tienes los
botones **Comprar** y **Vender**.

## Comprar y vender

1. Indica la cantidad de titulos (numeros enteros; no se permiten
   titulos fraccionados en esta version).
2. Confirma. **Importante**: tu orden NO se ejecuta de inmediato ni al
   precio que ves en pantalla — se ejecutara al precio de **cierre**
   de la **siguiente sesion bursatil disponible** (nunca el mismo dia).
   Si el precio de cierre real termina siendo mayor a lo estimado y no
   tienes suficiente efectivo adicional disponible, tu orden de compra
   se **rechaza** automaticamente (nunca se te cobra de mas ni quedas
   con saldo negativo).
3. Todo tu efectivo y todos los instrumentos estan en USD; no hay que
   convertir ninguna divisa para comprar nada.

## Revisar tus ordenes

En **Operaciones** ves todas tus ordenes: pendientes, ejecutadas (con
el precio real al que se ejecutaron), canceladas y rechazadas (con el
motivo). Puedes cancelar una orden mientras siga **pendiente** — esto
libera de inmediato el efectivo o los titulos que tenia reservados.

## Analizar tu portafolio

En **Analisis** encuentras, para distintos periodos (1 mes, 3 meses, 6
meses, 1 anio y desde el inicio del curso): tu rendimiento acumulado,
volatilidad anualizada, Sharpe, beta, maximo drawdown y VaR historico
al 95%. Si un periodo muestra "informacion insuficiente", significa
que todavia no ha pasado suficiente tiempo para calcularlo de forma
confiable — no es un error.

Tambien veras, si tu profesor configuro un benchmark para el curso, una
grafica comparando tu portafolio contra ese indice de referencia (ambos
normalizados a 100 al inicio del periodo comun), la matriz de
correlacion entre los instrumentos permitidos en tu curso, y la
frontera eficiente de Markowitz con los portafolios teoricos de minima
varianza y de maximo Sharpe para ese mismo conjunto de instrumentos —
utiles para comparar tus decisiones reales contra lo que la teoria de
portafolios sugeriria.

## Preguntas frecuentes

**¿Por que mi orden sigue "pendiente" despues de un dia?** Puede que
todavia no se haya importado el precio de cierre de esa sesion (el
profesor/administrador corre esa importacion por las tardes); se
ejecutara automaticamente en cuanto el precio este disponible.

**¿Por que mi rendimiento no se actualiza al momento de comprar/vender?**
La valuacion de tu portafolio se recalcula una vez al dia (no en cada
clic), para que el sistema funcione bien incluso con muchos estudiantes
conectados a la vez.
