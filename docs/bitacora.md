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
- Rechazos: Panadería La Espiga (falta código postal), Sanitarios Rivera (falta dirección), Carnicería El Gaucho (bultos menor a 1). Ojo: esos tres son **destinatarios**. Los clientes de LogiSur son Textil Del Plata SRL (R-10000477) y Ferretería Industrial Norte SA (R-10000516 y R-10000541).
- Un envío confirmado en el segundo intento tras un error de la API (Pinturerías del Oeste).
- Segunda corrida: 0 cargados, 20 ya existían. Nada se duplica.
- Atrasados al 2026-10-03: ver `caso-expreso/reports/atrasados_2026-10-03.md`.

## 9. Las tres direcciones visuales (T1)

Están en `design/resultado-corrida/`, con el brief de trabajo en `brief.md`. Las tres responden lo mismo y en el mismo orden: primero la frase que contesta "¿Tengo que hacer algo?", después qué corregir y dónde, después lo que salió bien (plegado) y al final el detalle técnico. Donde se diferencian es en la forma de leer la pantalla:

- **01 · La nota.** Una sola columna, como una nota que te deja un compañero antes de irse. La respuesta va en letra serif grande y los tres arreglos están escritos como frases, no como tarjetas. Es la más calma y la más humana. Su costo: si un día hay 30 rechazos, una lista de frases se vuelve larga de recorrer.
- **02 · La bandeja.** Una aplicación con menú (Cargar export, Cargas, Atrasados), una lista de pendientes y, al lado, el detalle del que elegiste, con los pasos para resolverlo y un "Ya lo corregí". Cuando marcás los tres, el botón de volver a cargar pasa a ser el principal. Escala mejor y deja lugar para la vista de atrasados. Su costo: es la que más se parece a "un sistema" y la que más elementos muestra.
- **03 · El mapa.** Cada envío es un casillero. Los 20 que están bien quedan verdes y quietos; los 3 que necesitan algo resaltan. Los mismos casilleros aparecen al elegir el archivo (vacíos) y durante la carga (se van llenando), así que los tres momentos se ven como una sola cosa. Su costo: lo que salió bien queda a la vista (en silencio, pero visible), y con cientos de envíos el mapa necesita agruparse.

Cómo se aplicó el stack, con criterio y no como receta:

- **impeccable** (modo Operate): la ambición está en la precisión y en lo que se saca, no en efectos. Sin métricas gigantes, sin etiquetas en mayúsculas arriba de los títulos, sin degradados ni vidrio.
- **better-writing:** cada problema dice qué falta, para quién y qué hacer. Los botones arrancan con un verbo ("Volver a cargar el export"). Los "Ver detalle técnico" llevan el remito, para que tengan sentido leídos solos (un lector de pantalla los lista sin contexto).
- **better-colors / better-accessibility:** colores en OKLCH, contraste medido (todo el texto por encima de 4,5:1; los bordes de los casilleros pendientes, por encima de 3:1). El estado nunca depende solo del color: siempre hay ícono y texto. Navegación con teclado, foco visible y respeto por "reducir movimiento".
- **unslop:** se usó como lista de cosas a evitar (el aspecto de plantilla generada por IA) y para obligarnos a darle a cada dirección un carácter propio. Se clonó aparte y no se corrió ningún script.

### Por qué el mapa

Mateo eligió el mapa y coincidimos. Las razones:

- **Responde la pregunta de un vistazo.** Antes de leer una palabra ya se ve que casi todo está verde y que hay tres casilleros distintos. La frase de arriba lo confirma.
- **Hace visible lo que antes había que explicar.** Que el puente no duplica envíos se entiende solo: en la segunda corrida los mismos casilleros aparecen como "ya estaba". No hace falta saber qué es un 409.
- **Une los tres momentos.** Elegir el archivo, ver el avance y leer el resultado usan el mismo objeto. No hay que aprender tres pantallas.
- **Se vende solo.** La pregunta de la entrevista fue cómo se lo venderíamos a un cliente. Ver los casilleros llenarse en vivo se entiende en una demo de diez segundos.
- **El arreglo sigue siendo texto.** La tabla de abajo dice qué falta, para quién, de qué cliente y en qué remito. El mapa orienta; las frases resuelven.

Lo que hay que cuidar al implementarlo:

- **Volumen.** Con los 23 envíos de hoy funciona. Si un día son cientos, los verdes se agrupan en un solo bloque ("240 cargados") y solo se muestran sueltos los que necesitan algo.
- **Pantallas chicas.** En el celular, lo que hay que corregir va antes que el mapa.
- **Lo que salió bien queda a la vista.** Es el único punto donde el mapa se aparta del principio "resumido y plegado". Se compensa con verdes suaves y sin texto extra; si molesta en el uso real, el mapa se puede plegar.

### Movimiento

Mateo pidió sumar animaciones sutiles, al estilo de Emil Kowalski, que den sensación de cuidado y de fluidez. El criterio: el movimiento tiene que explicar algo, no decorar.

- **La carga en vivo es el momento principal.** Cada casillero se completa cuando Expreso Andino confirma el envío. Ahí el movimiento es información: muestra el avance.
- **Al abrir el resultado no se mueve nada.** Quien entra a ver qué tiene que hacer no tiene que esperar una coreografía.
- **Todo lo demás responde a la persona.** Elegir un casillero, abrir un detalle o apretar un botón tiene una respuesta corta (menos de 300 ms) que confirma que algo pasó.
- **Nada en loop y nada que distraiga.** Quien tiene activado "reducir movimiento" en su sistema ve los mismos cambios de estado, sin desplazamientos.

### Ronda de pulido (T1.1): que deje de parecer una plantilla

Con el mapa elegido, Mateo pidió una ronda de pulido: el flujo de animación de Emil Kowalski (sacar, mejorar, revisar rendimiento y recién después agregar), más better-ui, impeccable y unslop, con criterio propio para salir de lo genérico. Las decisiones con sus valores están en `design/resultado-corrida/polish-t1-1.md`.

El diagnóstico fue: **la estructura es nuestra, la piel es intercambiable**. Si se cambiaba "Expreso Andino" por otro nombre, la pantalla servía igual para cualquier producto. Lo que la hacía genérica era la fuente del sistema, las cajas redondeadas con sombra (y cajas dentro de cajas), un trío de colores pastel de catálogo, una palabra del título pintada de naranja y una etiqueta chica arriba de los títulos. Lo que la hacía propia, y se conserva, es el casillero por remito, la respuesta como frase, el ámbar en lugar del rojo y los textos con nombres reales.

Para darle identidad buscamos un mundo concreto: **el talonario de remitos**. Original, duplicado y triplicado en papel carbónico, tinta de sello, resaltador. De ahí salen las decisiones:

- **Tipografía: Atkinson Hyperlegible Next.** La diseñó el Braille Institute para que ningún carácter se confunda con otro (0 y O, 1, l e I). Es exactamente el riesgo de leer "R-10000477" o "AND4BD591C". No está entre las fuentes gastadas por las interfaces generadas con IA, tiene licencia abierta y va incrustada en la página, así que sigue funcionando sin internet. Un detalle que se aceptó a conciencia: su cero lleva una barra (Ø) y la fuente no trae un cero sin barra. En los códigos ayuda; en un texto como "los otros 20" se nota un poco técnico. Se queda porque el beneficio en remitos y seguimientos pesa más; si en el uso real molesta, el plan B es Public Sans.
- **Una sola mancha de color, y es lo que requiere acción.** Los 20 envíos que están bien bajan a un verde casi gris. "Ya estaba" deja de ser celeste y pasa a una trama de carbónico. Los 3 pendientes van en amarillo de resaltador, y el "3 de 23 envíos" del título queda subrayado como con un resaltador, en vez de pintado.
- **El azul de tinta de sello** une el botón principal, la selección y el foco.
- **Radios más chicos (2, 4, 6 y 10 px).** Un remito, una etiqueta o un casillero de depósito tienen esquinas casi vivas. Los radios grandes eran justamente parte del aspecto de plantilla.
- **Menos cajas.** El mapa va directo sobre la página; la única hoja elevada es la de "Para corregir en LogiSur", porque lo que hay que hacer es papel.
- **El movimiento se ajustó con el flujo de Emil.** Se sacó un hover casi imperceptible. Las curvas pasaron a una ease-out más decidida y la carga en vivo dura 2 segundos en vez de 3. Las filas a corregir aparecen en el momento en que su casillero se resuelve, así se ve la causa y el efecto. Al terminar, los 3 casilleros ámbar hacen un único pulso que los ata a la frase del título.

Cuando las skills se contradecían (pasa entre better-ui, impeccable y unslop en sombras, radios, curvas y tipografía), decidió lo que dejaba más clara la pantalla para operaciones y, ante la duda, el pedido explícito de Mateo. La tabla de conflictos y cómo se resolvió cada uno está en `polish-t1-1.md`.

### Segunda pasada (T1.2): mirar con ojo crítico

Después de la ronda de pulido revisamos el resultado como lo haría alguien escéptico, y salieron cinco ajustes:

- **El amarillo gritaba.** Relleno saturado, borde y negrita decían lo mismo tres veces, y los tres casilleros competían con la frase del título. El relleno pasó a un amarillo lavado; el borde y la negrita siguen marcando. El resaltador fuerte quedó solo para el "3 de 23 envíos" del título.
- **Una idea, una vez.** "Volvé a cargar el export" aparecía dos veces. Quedó solo en la hoja de arreglos, que es donde se actúa: "Cuando los corrijas, volvé a cargar el export. No se duplica nada."
- **"Elegí", no "Tocá".** Se usa en una computadora.
- **Sin hueco durante la carga en vivo.** La leyenda sube debajo del contador mientras corre y vuelve a su lugar al terminar.
- **La tipografía se elige mirando.** El cero con barra de Atkinson ayuda en los códigos, pero en "10:47" o en una fecha la pantalla parece una terminal. En vez de decidirlo razonando, armamos el artboard 04: el mismo mapa en Public Sans (la tipografía del gobierno de EE. UU., licencia abierta), para elegir viéndolas lado a lado.

## 10. Registro de decisiones

| Fecha | Decisión | Por qué | Descartado |
| --- | --- | --- | --- |
| 2026-11-03 | Repo nuevo (`expreso-panel`) en lugar de sumar la UI al repo del challenge | El repo del challenge queda como se entregó y se defendió; el panel es una iteración posterior, a partir del feedback de la entrevista | Modificar `caso-expreso` |
| 2026-11-03 | El panel no cambia la lógica del puente | La lógica ya está testeada; el problema es de comunicación, no de reglas | Reescribir el puente |
| 2026-11-03 | Diseñar para la persona de operaciones de LogiSur | Una persona concreta define qué es "lo justo y necesario" | Diseñar para "no técnicos" en general |
| 2026-11-03 | Tres direcciones visuales antes de implementar | Elegir viendo, no imaginando | Ir directo al código |
| 2026-11-03 | Contar envíos (23), no filas del resumen (24) | R-10000507 viene dos veces en el export pero es un solo envío. Para operaciones son 3 para corregir y 20 en orden; la repetición se aclara aparte | Mostrar "21 sin acción pendiente" como el resumen técnico |
| 2026-11-03 | Mostrar el cliente de LogiSur además del destinatario | El resultado del puente trae el destinatario; el cliente (a quien hay que llamar) sale del export. El panel puede leerlo sin tocar la lógica | Mostrar solo el destinatario, como el resumen técnico |
| 2026-11-03 | Usar la observación del remito en la frase | "Cliente no informó CP" dice a quién pedirle el dato; ninguna frase genérica dice tanto | Frase genérica por campo |
| 2026-11-03 | El reintento no se cuenta en la vista principal | Pinturerías del Oeste quedó cargado; "confirmado en el intento 2" es ruido interno y queda en el detalle técnico | Avisar del error de la API |
| 2026-11-03 | Rechazado se marca en ámbar, nunca en rojo | El envío no se perdió y nadie hizo algo mal: es "falta un dato", no un error grave | Rojo de error |
| 2026-11-03 | Detalle técnico detrás de "Ver detalle técnico de R-…" | Sistemas o soporte lo necesitan (HTTP 422, campo de la API, archivo del resumen, código de salida); operaciones no. El remito en el texto hace que el enlace se entienda solo | Borrarlo, o mostrarlo siempre |
| 2026-11-03 | Textos en español con voseo, sin modismos | Así le habla el software argentino a sus usuarios (argentina.gob.ar también). Una sola forma en todo el flujo. Mateo puede pedir otra | "Usted" o tuteo |
| 2026-11-03 | Sin tipografías externas: fuentes del sistema | Las páginas tienen que funcionar sin internet y cargar al instante; la personalidad la dan el tamaño, el espacio y las palabras | Fuentes web |
| 2026-11-03 | Las tres direcciones comparten contenido y orden, y cambian la forma de leer | Así la elección es sobre la experiencia (nota, bandeja de trabajo, mapa) y no sobre el texto | Variar solo colores |
| 2026-11-03 | Dirección elegida: 03 · El mapa | Responde de un vistazo, hace visible que no se duplica nada, une los tres momentos en un solo objeto y se entiende en una demo. Las frases siguen resolviendo el arreglo | 01 · La nota (no escala), 02 · La bandeja (demasiado "sistema" para la tarea) |
| 2026-11-03 | Animaciones solo con propósito: la carga en vivo, y respuestas cortas a lo que hace la persona | El movimiento tiene que explicar (avance, selección) y dar sensación de cuidado sin hacer esperar. Nada al abrir el resultado y nada en loop | Animación de entrada en cada visita, efectos decorativos |
| 2026-11-03 | Mundo visual "Remito": talonario con carbónico, tinta de sello, resaltador | Darle a la pantalla una identidad que venga del oficio de quien la usa, y no de una plantilla | Paleta y estilo genéricos de SaaS |
| 2026-11-03 | Tipografía Atkinson Hyperlegible Next, incrustada en la página (reemplaza la decisión de usar fuentes del sistema) | Está hecha para no confundir caracteres parecidos, que es el riesgo con códigos de remito y de seguimiento; no está gastada; al ir incrustada sigue funcionando sin internet | Fuente del sistema (genérica), Inter, DM Sans, Geist, IBM Plex y otras muy usadas |
| 2026-11-03 | Una sola mancha de color: amarillo resaltador para lo que requiere acción; verde casi gris para lo que salió bien; trama para "ya estaba" | Lo que no requiere acción no tiene que competir con lo que sí | Verde menta, celeste y ámbar con el mismo peso |
| 2026-11-03 | Radios de 2, 4, 6 y 10 px | Esquinas de papel y de etiqueta; los radios grandes eran parte del aspecto genérico | Radios de 10 a 20 px |
| 2026-11-03 | Menos cajas: mapa sobre la página, una sola hoja elevada para lo que hay que corregir, sin etiquetas arriba de los títulos | Cajas dentro de cajas agregan ruido y no agrupan nada que el espacio no agrupe | Tarjeta para cada bloque |
| 2026-11-03 | Movimiento ajustado con el flujo de Emil Kowalski: sacar el hover de brillo, curva ease-out más marcada, carga en vivo de ~2 s, filas que aparecen cuando su casillero se resuelve, un solo pulso final en los pendientes | Cada movimiento explica algo (avance, causa y efecto); lo imperceptible se saca | Mantener la versión anterior sin auditar |
| 2026-11-03 | Relleno amarillo lavado en los pendientes; resaltador fuerte solo en el título | Tres señales iguales hacían que los casilleros le ganaran a la frase, que es la respuesta | Amarillo saturado en todo |
| 2026-11-03 | Cada indicación aparece una sola vez, donde se actúa | Repetir la misma frase cansa y le resta peso | Repetir "volvé a cargar el export" junto a cada botón |
| 2026-11-03 | Comparar Atkinson Hyperlegible Next y Public Sans en dos artboards antes de elegir | El cero con barra ayuda en códigos pero endurece horas y fechas; la elección es visual | Decidir la fuente sin verla |
| 2026-11-03 | Tipografía final: Public Sans (reemplaza a Atkinson Hyperlegible Next) | Vistas lado a lado, las horas, fechas y cantidades se leen como texto común; los códigos siguen siendo claros y la personalidad la ponen el casillero, el resaltador y la trama | Atkinson Hyperlegible Next (cero con barra) |
