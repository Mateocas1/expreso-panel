# Bitácora · Panel de operaciones para el puente LogiSur → Expreso Andino

Esta bitácora cuenta cómo se pensó el panel: el problema, para quién es, las decisiones de diseño y por qué se tomó cada una, qué se descartó y qué encontraron las revisiones. La última sección es el registro de decisiones, con fecha y motivo. Cómo está armado por dentro se cuenta en [`como-se-construyo.md`](como-se-construyo.md).

---

## 1. De dónde sale

En la entrevista técnica del 3/11/2026, Ignacio Penissi (Co-Founder y CTO de Geno Insights) preguntó cómo le venderíamos esta automatización a un cliente y sugirió una interfaz. Su punto: una persona no técnica tiene que poder entender qué está pasando, y en la terminal, con códigos como 409 o 503, eso no se entiende.

El puente ya existía y funciona: es el repo [`caso-expreso`](https://github.com/Mateocas1/caso-expreso). Lee el export diario de remitos de LogiSur, se queda con los de Expreso Andino, los carga en su API y deja un resumen. Se puede correr dos veces sin duplicar envíos.

## 2. El problema

El puente le habla bien a una máquina: códigos de salida para un cron, estados HTTP, un resumen en Markdown. Pero quien lo usa todos los días no es una máquina. Es alguien de operaciones que necesita responder una sola pregunta:

> **¿Tengo que hacer algo?**

Hoy, para responderla, tiene que leer una tabla, saber qué es un 409 y entender que `destinatario.codigo_postal: required non-empty string` quiere decir «falta el código postal».

## 3. Para quién

Diseñamos para una persona concreta, no para «los no técnicos» en general: **quien opera los envíos en LogiSur**. Conoce su negocio, los clientes y los remitos. No conoce HTTP, APIs ni códigos de error, y no tiene por qué conocerlos. Una persona concreta también define qué es «lo justo y necesario».

## 4. Principios

1. **Primero lo que requiere acción.** Lo que salió bien se resume; lo que hay que corregir se muestra.
2. **Cada mensaje dice qué pasó y qué hacer.** Nunca un código solo.
3. **Lo justo y necesario.** Si un dato no cambia lo que la persona hace, no va en la vista principal.
4. **El detalle técnico no se borra: se guarda.** Queda en un «Ver detalle técnico» para sistemas o soporte.
5. **La lógica no cambia.** El panel es una capa nueva sobre el puente existente, como el tablero de un auto: el motor no se toca y cambia lo que ve quien maneja. Los tests del puente siguen protegiendo las reglas de negocio.

## 5. Diseño

Primero el diseño, después el código. Las tres direcciones visuales y las rondas de pulido están en `design/resultado-corrida/`; los criterios de trabajo de cada una, en `brief.md` y `polish-notes.md`.

### Los datos

Los diseños usan los datos reales del kit del challenge, no datos inventados:

- Primera corrida: 51 remitos en el export, 24 de Expreso Andino → 19 cargados, 1 ya existía, 1 duplicado en el export, 3 rechazados.
- Rechazos: Panadería La Espiga (falta código postal), Sanitarios Rivera (falta dirección), Carnicería El Gaucho (bultos menor a 1). Esos tres son **destinatarios**; los clientes de LogiSur son Textil Del Plata SRL (R-10000477) y Ferretería Industrial Norte SA (R-10000516 y R-10000541).
- Un envío confirmado en el segundo intento tras un error de la API (Pinturerías del Oeste).
- Segunda corrida: 0 cargados, 20 ya existían. Nada se duplica.
- Atrasados al 2026-10-03: ver `caso-expreso/reports/atrasados_2026-10-03.md`.

### Qué se ve, en qué orden

1. Una frase grande arriba que resume la corrida. Con los datos del kit: «3 de 23 envíos esperan un dato de LogiSur.»
2. Lo que requiere acción: qué remito, de qué cliente, qué falta y dónde corregirlo.
3. Lo que salió bien, resumido.
4. Una vista aparte para los envíos atrasados.

Tres momentos: elegir el export y cargar, ver el avance en vivo, leer el resultado.

### Tres direcciones

Las tres responden lo mismo y en el mismo orden: primero la frase que contesta «¿Tengo que hacer algo?», después qué corregir y dónde, después lo que salió bien (plegado) y al final el detalle técnico. Donde se diferencian es en la forma de leer la pantalla:

- **01 · La nota.** Una sola columna, como una nota que te deja un compañero antes de irse. La respuesta va en letra serif grande y los tres arreglos están escritos como frases, no como tarjetas. Es la más calma y la más humana. Su costo: con 30 rechazos, una lista de frases se vuelve larga de recorrer.
- **02 · La bandeja.** Una aplicación con menú (Cargar export, Cargas, Atrasados), una lista de pendientes y, al lado, el detalle del que elegiste, con los pasos para resolverlo y un «Ya lo corregí». Cuando se marcan los tres, el botón de volver a cargar pasa a ser el principal. Escala mejor y deja lugar para la vista de atrasados. Su costo: es la que más se parece a «un sistema» y la que más elementos muestra.
- **03 · El mapa.** Cada envío es un casillero. Los 20 que están bien quedan verdes y quietos; los 3 que necesitan algo resaltan. Los mismos casilleros aparecen al elegir el archivo (vacíos) y durante la carga (se van llenando), así que los tres momentos se ven como una sola cosa. Su costo: lo que salió bien queda a la vista (en silencio, pero visible), y con cientos de envíos el mapa necesita agruparse.

Las tres direcciones se revisaron contra criterios de escritura de interfaz, color, accesibilidad y tipografía, y contra una lista de señales de interfaz genérica, que sirvió para darle a cada una un carácter propio. Se aplicaron con criterio y no como receta: la ambición está en la precisión y en lo que se saca, sin métricas gigantes, sin etiquetas en mayúsculas arriba de los títulos, sin degradados ni vidrio. Cada problema dice qué falta, para quién y qué hacer; los botones arrancan con un verbo («Volver a cargar el export»); los «Ver detalle técnico» llevan el remito, para que se entiendan leídos solos (un lector de pantalla los lista sin contexto). Los colores están en OKLCH, con contraste medido: todo el texto por encima de 4,5:1 y los bordes de los casilleros pendientes por encima de 3:1. El estado nunca depende solo del color, siempre hay ícono y texto. Se puede usar con teclado, el foco se ve y se respeta «reducir movimiento».

### Por qué el mapa

Elegimos el mapa. Las razones:

- **Responde la pregunta de un vistazo.** Antes de leer una palabra ya se ve que casi todo está verde y que hay tres casilleros distintos. La frase de arriba lo confirma.
- **Hace visible lo que antes había que explicar.** Que el puente no duplica envíos se entiende solo: en la segunda corrida los mismos casilleros aparecen como «ya estaba». No hace falta saber qué es un 409.
- **Une los tres momentos.** Elegir el archivo, ver el avance y leer el resultado usan el mismo objeto. No hay que aprender tres pantallas.
- **Se entiende en una demo.** La pregunta de la entrevista fue cómo se lo venderíamos a un cliente. Ver los casilleros llenarse en vivo se entiende en diez segundos.
- **El arreglo sigue siendo texto.** La tabla de abajo dice qué falta, para quién, de qué cliente y en qué remito. El mapa orienta; las frases resuelven.

Lo que hay que cuidar:

- **Volumen.** Con los 23 envíos de hoy funciona. Si un día son cientos, los verdes se agrupan en un solo bloque («240 cargados») y solo se muestran sueltos los que necesitan algo.
- **Pantallas chicas.** En el celular, lo que hay que corregir va antes que el mapa.
- **Lo que salió bien queda a la vista.** Es el único punto donde el mapa se aparta del principio «resumido y plegado». Se compensa con verdes suaves y sin texto extra; si molesta en el uso real, el mapa se puede plegar.

### Movimiento

Las animaciones tienen que ser sutiles y dar sensación de cuidado y de fluidez. Para decidirlas seguimos el método de Emil Kowalski: primero sacar lo que no hace falta, después mejorar lo que queda, revisar el rendimiento y recién entonces agregar. El criterio: el movimiento explica algo, no decora.

- **La carga en vivo es el momento principal.** Cada casillero se completa cuando Expreso Andino confirma el envío. Ahí el movimiento es información: muestra el avance.
- **Al abrir el resultado no se mueve nada.** Quien entra a ver qué tiene que hacer no tiene que esperar una coreografía.
- **Todo lo demás responde a la persona.** Elegir un casillero, abrir un detalle o apretar un botón tiene una respuesta corta (menos de 300 ms) que confirma que algo pasó.
- **Nada en loop y nada que distraiga.** Quien tiene activado «reducir movimiento» en su sistema ve los mismos cambios de estado, sin desplazamientos.

### Primera ronda de pulido: que deje de parecer una plantilla

Con el mapa elegido hicimos una ronda de pulido, de movimiento y visual, con criterio propio para salir de lo genérico. Las decisiones con sus valores están en `design/resultado-corrida/polish-notes.md`.

El diagnóstico: **la estructura era propia, la piel era intercambiable**. Si se cambiaba «Expreso Andino» por otro nombre, la pantalla servía igual para cualquier producto. Lo que la hacía genérica era la fuente del sistema, las cajas redondeadas con sombra (y cajas dentro de cajas), un trío de colores pastel de catálogo, una palabra del título pintada de naranja y una etiqueta chica arriba de los títulos. Lo que la hacía propia, y se conserva, es el casillero por remito, la respuesta como frase, el ámbar en lugar del rojo y los textos con nombres reales.

Para darle identidad buscamos un mundo concreto: **el talonario de remitos**. Original, duplicado y triplicado en papel carbónico, tinta de sello, resaltador. De ahí salen las decisiones:

- **Una sola mancha de color, y es lo que requiere acción.** Los 20 envíos que están bien bajan a un verde casi gris. «Ya estaba» deja de ser celeste y pasa a una trama de carbónico. Los 3 pendientes van en amarillo de resaltador, y el «3 de 23 envíos» del título queda subrayado como con un resaltador, en vez de pintado.
- **El azul de tinta de sello** une el botón principal, la selección y el foco.
- **Radios más chicos (2, 4, 6 y 10 px).** Un remito, una etiqueta o un casillero de depósito tienen esquinas casi vivas. Los radios grandes eran parte del aspecto de plantilla.
- **Menos cajas.** El mapa va directo sobre la página; la única hoja elevada es la de «Para corregir en LogiSur», porque lo que hay que hacer es papel.
- **Movimiento.** Se sacó un hover casi imperceptible. Las curvas pasaron a una ease-out más decidida y la carga en vivo dura 2 segundos en vez de 3. Las filas a corregir aparecen en el momento en que su casillero se resuelve, así se ve la causa y el efecto. Al terminar, los 3 casilleros ámbar hacen un único pulso que los ata a la frase del título.
- **Tipografía.** Primero se eligió Atkinson Hyperlegible Next, diseñada por el Braille Institute para que ningún carácter se confunda con otro (0 y O, 1, l e I), que es el riesgo al leer «R-10000477» o «AND4BD591C». Su cero lleva una barra y no hay una versión sin barra. Se aceptó a conciencia, con Public Sans como plan B; la segunda pasada la reemplazó (ver abajo).

Cuando los criterios se contradecían (pasa entre las guías de interfaz, de diseño y de señales genéricas en sombras, radios, curvas y tipografía), decidió lo que dejaba más clara la pantalla para operaciones y, ante la duda, el pedido explícito. La tabla de conflictos y cómo se resolvió cada uno está en `polish-notes.md`.

### Segunda pasada: mirar con ojo crítico

Revisamos el resultado como lo haría alguien escéptico, y salieron cinco ajustes:

- **El amarillo gritaba.** Relleno saturado, borde y negrita decían lo mismo tres veces, y los tres casilleros competían con la frase del título. El relleno pasó a un amarillo lavado; el borde y la negrita siguen marcando. El resaltador fuerte quedó solo para el «3 de 23 envíos» del título.
- **Una idea, una vez.** «Volvé a cargar el export» aparecía dos veces. Quedó solo en la hoja de arreglos, que es donde se actúa: «Cuando los corrijas, volvé a cargar el export. No se duplica nada.»
- **«Elegí», no «Tocá».** Se usa en una computadora.
- **Sin hueco durante la carga en vivo.** La leyenda sube debajo del contador mientras corre y vuelve a su lugar al terminar.
- **La tipografía se elige mirando.** El cero con barra de Atkinson ayuda en los códigos, pero en «10:47» o en una fecha la pantalla parece una terminal. En vez de decidirlo razonando, armamos el mismo mapa en Public Sans (la tipografía del gobierno de EE. UU., licencia abierta) para compararlas lado a lado. Elegimos Public Sans: horas, fechas y cantidades se leen como texto común, y los códigos siguen siendo claros.

### Estados y verificación

Hasta acá habíamos diseñado un solo día: el lunes, con 3 envíos para corregir. Una pantalla de resultados tiene que aguantar todos los días, así que armamos `04-estados.html` como una semana con el panel:

- **Martes, segunda carga.** No hay nada nuevo: los 20 ya estaban y siguen los mismos 3 para corregir. La frase lo dice sin alarma: «No se cargó nada dos veces.» Es la prueba visible de que el puente no duplica.
- **Miércoles, LogiSur corrigió los 3.** «No tenés que hacer nada.» No hay hoja ni botón: la calma sale de la frase y de que no hay nada que llame la atención.
- **Jueves, Expreso Andino no respondió para 2 envíos.** Aparece «Sin respuesta», con su propio ícono (una nube cortada) y borde gris tinta, no ámbar, porque no es un problema de LogiSur. En la hoja va en un grupo aparte, con otra indicación: volver a cargar en unos minutos.
- **Viernes, no se pudo correr.** No hay resultado que mostrar, así que en el lugar del mapa van los 23 casilleros vacíos: se ve que no se tocó nada. Al lado, el caso del archivo que no se puede leer.

La semana también sirve para mostrar el producto: en un minuto se ve qué ve operaciones cada día, incluso cuando algo falla.

En paralelo cerramos los cabos sueltos de verificación del mapa:

- **Celular, tablet y zoom al 200%.** Funciona en una columna. Se arregló el encabezado, que en pantallas chicas partía el nombre del archivo.
- **Pulso final.** Era demasiado tenue y se reforzó sin cambiar su duración.
- **Firefox.** Anda bien. Se corrigió una línea finita que se dibujaba en el borde de los casilleros.
- **Safari (WebKit).** No se pudo probar en esta máquina, porque le faltan librerías del sistema.
- **Modo de colores forzados.** Lo usan personas con baja visión. Ahora cada estado se distingue por el ícono y por el tipo y grosor del borde.
- **Teclado.** Se puede recorrer toda la pantalla y el foco siempre se ve.

Al ver los 20 «Ya estaba» juntos, la trama de carbónico ensuciaba justo el día en que no había que hacer nada. Se aclaró un poco: el ícono sigue diciendo el estado.

## 6. De códigos a frases

El puente clasifica cada remito en exactamente uno de cinco resultados. Cada uno pasa a ser una frase. Un caso fino: un `503` seguido de un `409` en el reintento. Para la máquina son dos eventos; para operaciones es uno solo: «Cargado». La interfaz no cuenta el ruido interno.

Las frases salen de recorrer todos los mensajes que el puente puede producir (rechazos locales, las reglas de la API que dan `422`, las fallas después de reintentar y los errores que impiden correr) y de revisarlos con criterios de escritura de interfaz: cada frase dice qué pasó y qué hacer, en palabras que se entienden cansado y a la primera, sin culpa, sin «ups» y sin signos de exclamación. El texto original del puente nunca se borra: queda en «Ver detalle técnico».

**Vocabulario fijo** (una cosa, un nombre): *envío* para lo que viaja, *remito* para el papel de LogiSur y su número, *export* para el archivo del día, *cargar* para mandarlo a Expreso Andino, *LogiSur* para donde se corrige y *sistemas* para a quién avisar. Voseo, oraciones completas con punto, botones que empiezan con un verbo.

**Estados de un envío.** Son los casilleros del mapa y la leyenda:

| Resultado del puente | Etiqueta | Frase al elegir el casillero | Qué tiene que hacer la persona |
| --- | --- | --- | --- |
| Cargado (`201`) | Cargado | «Cargado. Seguimiento ANDC4BD591C.» | Nada |
| Cargado después de reintentar (`5xx` y después `409`) | Cargado | La misma que Cargado. «Confirmado en el intento 2» queda solo en el detalle técnico | Nada |
| Ya existía (`409` al primer intento) | Ya estaba | «Ya estaba cargado de antes. No se duplicó.» | Nada |
| Duplicado en el export | No tiene casillero propio: es el mismo envío | En el casillero del primero: «Venía dos veces en el archivo. Se cargó una sola vez.» Si ese día ya estaba cargado de antes: «Ya estaba cargado de antes. No se duplicó. Venía dos veces en el archivo.» | Nada |
| Rechazado (dato que no se puede traducir, o `422`) | **Para corregir** | Una frase por problema (tabla siguiente) | Corregir en LogiSur y volver a cargar el export |
| Falló (`500`-`504` o sin conexión, después de 4 intentos) | **Sin respuesta** | «Expreso Andino no respondió. No se perdió nada: volvé a cargar el export en unos minutos.» | Volver a cargar más tarde |
| Falló (cualquier otra respuesta, por ejemplo `400` o `404`) | **Sin respuesta** | «Expreso Andino respondió algo inesperado. Volvé a cargar el export más tarde; si sigue igual, avisale a sistemas con el número de remito.» | Volver a cargar; si se repite, avisar |

La etiqueta «Para corregir» reemplazó a «Falta un dato» porque no todos los rechazos son datos que faltan: unos bultos en 0 o una provincia mal escrita están, pero mal. «Para corregir» nombra lo que hay que hacer y sirve para todos.

**Frases por problema en un envío para corregir.** Título en negrita, y debajo una pista que dice cómo dejarlo bien. Si el remito trae una observación, se agrega: «El remito dice «…».» Si hay más de un problema en el mismo remito, se listan todos.

| Mensaje del puente (texto real) | Título | Pista |
| --- | --- | --- |
| `destinatario.razon_social: required non-empty string` | Falta el nombre del destinatario | Completalo en el remito. |
| `destinatario.direccion: required non-empty string` | Falta la dirección | En el remito quedó en blanco. |
| `destinatario.localidad: required non-empty string` | Falta la localidad | Completala en el remito. |
| `destinatario.provincia: required non-empty string` | Falta la provincia | Completala en el remito. |
| `destinatario.codigo_postal: required non-empty string` | Falta el código postal | Completalo en el remito. (Con observación: «El remito dice «Cliente no informó CP»: hay que pedírselo al cliente.») |
| `provincia desconocida: '{valor}'` o `destinatario.provincia: unknown province, see GET /v1/provinces` | La provincia «{valor}» no se reconoce | Escribila completa, por ejemplo «Buenos Aires» o «Córdoba». |
| `bultos: integer >= 1` | Los bultos figuran en {n} | Tiene que haber al menos 1 bulto. |
| `peso inválido: '{valor}'` | El peso «{valor}» no se puede leer | Escribilo como número, por ejemplo 29,5. Sin separador de miles. |
| `peso_kg: number > 0` | El peso figura en {n} | Tiene que ser mayor que 0. |
| `servicio desconocido: '{valor}'` o `servicio: one of: standard, express` | El servicio «{valor}» no existe | Tiene que ser Normal o Urgente. |
| `valor_declarado: number >= 0` | El valor declarado es negativo | Tiene que ser 0 o más. |
| `nro_remito: required string` | El remito no tiene número | Revisalo en LogiSur antes de volver a cargar. |
| `la API rechazó los datos sin detalle`, o cualquier mensaje que no esté en esta tabla | Expreso Andino rechazó este envío sin explicar por qué | Avisale a sistemas con el número de remito. |

**La frase de arriba (la respuesta a «¿Tengo que hacer algo?»).** Depende de la mezcla de resultados. Las cantidades se arman con reglas de plural (`Intl.PluralRules`), nunca pegando una «s»:

| Situación | Frase grande | Debajo | Botón |
| --- | --- | --- | --- |
| Hay envíos para corregir | «3 de 23 envíos esperan un dato de LogiSur.» | «Los otros 20 ya están en Expreso Andino. No hace falta hacer nada con ellos.» | Ver qué falta |
| Hay para corregir y sin respuesta | «5 de 23 envíos no se cargaron.» | «3 esperan un dato de LogiSur y 2 no tuvieron respuesta de Expreso Andino. Los otros 18 ya están cargados.» | Ver qué pasó |
| Solo sin respuesta | «2 de 23 envíos no se cargaron.» | «Expreso Andino no respondió. No se perdió nada: volvé a cargar el export en unos minutos.» | Volver a cargar el export |
| Todo bien, primera carga | «No tenés que hacer nada.» | «Los 23 envíos ya están en Expreso Andino.» | Ninguno |
| Segunda carga, nada nuevo, quedan para corregir | «3 de 23 envíos esperan un dato de LogiSur.» | «Los otros 20 ya estaban en Expreso Andino desde una carga anterior. No se cargó nada dos veces.» | Ver qué falta |
| Segunda carga, todo bien | «No tenés que hacer nada.» | «Los 23 envíos ya estaban en Expreso Andino. No se cargó nada dos veces.» | Ninguno |

**Cuando no se pudo correr.** No hay mapa que mostrar, así que la pantalla dice qué pasó, qué se tocó (nada) y a quién avisar:

| Error del puente (texto real) | Frase grande | Debajo | Botón |
| --- | --- | --- | --- |
| `No se pudo leer el export {archivo}: {error}` | «No se pudo leer el archivo.» | ««{archivo}» no parece un export de LogiSur o está dañado. Descargalo de nuevo desde LogiSur y volvé a elegirlo. No se cargó ningún envío.» | Elegir otro archivo |
| `Falta la variable de entorno EXPRESO_API_KEY.` | «El panel no está conectado con Expreso Andino.» | «Falta configurar la clave de acceso. Avisale a sistemas. No se cargó ningún envío.» | Ninguno |
| `la API rechazó la API key (401)` al empezar | «Expreso Andino no aceptó la conexión.» | «La clave de acceso del panel no es válida. Avisale a sistemas. No se cargó ningún envío.» | Ninguno |
| `sin conexión con la API tras 4 intentos: …` o `GET /v1/provinces respondió 503` al empezar | «Expreso Andino no responde.» | «No se cargó ningún envío. Probá de nuevo en unos minutos; si sigue igual, avisale a sistemas.» | Volver a intentar |
| `401` a mitad de la carga | «La carga se cortó a mitad de camino.» | «Expreso Andino dejó de aceptar la conexión. Avisale a sistemas. Lo que se llegó a cargar no se va a duplicar cuando vuelvas a cargar el export.» | Ninguno |

**Antes y durante la carga.** «23 envíos para Expreso Andino» con «El archivo tiene 51 remitos. Los otros 27 van con otros transportistas y no se tocan.» y el botón «Cargar 23 envíos». Durante la carga: «Cargando 14 de 23…» y «Cada casillero se completa cuando Expreso Andino confirma el envío.»

**Atrasados** (la vista aparte). El estado de la API pasa a palabras: `CREATED` → «Todavía no salió», `IN_TRANSIT` → «En viaje», `EXCEPTION` → «Con un problema en el viaje». Cada fila dice cuánto se atrasó: «Atrasado 1 día: tenía que llegar el 2 de octubre.» Título: «2 envíos atrasados al 3 de octubre»; sin atrasados: «Ningún envío atrasado al 3 de octubre.» La fecha va en palabras porque el campo de fecha del navegador muestra 10/03/2026 y se puede leer como 10 de marzo.

**Huecos del puente que aparecieron al recorrer los mensajes.** El panel no cambia la lógica, pero tiene que cubrirlos al envolver la llamada:

- Un archivo que es JSON pero no es una lista de remitos, o un remito sin `nro_remito`, rompe la corrida sin un mensaje claro (sale un error de Python). El panel lo atrapa y muestra «No se pudo leer el archivo.»
- Un `401` a mitad de la carga corta todo y no deja resumen, así que el panel no sabe qué se llegó a cargar. Por eso la frase no da cantidades.
- «Sin conexión» y «respuesta inesperada» traen texto crudo de Python (`[Errno 111] Connection refused`, un diccionario impreso). Va solo al detalle técnico.

## 7. Cómo está construido

La explicación completa, con las etapas, los módulos y el contrato de la API, está en [`como-se-construyo.md`](como-se-construyo.md). Acá va lo que importa para entender las decisiones.

La regla era no tocar la lógica del puente. Había dos formas de respetarla:

- **Correr el puente como lo corre una persona** (la línea de comandos) y leer el resumen en Markdown que deja. Es lo más desacoplado, pero el panel tendría que interpretar texto pensado para leer, y se perdería el resultado de cada remito tal como lo arma el puente.
- **Usar el puente como una librería**: llamar a sus funciones públicas desde el panel, en el mismo proceso. El panel recibe cada resultado como dato (remito, resultado, seguimiento, detalle) y no tiene que adivinar nada.

Elegimos la segunda, con tres cuidados:

1. **El puente entra como submódulo de git, fijado en una versión exacta** (5147381, la que se entregó). El panel no copia ni modifica su código: si el puente cambia, el panel sigue usando esa versión hasta que alguien decida actualizarla.
2. **Solo se usan funciones públicas.** Las reglas de negocio (qué es de Expreso Andino, los duplicados, los reintentos, la validación) siguen viviendo en un solo lugar.
3. **El avance en vivo sale de lo que el puente ya cuenta.** Por cada remito, el puente escribe una línea en su registro. El panel la escucha mientras dura la carga y con eso va llenando los casilleros. No hizo falta agregarle nada al puente.

Lo que el panel sí agrega es lo que el puente no tenía por qué saber: el cliente de cada remito (lo lee del export), las frases para operaciones y los avisos claros para los huecos que encontramos.

Es un servidor Python que usa solo la biblioteca estándar y una página sin frameworks: nada que instalar y todo explicable de punta a punta. Tiene 187 tests, todos contra la API del kit, igual que los del puente. Se probó de punta a punta: primera carga (19 cargados, 1 ya estaba, 3 para corregir), segunda carga (20 ya estaban, nada duplicado), atrasados al 3 de octubre (Kiosco El Sol y Veterinaria Patitas, «Atrasado 1 día») y Expreso Andino caído («Expreso Andino no responde.», sin tocar ningún envío).

Cosas que aparecieron en el camino y vale la pena contar:

- **El puente avisaba en voz baja.** Escribe una línea por remito, pero con un nivel que Python no muestra por defecto. Sin ajustar eso, el panel nunca se enteraba del avance. Se resolvió del lado del panel, mientras dura la carga, sin tocar el puente.
- **Una cuenta mal hecha que nadie habría notado.** La vista previa decía «los otros 28 van con otros transportistas», pero eran 27: restaba envíos en vez de remitos (uno viene repetido). Lo agarró la revisión, con un test que primero falló.
- **El resumen técnico tenía que seguir sirviendo.** Al principio el resumen que deja el puente nombraba el archivo con un código interno. Ahora conserva el nombre real del export, así soporte puede ubicarlo.
- **«Sanitarios Rivera, , Caballito».** Un remito sin calle dejaba una coma colgando. Ahora se arma solo con lo que hay: «Caballito, Capital Federal».
- **Los botones ya no dependen de su texto.** La página decidía qué hacía cada botón leyendo lo que decía; si alguien cambiaba «Ver qué falta» se rompía sin avisar. Ahora el servidor manda la acción explícita.
- **El puente no trae el valor del error.** Dice `bultos: integer >= 1`, no `bultos: 0`. Para poder decir «Los bultos figuran en 0», el panel lo lee del export.

Lo que no se pudo verificar: Safari, porque WebKit no corre en esta máquina, y la reconexión de la página si se corta la red a mitad de una carga.

## 8. Abrirlo con doble clic

**Por qué existe.** El panel nació para que operaciones no tenga que abrir una terminal ni escribir comandos de Python. Con el panel terminado, seguía faltando lo primero: para abrirlo había que levantar un servidor desde la terminal. Eso dejaba la barrera en la puerta de entrada.

**Cómo funciona.** El repo trae `Abrir panel.bat` (Windows) y `Abrir panel.sh` (Linux), que corren `python3 -m panel.launcher`. Con doble clic se abre una ventana con el estado y el panel en el navegador; al cerrar la ventana se apaga todo. Usa el puerto 8080 o, si está ocupado, uno libre.

**Dos modos con el mismo doble clic.** Sirve tanto para operar como para mostrarlo, y lo que cambia es un archivo:

- **Con `expreso.ini`** (junto al README, fuera de git) el panel usa la API real de Expreso Andino, con la dirección y la clave que el archivo indica. Hay un ejemplo en `expreso.ini.ejemplo`.
- **Sin `expreso.ini`** el panel abre en modo prueba: levanta la API de prueba del kit en el mismo proceso y usa su clave de prueba, que es pública. La cabecera muestra el sello «Modo prueba» y la aclaración «Los envíos no llegan a Expreso Andino.», para no confundir una demostración con una carga real.

**Qué pasa cuando algo falla.** Los errores se dicen en una oración y la ventana espera un Enter para que se alcance a leer: falta Python (en Windows), falta el puente (la descarga en ZIP de GitHub no trae el submódulo), `expreso.ini` está incompleto o mal escrito. Una dirección `http://` que no sea de la misma computadora se rechaza, porque la clave viajaría sin cifrar.

**Cómo se verificó.** En Linux, la primera versión era un archivo `.desktop`. Se probó con `gio launch`, que lo abrió bien, pero al usarlo desde el gestor de archivos de GNOME no pasaba nada: ese gestor ya no abre archivos `.desktop`, y «Ejecutar como un programa» lo corre como un script de shell, que falla sin mostrar nada. Se reemplazó por `Abrir panel.sh`: un script que, si lo arranca el gestor de archivos (sin ventana), se vuelve a abrir solo dentro de una terminal. Así quedan a la vista la dirección del panel y los errores, y cerrar esa ventana lo apaga. Se probó arrancándolo sin terminal, como lo hace el gestor de archivos: abrió la terminal y el panel, cargó el export del kit (19 cargados, 1 ya estaba, 3 para corregir) y al cerrar la ventana se apagó todo. Los tests reemplazan la terminal y Python por versiones falsas para comprobar cada camino: con terminal, sin terminal y sin Python. Windows queda sin probar en un equipo real. Una revisión independiente del lanzador no encontró problemas críticos ni altos y marcó dos medios, ambos de Windows; se corrigieron junto con otros dos detalles:

- El Bloc de notas puede guardar `expreso.ini` como «UTF-8 con BOM», y eso hacía que el archivo no se leyera. Ahora se acepta.
- En Windows, la opción de reutilizar la dirección permite que un segundo panel use un puerto que ya está en uso. Se desactivó ahí, para que el lanzador pase a un puerto libre.
- Las direcciones `http://` remotas, como se dijo, se rechazan.
- Un error inesperado ya no muestra el seguimiento de Python: dice qué falló y deja la ventana abierta.

## 9. Revisiones independientes y qué cambiaron

El panel se revisó dos veces antes de darlo por terminado, y el lanzador una vez más (sección anterior). En los tres casos la revisión la hizo alguien que no escribió el código; en la primera, además, sin permiso para modificarlo. Todo lo que se encontró se corrigió con un test que primero falló.

### Revisión del servidor

Es la parte que recibe archivos de afuera y habla con Expreso Andino, así que un error ahí es caro. Se intentó romperlo con pedidos reales: leer archivos fuera de sus carpetas, encontrar la clave de acceso en alguna respuesta, meter código en la página con un export malicioso, mandar archivos gigantes o mal formados, lanzar treinta cargas a la vez. Nada de eso funcionó.

Encontró dos cosas medias y tres chicas:

- **Un mensaje que mentía.** Si el export traía un dato con un tipo raro (un número donde va un nombre), el puente se rompía a mitad de la carga y la pantalla decía «No se cargó ningún envío.» cuando ya se habían cargado 19. Ahora esos exports se rechazan antes de empezar, y si algo inesperado corta una carga, la frase dice la verdad: «La carga se cortó a mitad de camino» y que lo cargado no se va a duplicar.
- **Pedidos desde otros sitios.** Una página web maliciosa podía, con una técnica conocida, usar el panel para cargar envíos con la clave de LogiSur. Ahora el panel solo atiende pedidos hechos desde sí mismo.
- **Detalles chicos:** un archivo de más de 20 MB ya no dice que está «dañado» sino que es «demasiado grande», los exports mal formados ya no dejan carpetas sueltas, y un pedido incompleto ya no deja al servidor esperando para siempre.

Después se volvió a correr cada prueba del revisor contra el panel real: todas quedaron cerradas.

### Prueba final de punta a punta

Para cerrar, otra persona usó el panel como lo usaría operaciones, siguiendo el README al pie de la letra: primera carga, segunda carga, atrasados y Expreso Andino caído, en Chromium y Firefox, en pantalla grande y en celular. Los cuatro pasos dieron bien y los números coincidieron con los resúmenes que escribe el propio puente. En la revisión de UX dio 30 sobre 40 en las heurísticas de Nielsen, sin problemas graves, con el veredicto de que el diseño es «de autor, no una plantilla». Todas las frases que vio coincidían palabra por palabra con la tabla de la sección 6.

Lo que encontró y se corrigió:

- **Volver atrás perdía la respuesta.** En el celular «atrás» es un reflejo, y sacaba del panel. Ahora vuelve al resultado, y recargar la página también lo conserva, incluso a mitad de una carga.
- **En el celular, lo que había que corregir quedaba a más de dos pantallas**, debajo de los 23 casilleros. Ahora va antes del mapa, como habíamos decidido al elegirlo. En pantalla grande se ve igual que el diseño aprobado; quien navega con teclado llega primero a los arreglos y después al mapa, a propósito.
- **Detalles:**
  - el reintento de Pinturerías del Oeste se puede ver en «Ver detalle técnico»;
  - la leyenda usa las mismas palabras que los casilleros;
  - la fecha de atrasados se repite en palabras para que nadie lea 10 de marzo;
  - los enlaces chicos son más fáciles de tocar;
  - si el puerto está ocupado, el panel lo explica en una oración en vez de mostrar un error de Python.

Lo único que no se pudo probar fue Safari, porque WebKit no corre en esta máquina.

## 10. Registro de decisiones

| Fecha | Decisión | Por qué | Descartado |
| --- | --- | --- | --- |
| 2026-11-03 | Repo nuevo (`expreso-panel`) en lugar de sumar la UI al repo del challenge | El repo del challenge queda como se entregó y se defendió; el panel es una iteración posterior, a partir del feedback de la entrevista | Modificar `caso-expreso` |
| 2026-11-03 | El panel no cambia la lógica del puente | La lógica ya está testeada; el problema es de comunicación, no de reglas | Reescribir el puente |
| 2026-11-03 | Diseñar para la persona de operaciones de LogiSur | Una persona concreta define qué es «lo justo y necesario» | Diseñar para «no técnicos» en general |
| 2026-11-03 | Tres direcciones visuales antes de implementar | Elegir viendo, no imaginando | Ir directo al código |
| 2026-11-03 | Contar envíos (23), no filas del resumen (24) | R-10000507 viene dos veces en el export pero es un solo envío. Para operaciones son 3 para corregir y 20 en orden; la repetición se aclara aparte | Mostrar «21 sin acción pendiente» como el resumen técnico |
| 2026-11-03 | Mostrar el cliente de LogiSur además del destinatario | El resultado del puente trae el destinatario; el cliente (a quien hay que llamar) sale del export. El panel puede leerlo sin tocar la lógica | Mostrar solo el destinatario, como el resumen técnico |
| 2026-11-03 | Usar la observación del remito en la frase | «Cliente no informó CP» dice a quién pedirle el dato; ninguna frase genérica dice tanto | Frase genérica por campo |
| 2026-11-03 | El reintento no se cuenta en la vista principal | Pinturerías del Oeste quedó cargado; «confirmado en el intento 2» es ruido interno y queda en el detalle técnico | Avisar del error de la API |
| 2026-11-03 | Rechazado se marca en ámbar, nunca en rojo | El envío no se perdió y nadie hizo algo mal: hay algo para corregir, no un error grave | Rojo de error |
| 2026-11-03 | Detalle técnico detrás de «Ver detalle técnico de R-…» | Sistemas o soporte lo necesitan (HTTP 422, campo de la API, archivo del resumen, código de salida); operaciones no. El remito en el texto hace que el enlace se entienda solo | Borrarlo, o mostrarlo siempre |
| 2026-11-03 | Textos en español con voseo, sin modismos | Así le habla el software argentino a sus usuarios (argentina.gob.ar también). Una sola forma en todo el flujo. Se puede cambiar si el cliente prefiere otra | «Usted» o tuteo |
| 2026-11-03 | Sin tipografías externas: fuentes del sistema | Las páginas tienen que funcionar sin internet y cargar al instante; la personalidad la dan el tamaño, el espacio y las palabras | Fuentes web |
| 2026-11-03 | Las tres direcciones comparten contenido y orden, y cambian la forma de leer | Así la elección es sobre la experiencia (nota, bandeja de trabajo, mapa) y no sobre el texto | Variar solo colores |
| 2026-11-03 | Dirección elegida: 03 · El mapa | Responde de un vistazo, hace visible que no se duplica nada, une los tres momentos en un solo objeto y se entiende en una demo. Las frases siguen resolviendo el arreglo | 01 · La nota (no escala), 02 · La bandeja (demasiado «sistema» para la tarea) |
| 2026-11-03 | Animaciones solo con propósito: la carga en vivo, y respuestas cortas a lo que hace la persona | El movimiento tiene que explicar (avance, selección) y dar sensación de cuidado sin hacer esperar. Nada al abrir el resultado y nada en loop | Animación de entrada en cada visita, efectos decorativos |
| 2026-11-03 | Mundo visual «Remito»: talonario con carbónico, tinta de sello, resaltador | Darle a la pantalla una identidad que venga del oficio de quien la usa, y no de una plantilla | Paleta y estilo genéricos de SaaS |
| 2026-11-03 | Tipografía Atkinson Hyperlegible Next, incrustada en la página (reemplaza la decisión de usar fuentes del sistema) | Está hecha para no confundir caracteres parecidos, que es el riesgo con códigos de remito y de seguimiento; no está gastada; al ir incrustada sigue funcionando sin internet | Fuente del sistema (genérica), Inter, DM Sans, Geist, IBM Plex y otras muy usadas |
| 2026-11-03 | Una sola mancha de color: amarillo resaltador para lo que requiere acción; verde casi gris para lo que salió bien; trama para «ya estaba» | Lo que no requiere acción no tiene que competir con lo que sí | Verde menta, celeste y ámbar con el mismo peso |
| 2026-11-03 | Radios de 2, 4, 6 y 10 px | Esquinas de papel y de etiqueta; los radios grandes eran parte del aspecto genérico | Radios de 10 a 20 px |
| 2026-11-03 | Menos cajas: mapa sobre la página, una sola hoja elevada para lo que hay que corregir, sin etiquetas arriba de los títulos | Cajas dentro de cajas agregan ruido y no agrupan nada que el espacio no agrupe | Tarjeta para cada bloque |
| 2026-11-03 | Movimiento ajustado con el método de Emil Kowalski: sacar el hover de brillo, curva ease-out más marcada, carga en vivo de ~2 s, filas que aparecen cuando su casillero se resuelve, un solo pulso final en los pendientes | Cada movimiento explica algo (avance, causa y efecto); lo imperceptible se saca | Mantener la versión anterior sin auditar |
| 2026-11-03 | Relleno amarillo lavado en los pendientes; resaltador fuerte solo en el título | Tres señales iguales hacían que los casilleros le ganaran a la frase, que es la respuesta | Amarillo saturado en todo |
| 2026-11-03 | Cada indicación aparece una sola vez, donde se actúa | Repetir la misma frase cansa y le resta peso | Repetir «volvé a cargar el export» junto a cada botón |
| 2026-11-03 | Comparar Atkinson Hyperlegible Next y Public Sans antes de elegir | El cero con barra ayuda en códigos pero endurece horas y fechas; la elección es visual | Decidir la fuente sin verla |
| 2026-11-03 | Tipografía final: Public Sans (reemplaza a Atkinson Hyperlegible Next) | Vistas lado a lado, las horas, fechas y cantidades se leen como texto común; los códigos siguen siendo claros y la personalidad la ponen el casillero, el resaltador y la trama | Atkinson Hyperlegible Next (cero con barra) |
| 2026-11-03 | Frases finales: una por resultado, por problema y por estado de la carga, con el texto original siempre en el detalle técnico | Recorrimos todos los mensajes que puede producir el puente; ninguno llega a operaciones sin traducir | Mostrar el mensaje de la API, aunque sea con una explicación al lado |
| 2026-11-03 | «Para corregir» en lugar de «Falta un dato» | No todos los rechazos son datos que faltan (bultos en 0, provincia mal escrita); la etiqueta nombra lo que hay que hacer | «Falta un dato», «Rechazado» |
| 2026-11-03 | «Sin respuesta» como estado propio, separado de «Para corregir» | Si Expreso Andino no responde, no es un problema de LogiSur y la acción es otra (volver a cargar más tarde) | Mezclarlo con los rechazos |
| 2026-11-03 | Cuando toda la carga está bien, la respuesta es «No tenés que hacer nada.» | Responde literalmente la pregunta que guía todo el panel | «Carga exitosa», «Todo OK» |
| 2026-11-03 | Diseñar los estados como «una semana con el panel» (`04-estados.html`) | Una pantalla de resultados tiene que aguantar todos los días: segunda carga, día sin pendientes, falla de la API, carga que no arranca. Además cuenta el producto en un minuto | Diseñar solo el caso con pendientes |
| 2026-11-03 | Si no se pudo correr, mostrar los casilleros vacíos del export en lugar del mapa | Deja claro que no se tocó ningún envío | Una pantalla de error genérica |
| 2026-11-03 | Trama de «Ya estaba» más suave | Con 20 casilleros juntos ensuciaba el día tranquilo; el ícono ya lleva el estado | Mantener la trama original |
| 2026-11-03 | El panel usa el puente como librería, en el mismo proceso, fijado como submódulo de git en 5147381 | Recibe cada resultado como dato sin interpretar texto; la lógica sigue en un solo lugar y en una versión exacta | Correr la línea de comandos y leer el Markdown; copiar el código del puente |
| 2026-11-03 | El avance en vivo sale de la línea de registro que el puente ya escribe por cada remito | Permite llenar los casilleros a medida que llegan sin cambiar el puente | Modificar el puente para que avise el avance |
| 2026-11-03 | Solo biblioteca estándar de Python y una página sin frameworks | Igual que el puente: nada que instalar y todo explicable de punta a punta | Flask, React u otros frameworks |
| 2026-11-03 | Cada acción de la pantalla viaja como dato (`action`), no se deduce del texto del botón | Las frases se pueden ajustar sin romper el comportamiento | Elegir la acción por el texto |
| 2026-11-03 | El panel lee del export los valores que el puente no informa (bultos, peso, servicio, provincia) | Para decir «Los bultos figuran en 0» en vez de un genérico «no son válidos» | Frases sin el valor |
| 2026-11-03 | La vista de atrasados vive en la misma página, con una fecha y una lista simple | Es una consulta ocasional; no merece otra aplicación ni un menú | Una sección o pantalla aparte |
| 2026-11-03 | Revisión independiente del servidor antes de dar el panel por terminado, y corrección de todo lo que encontró | Es la parte que recibe archivos de afuera y habla con Expreso Andino; un error ahí es caro | Darlo por bueno con los tests propios |
| 2026-11-03 | Validar los tipos del export antes de cargar | Un dato con tipo raro rompía el puente a mitad de camino; es mejor rechazarlo entero que cargar a medias | Dejar que el puente falle y explicar después |
| 2026-11-03 | En el celular, los arreglos van antes del mapa; en pantalla grande el orden de teclado también pone primero los arreglos | Lo accionable no puede quedar a dos pantallas; el mapa es la vista general | Mantener el mapa primero en todos los tamaños |
| 2026-11-03 | Volver atrás y recargar conservan el resultado | La respuesta a «¿Tengo que hacer algo?» no se puede perder por un gesto reflejo | Una página que olvida todo al recargar |
| 2026-11-03 | Abrir el panel con doble clic (`Abrir panel.bat` en Windows, `Abrir panel.sh` en Linux) | Quien opera no debería abrir una terminal ni escribir comandos de Python; el doble clic abre el navegador y cerrar la ventana apaga todo | Instrucciones de terminal en el README como único camino |
| 2026-11-03 | Con `expreso.ini` el panel usa la API real; sin él, abre en modo prueba contra la API del kit y lo dice en la cabecera | El mismo doble clic sirve para operar y para mostrarlo; la clave real queda en un archivo local fuera de git, y el sello «Modo prueba» evita confundir una prueba con una carga real | Dos lanzadores distintos; pedir la clave en la página |
| 2026-11-03 | En Linux, un script (`Abrir panel.sh`) en lugar de un archivo `.desktop` | El gestor de archivos de GNOME no abre `.desktop`; un script ejecutable funciona con «Ejecutar como un programa» y con doble clic en KDE y Xfce, y se abre solo en una terminal | Mantener el `.desktop`, que solo sirve en algunos escritorios |
