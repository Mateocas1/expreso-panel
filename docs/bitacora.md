# Bitácora · Panel de operaciones para el puente LogiSur → Expreso Andino

Este documento registra cómo pensamos el panel: el problema, las decisiones, por qué se tomó cada una y qué se descartó. Sirve como fuente para el mail de seguimiento a Geno Insights. Cada decisión nueva se agrega al final de "Registro de decisiones", con fecha y motivo.

---

## 1. De dónde sale

En la entrevista técnica del 3/11/2026, Ignacio Penissi (Co-Founder y CTO de Geno Insights) preguntó cómo le venderíamos esta automatización a un cliente, y sugirió una interfaz. Su punto: una persona no técnica tiene que poder entender qué está pasando, y en la terminal, con códigos como 409 o 503, eso no se entiende.

El puente ya existe y funciona: es el repo `caso-expreso` (github.com/Mateocas1/caso-expreso). Lee el export diario de remitos de LogiSur, se queda con los de Expreso Andino, los carga en su API y deja un resumen. Se puede correr dos veces sin duplicar envíos.

## 2. El problema, dicho en simple

El puente le habla bien a una máquina: códigos de salida para un cron, estados HTTP, un resumen en Markdown. Pero la persona que lo usa todos los días no es una máquina. Es alguien de operaciones que necesita responder una sola pregunta:

> **¿Tengo que hacer algo?**

Hoy, para responderla, tiene que leer una tabla, saber qué es un 409 y entender que "destinatario.codigo_postal: required non-empty string" quiere decir "falta el código postal".

## 3. Para quién diseñamos

No diseñamos "para no técnicos" en general. Diseñamos para una persona concreta: **quien opera los envíos en LogiSur**. Conoce su negocio, los clientes y los remitos. No conoce HTTP, APIs ni códigos de error, y no tiene por qué conocerlos.

## 4. Principios

1. **Primero lo que requiere acción.** Lo que salió bien se resume; lo que hay que corregir se muestra.
2. **Cada mensaje dice qué pasó y qué hacer.** Nunca un código solo.
3. **Lo justo y necesario.** Si un dato no cambia lo que la persona hace, no va en la vista principal.
4. **El detalle técnico no se borra: se guarda.** Queda en un "ver detalle" para sistemas o soporte.
5. **La lógica no cambia.** El panel es una capa nueva sobre el puente existente. Analogía: el tablero de un auto. El motor no se toca; cambia lo que ve quien maneja. Los tests del puente siguen protegiendo las reglas de negocio.

## 5. De códigos a frases (borrador inicial)

El puente ya clasifica cada remito en exactamente uno de cinco resultados. Cada uno pasa a ser una frase:

| Resultado técnico | Frase para operaciones (borrador) |
| --- | --- |
| Cargado (`201`) | "Listo. Expreso Andino ya tiene este envío." |
| Ya existía (`409`) | "Ya estaba cargado de antes. No se duplicó." |
| Duplicado en el export | "Este remito venía repetido en el archivo. Lo cargamos una sola vez." |
| Rechazado (`422` o dato que no se puede mapear) | Frase específica por campo. Ejemplo real: `destinatario.codigo_postal: required non-empty string` → "Falta el código postal de Panadería La Espiga. Cargalo en LogiSur y volvé a cargar." |
| Falló (`5xx` o sin conexión, después de reintentar) | "Expreso Andino no respondió. No se perdió nada: probá de nuevo en unos minutos." |
| No se pudo correr (key inválida, export ilegible) | "No pudimos conectarnos con Expreso Andino. Avisale a sistemas." |

Un caso fino: un `503` seguido de un `409` en el reintento. Para la máquina son dos eventos; para operaciones es uno solo: "Listo, el envío está cargado". La interfaz no tiene que contar el ruido interno.

Estas frases son un borrador: se ajustan durante el diseño.

## 6. Qué se ve, en qué orden

1. Una frase grande arriba que resume la corrida. Ejemplo con los datos del kit: "19 envíos cargados. 3 necesitan que los revises."
2. Tarjetas con lo que requiere acción: qué remito, de qué cliente, qué falta y dónde corregirlo.
3. Lo que salió bien, resumido y plegado.
4. Una vista aparte para los envíos atrasados.

Tres momentos: elegir el export y cargar, ver el avance en vivo, leer el resultado.

## 7. Cómo lo construimos

- **Diseño primero.** Tres direcciones visuales para comparar antes de escribir una línea de código de la aplicación.
- **Stack de diseño:** gentle-design (direcciones en un canvas), impeccable 4.8, la familia better (better-ui, better-writing, better-interface, better-layout, better-typography, better-colors, better-accessibility) y unslop (github.com/heydamir/unslop), aplicados con criterio propio, no como receta.
- **Técnica (a confirmar al implementar):** un servidor Python chico que reutiliza el código del puente, y una página web simple. Sin frameworks pesados, para poder explicarlo entero.

## 8. Datos reales para diseñar

Los diseños usan los datos del kit del challenge, no datos inventados:

- Primera corrida: 51 remitos en el export, 24 de Expreso Andino → 19 cargados, 1 ya existía, 1 duplicado en el export, 3 rechazados.
- Rechazos: Panadería La Espiga (falta código postal), Sanitarios Rivera (falta dirección), Carnicería El Gaucho (bultos menor a 1).
- Un envío confirmado en el segundo intento tras un error de la API (Pinturerías del Oeste).
- Segunda corrida: 0 cargados, 20 ya existían. Nada se duplica.
- Atrasados al 2026-10-03: ver `caso-expreso/reports/atrasados_2026-10-03.md`.

## 9. Registro de decisiones

| Fecha | Decisión | Por qué | Descartado |
| --- | --- | --- | --- |
| 2026-11-03 | Repo nuevo (`expreso-panel`) en lugar de sumar la UI al repo del challenge | El repo del challenge queda como se entregó y se defendió; el panel es una iteración posterior, a partir del feedback de la entrevista | Modificar `caso-expreso` |
| 2026-11-03 | El panel no cambia la lógica del puente | La lógica ya está testeada; el problema es de comunicación, no de reglas | Reescribir el puente |
| 2026-11-03 | Diseñar para la persona de operaciones de LogiSur | Una persona concreta define qué es "lo justo y necesario" | Diseñar para "no técnicos" en general |
| 2026-11-03 | Tres direcciones visuales antes de implementar | Elegir viendo, no imaginando | Ir directo al código |
