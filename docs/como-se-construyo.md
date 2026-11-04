# Cómo se construyó el panel

El panel es una página web que le dice a una persona de operaciones de LogiSur, en frases, qué pasó al cargar el export diario de remitos en Expreso Andino y si tiene algo para hacer. Se apoya en el puente [`caso-expreso`](https://github.com/Mateocas1/caso-expreso) sin modificarlo.

Este documento es para quien revise el trabajo: cuenta en qué etapas se dividió, en qué se basó cada una y por qué, cómo se conecta con el puente, qué hace cada módulo, qué encontraron las revisiones independientes y cómo se corrigió, y el contrato de la API HTTP. El razonamiento de diseño, las frases y la tabla de decisiones están en [`bitacora.md`](bitacora.md).

## Contenido

1. [Las etapas](#las-etapas)
2. [Cómo usa el panel al puente](#cómo-usa-el-panel-al-puente)
3. [Los módulos](#los-módulos)
4. [Las revisiones independientes](#las-revisiones-independientes)
5. [Contrato de la API HTTP](#contrato-de-la-api-http)
6. [Tests y lo que no se verificó](#tests-y-lo-que-no-se-verificó)

## Las etapas

| # | Etapa | En qué se basó | Por qué |
| --- | --- | --- | --- |
| 1 | Tres direcciones visuales (`design/resultado-corrida/`): la nota, la bandeja, el mapa | Los datos reales del kit del challenge, con el mismo contenido y el mismo orden en las tres | Elegir viendo, no imaginando. Si solo cambian la forma de leer y no el texto, la elección es sobre la experiencia |
| 2 | Elección de «el mapa» (un casillero por envío) | La pregunta que guía todo: «¿tengo que hacer algo?» | Se responde de un vistazo, hace visible que no se duplica nada (en la segunda corrida los mismos casilleros pasan a «Ya estaba»), une los tres momentos en un objeto y se entiende en una demo corta |
| 3 | Rondas de pulido sobre el mapa: movimiento, paleta, radios, tipografía, menos cajas | Una auditoría de movimiento (quitar lo que no explica nada, mejorar lo que queda, cuidar el rendimiento) y una visual (accesibilidad, color, escritura, lo que hace que una interfaz parezca una plantilla) | Que el movimiento informe (avance de la carga, selección) y que la pantalla tenga identidad propia. Se compararon dos tipografías lado a lado y se eligió Public Sans |
| 4 | Tabla de códigos a frases | Todos los mensajes que puede producir el puente: un resultado por remito, un problema por campo rechazado, un estado por corrida | Ningún mensaje llega a operaciones sin traducir. El texto original queda siempre en «Ver detalle técnico» |
| 5 | Estados (`04-estados.html`) | «Una semana con el panel»: segunda corrida, día sin pendientes, envío que falló tras reintentar, carga que no se pudo hacer | Una pantalla de resultados tiene que servir todos los días, no solo el caso con pendientes |
| 6 | Implementación: adaptador, frases, servidor con eventos en vivo, página, vista de atrasados | Los diseños aprobados y la tabla de frases, con tests contra la API del kit | Una pieza chica por vez, cada una con sus tests, para poder revisar cada una por separado |
| 7 | Revisión independiente del servidor | Un revisor que no escribió el código y no podía modificarlo | El servidor recibe archivos de afuera y habla con Expreso Andino: un error ahí es caro |
| 8 | Prueba real y revisión de UX | El README seguido al pie de la letra, en Chromium y Firefox, en pantalla grande y en celular | Comprobar que lo que está escrito funciona y que una persona de operaciones lo entiende |
| 9 | Lanzador de doble clic y su verificación independiente | La necesidad de abrir el panel sin terminal | Quien opera no debería escribir comandos de Python |

Las decisiones de cada etapa, con fecha y alternativas descartadas, están en el registro de decisiones de la bitácora.

## Cómo usa el panel al puente

La regla fue no tocar la lógica del puente. Se evaluaron dos caminos: correr su línea de comandos y leer el resumen en Markdown, o usarlo como librería. Se eligió la librería porque el panel recibe cada resultado como dato (remito, resultado, seguimiento, detalle) y no tiene que interpretar texto pensado para leer.

- **El puente es un submódulo de git** en `vendor/caso-expreso`, fijado en `5147381`. No se edita nada ahí; si el puente cambia, el panel sigue usando esa versión hasta que alguien decida actualizarla.
- **Solo se importan funciones públicas, en el mismo proceso:** `remitos.load_remitos`, `remitos.is_andino`, `client.ExpresoClient`, `upload.upload_remitos`, `report.render_run_report` y `overdue.find_overdue`. No se llama a funciones privadas ni se repite ninguna regla del puente (deduplicado, clasificación, reintentos, validación).
- **El avance en vivo sale de la línea de log que el puente ya escribe por cada remito.** `upload_remitos` registra un evento INFO en el logger `expreso_bridge.upload` con `(número de remito, resultado, seguimiento, detalle)`. El panel engancha un `logging.Handler` a ese logger mientras dura la carga y reenvía cada evento al navegador. Hay una sola carga a la vez (un candado), de modo que los eventos de dos cargas nunca se mezclan.
- **Solo biblioteca estándar de Python (3.9 o superior) y una página sin frameworks**, igual que el puente: no hay nada que instalar y se puede explicar de punta a punta.

### Lo que el panel agrega

El puente no tenía por qué saber estas cosas, así que las resuelve el panel envolviendo la llamada:

- **El cliente de cada remito** y los valores que el puente no informa (bultos, peso, servicio, provincia): salen del export. El puente dice «bultos: integer >= 1», no «bultos: 0»; con el valor, la frase puede decir «Los bultos figuran en 0».
- **Los huecos del puente:** un JSON que no es una lista de remitos, un remito sin `nro_remito`, un JSON anidado de más, datos con tipos inesperados, una clave rechazada a mitad de la carga. El panel los convierte en un aviso claro (`CannotRun`) en vez de dejar que la carga se rompa.
- **Las frases para operaciones**, con el detalle técnico original intacto para soporte.

## Los módulos

```
panel/
  bridge.py     adaptador sobre el puente
  phrases.py    resultados del puente → frases
  server.py     servidor HTTP con eventos en vivo (SSE)
  launcher.py   lo que corre el doble clic
  static/       la página: index.html, app.css, app.js, public-sans.woff2
tests/          contra la API del kit, igual que los del puente
runs/           (no se versiona) exports subidos y resúmenes de cada corrida
```

**`panel/bridge.py`** es el único módulo que importa el puente (agrega `vendor/caso-expreso` al `sys.path` una vez, al importarse).

- `preview_export` lee el export, se queda con los remitos de Expreso Andino y arma la vista previa: un envío por remito distinto, los duplicados y cuántos remitos hay de otros transportistas. También rechaza lo que el puente no valida (tipos incorrectos, remito sin número, anidado excesivo) con un mensaje que nombra la posición del remito y el campo, y solo el nombre del archivo, nunca la ruta del servidor.
- `run_upload` hace la carga: llama a `upload_remitos`, escucha su línea de log y devuelve los resultados tal como los armó el puente más el resumen que deja `render_run_report`. Distingue una clave que falta, una clave rechazada antes o durante la carga y una API que no responde.
- `find_overdue_shipments` usa `find_overdue` del puente sobre los remitos del export y le suma destinatario, cliente y ciudad.

**`panel/phrases.py`** son funciones puras, sin entrada ni salida. Cada texto sale de la tabla de frases de la bitácora, con un test por fila.

- `tile_state` y `LABELS`: el estado de cada casillero («Cargado», «Ya estaba», «Para corregir», «Sin respuesta»).
- `problems`: separa el detalle del puente por campo y lo traduce a título y pista; un texto desconocido cae en una frase genérica que no inventa una causa.
- `run_answer`: la frase de arriba, con su sub-línea y la acción del botón.
- `cannot_run`: las frases de «no se pudo correr» según el motivo.
- Las de la vista de atrasados: estado en palabras, «Atrasado 1 día: tenía que llegar el 2 de octubre.» y la fecha escrita con el nombre del mes, porque `10/03/2026` se lee de dos maneras.

**`panel/server.py`** es el servidor HTTP, con `http.server` y sin dependencias. Guarda los exports subidos, ejecuta cada carga en un hilo, publica los eventos del puente como eventos en vivo y aplica las defensas descritas más abajo. La clave de la API nunca llega al navegador.

**`panel/launcher.py`** es lo que corren `Abrir panel.bat` (Windows) y `Abrir panel.sh` (Linux), sobre `python3 -m panel.launcher`.

- Si existe `expreso.ini` (local, fuera de git), usa la API real con su dirección y su clave. Si no existe, levanta en el mismo proceso la API de prueba del kit, usa la clave de prueba publicada en el kit y la página muestra «Modo prueba».
- Usa el puerto 8080 o uno libre, abre el navegador y, al cerrar la ventana, apaga todo.
- Si falta algo, lo dice en una frase: falta Python, falta el puente (descarga en ZIP sin submódulo) o `expreso.ini` está incompleto.

**`panel/static/`** es la página, sin framework. Tiene tres momentos en una sola pantalla: elegir el export, ver el avance (los casilleros se llenan con los eventos en vivo) y leer el resultado. Respeta «reducir movimiento», el teclado y los colores forzados. Volver atrás y recargar conservan el resultado (guarda el estado de la corrida en `sessionStorage` y lo pide de nuevo al servidor).

## Las revisiones independientes

Hubo tres, hechas por alguien distinto de quien escribió el código, y un cuarto hallazgo salió del primer uso real. En las tres revisiones, cada hallazgo se corrigió con un test que primero fallaba, y después se repitió la prueba original del revisor contra el panel real.

### 1. El servidor

**Cómo se hizo.** Con acceso de solo lectura al código, el revisor intentó romper el servidor con pedidos reales: leer archivos fuera de sus carpetas, encontrar la clave en alguna respuesta, meter código en la página con un export malicioso, mandar archivos enormes o mal formados y lanzar treinta cargas a la vez. Nada de eso funcionó. Veredicto: aprobado con observaciones, sin hallazgos críticos ni altos.

**Qué encontró y cómo se corrigió.**

| Hallazgo | Qué pasaba | Corrección | Por qué importa |
| --- | --- | --- | --- |
| Mensaje que mentía (medio) | Un export con un dato de tipo inesperado (un número donde va un nombre) rompía el puente a mitad de la carga, y la pantalla decía «No se cargó ningún envío.» cuando ya se habían cargado 19 | Los tipos se validan antes de empezar y el export se rechaza entero. Si algo inesperado corta una carga, la frase lo dice: «La carga se cortó a mitad de camino», lo cargado no se duplica | Un mensaje falso en el momento de un error lleva a una decisión equivocada, como volver a cargar a ciegas o avisar al cliente que no salió nada |
| Pedidos desde otros sitios (medio) | Una página maliciosa abierta en el mismo navegador podía, con una técnica conocida (DNS rebinding o un pedido entre sitios), usar el panel para cargar envíos con la clave de LogiSur | El servidor solo atiende pedidos hechos desde sí mismo: controla `Host` y `Origin` en todas las rutas y exige `Content-Type: application/json` en `POST /api/runs` | La clave nunca sale del servidor, pero el servidor la usa para quien se lo pida; hay que decidir a quién le responde |
| Exports con tipos raros (bajo) | Además de romper la carga, dejaban carpetas sueltas en `runs/` | Respuesta 422 y la carpeta de esa subida se borra | Sin basura que se acumula y con un error en el momento correcto |
| Pedido incompleto (bajo) | Un cliente que declaraba un cuerpo y no lo mandaba dejaba un hilo esperando para siempre | Tiempo máximo de lectura de 30 segundos (408) | Cierra una forma barata de agotar el servidor |
| Archivo demasiado grande (bajo) | Un archivo de más de 20 MB se informaba como «dañado» | Frase propia: «El archivo es demasiado grande.», con el límite | La persona sabe qué hacer: elegir otro archivo |

Se sumaron cuatro ajustes baratos: fecha estricta en la vista de atrasados (`YYYY-MM-DD` real), respuesta JSON para HEAD y OPTIONS (405), eventos que siguen llegando a quien se suscribe después de un error, y contrato definido para consultar una corrida por su identificador. Al terminar una carga, la página además anuncia el resultado a los lectores de pantalla.

### 2. La prueba real y la revisión de UX

**Cómo se hizo.** El revisor usó el panel como lo usaría operaciones, siguiendo el README al pie de la letra: primera carga, segunda carga, atrasados y Expreso Andino caído, en Chromium y Firefox, en pantalla grande y en celular. Comparó los números con los resúmenes que escribe el propio puente y cada frase con la tabla aprobada. Los cuatro pasos dieron bien. En la evaluación de UX (heurísticas de Nielsen) sacó 30 de 40, sin problemas bloqueantes ni graves.

**Qué encontró y cómo se corrigió.**

| Hallazgo | Corrección | Por qué importa |
| --- | --- | --- |
| Volver atrás perdía la respuesta | «Atrás» vuelve al resultado, y recargar también lo conserva, incluso a mitad de una carga | En el celular «atrás» es un reflejo; perder la respuesta obliga a volver a cargar |
| En el celular, lo que había que corregir quedaba a más de dos pantallas, debajo de los 23 casilleros | Los arreglos van antes del mapa; en pantalla grande se ve igual que el diseño aprobado, y el orden del teclado también los pone primero | Lo accionable no puede quedar escondido |
| El reintento de un envío no se podía ver | Aparece en «Ver detalle técnico» | Soporte necesita saber que hubo un reintento |
| La leyenda y los casilleros usaban palabras distintas | La leyenda usa las mismas etiquetas | Una sola palabra por cosa |
| Una fecha como `10/03` se lee de dos maneras | El título de atrasados la repite en palabras | Evita un malentendido de mes y día |
| Un remito que viene repetido no se aclaraba en la segunda carga | Línea propia que lo explica | Se entiende por qué se cuentan 23 envíos y no 24 filas |
| Enlaces chicos | Áreas táctiles de al menos 24 px | Se pueden tocar en el celular |
| Puerto ocupado: aparecía un error de Python | Una oración que explica el problema y propone otro puerto | Nadie en operaciones debería leer un traceback |

### 3. El lanzador de doble clic

**Cómo se hizo.** Un verificador independiente revisó el lanzador (commit `325383a`). Veredicto: aprobado, sin hallazgos críticos ni altos, con dos hallazgos medios que solo se manifiestan en Windows. Una revisión de riesgos aparte sugirió además rechazar `http` remoto. Todo se corrigió en `1b5019e`, junto con el manejo de errores inesperados.

| Hallazgo | Corrección | Por qué importa |
| --- | --- | --- |
| `expreso.ini` guardado con el Bloc de notas empieza con una marca de orden de bytes (BOM) y el archivo podía no leerse como configuración válida | Se lee como UTF-8 con BOM. Otras codificaciones, rutas ilegibles o claves repetidas dan una frase que dice qué corregir | Es el editor que más va a usar quien edite el archivo en Windows |
| Con una dirección `http://` remota, la clave viajaba sin cifrar | `http://` se acepta solo para esta computadora (`localhost`, `127.0.0.1`); cualquier otra dirección exige `https://` | La clave real no tiene que viajar nunca en texto plano por una red |
| En Windows, `SO_REUSEADDR` permite que dos procesos escuchen el mismo puerto, así que un segundo doble clic no detectaba el puerto ocupado | En Windows no se usa esa opción | El segundo doble clic no se enteraba de que el puerto ya estaba tomado y dos paneles compartían el puerto |
| Un error inesperado no tenía un mensaje pensado para quien hizo doble clic: mostraba un traceback y la ventana podía cerrarse sola | Mensaje en español con el tipo de error, y la ventana espera Enter | Quien hizo doble clic necesita ver qué pasó antes de que desaparezca |

Windows queda sin probar en un equipo real.

### 4. El primer uso real en Linux

**Cómo se encontró.** No lo encontró una revisión, sino el primer uso: en el escritorio GNOME, «Ejecutar como un programa» sobre `Abrir panel.desktop` no hacía nada. La prueba anterior había abierto el archivo con `gio launch`, un camino que el gestor de archivos no usa.

| Hallazgo | Corrección | Por qué importa |
| --- | --- | --- |
| El gestor de archivos de GNOME ya no abre archivos `.desktop`: los corre como un script de shell, que falla sin mostrar nada | `Abrir panel.sh`, un script ejecutable que, si lo arranca el gestor de archivos sin ventana, se vuelve a abrir solo en una terminal (`xdg-terminal-exec` o la que haya instalada) y explica si falta Python | El lanzador existe para no usar la terminal; si no abre, no sirve |

Los tests corren el script como lo haría el gestor de archivos, con una terminal y un Python falsos, y comprueban cada camino. Además se probó de verdad arrancándolo sin terminal: abrió la ventana y el panel, la carga dio 19 cargados, 1 ya estaba y 3 para corregir, y al cerrar la ventana se apagó todo.

## Contrato de la API HTTP

Todo el JSON es UTF-8. Los errores usan `{"answer": Answer}` con las frases de «no se pudo correr», nunca un traceback.

### Regla del mismo sitio

Vale para todas las rutas, incluidas las estáticas y los eventos en vivo.

- `Host` tiene que ser `127.0.0.1:<puerto>`, `localhost:<puerto>` o `[::1]:<puerto>` (más el host al que se ató el servidor, si no es un comodín). Si no: `403 {"error": "forbidden_host"}`. Esto cierra el DNS rebinding.
- Si hay `Origin`, tiene que ser `http://` más uno de esos hosts. Si no: `403 {"error": "forbidden_origin"}`.
- `POST /api/runs` exige `Content-Type: application/json`. Si no: `415 {"error": "unsupported_media_type"}`.
- Cualquier otro método (HEAD, OPTIONS, PUT, DELETE, PATCH) da `405 {"error": "method_not_allowed"}` con `Allow: GET, POST`.
- Un cliente que deja de mandar su cuerpo durante 30 s se descarta con `408 {"error": "request_timeout"}`.

### Rutas

| Método y ruta | Cuerpo | Respuesta |
| --- | --- | --- |
| `GET /` | | `static/index.html` |
| `GET /static/<archivo>` | | el archivo, con su tipo de contenido; sin listado de carpetas ni `..` |
| `GET /api/config` | | `200 {"testMode": bool}`: `true` cuando el panel apunta a la API de prueba del kit (la página muestra «Modo prueba») |
| `POST /api/exports` | bytes del archivo; encabezado `X-Export-Name` | `201 {"export_id", "preview": Preview}`; `422 {"answer"}` si no se puede leer (incluye tipos incorrectos y borra la carpeta de esa subida); `413 {"answer"}` si supera el límite (20 MB) |
| `POST /api/runs` | `{"export_id"}` | `202 {"run_id"}`; `409 {"answer"}` si ya hay una carga en curso; `404` si el export no existe |
| `GET /api/runs/<id>/events` | | `text/event-stream`: un `event: result` por remito con un `ResultView`, y al final `event: done` con un `RunView` o `event: failed` con `{"answer", "technical"}`. Quien se suscribe tarde recibe primero lo ocurrido hasta ahí |
| `GET /api/runs/<id>` | | `200 RunView` si terminó; `200 {"answer", "technical", "run_id"}` si falló; `202 {"run_id", "running": true}` mientras corre; `404 {"error": "unknown_run"}` |
| `GET /api/exports/<export_id>/overdue?today=YYYY-MM-DD` | | `200 OverdueView`. `today` es opcional (por defecto, la fecha del servidor). `400 {"error": "bad_date"}` si no es una fecha real en ese formato; `404 {"error": "unknown_export"}`; si no se puede consultar, `{"answer", "technical"}` con `422` (ilegible), `503` (falta la clave) o `502` (clave rechazada o API caída) |

### Formas de los datos

```text
Preview    = { export_name, export_total, shipments: [{remito, recipient, client, street, city, province}],
               duplicates: [remito], andino_remitos }
ResultView = { index, remito, recipient, client, address, state, label, duplicate, tracking,
               problems: [{title, hint}], picked, technical }
RunView    = { run_id, export_name, export_total, shipments_total, generated_at, answer,
               counts: {ok, prev, fix, none}, results: [ResultView], report_file }
OverdueView = { title, empty, items: [{ remito, recipient, client, city, tracking, status,
                status_text, late_line, days_late, estimated_delivery }] }
Answer     = { headline, sub, button, action }   # action: show_fixes | reload | retry | pick_other | null
```

- `technical` es el detalle del puente, sin tocar. `state` es `ok`, `prev`, `fix`, `none` o `null` (un duplicado no tiene casillero propio).
- `action` le dice a la página qué hace un botón; la página nunca lo deduce del texto.
- Un atrasado cuya `estimated_delivery` no es una fecha ISO igual se lista, con `late_line` vacío y `days_late` en `null`.
- Si una carga se corta por una excepción que nadie previó, el evento `failed` lleva «No se pudo completar la carga.» (no se cargó nada) o «La carga se cortó a mitad de camino.» (algo ya se había cargado). Nunca se disfraza de «Expreso Andino no responde».
- Las frases de «no se pudo correr» terminan con «No se cargó ningún envío.», que no corresponde a la vista de atrasados; esa ruta usa la variante sin esa oración.

### Configuración

Se lee al arrancar `python3 -m panel`: `EXPRESO_API_URL` (por defecto `http://localhost:8000`) y `EXPRESO_API_KEY`. `--port` cambia el puerto (por defecto 8080). Con el doble clic se usa `expreso.ini` (ver [`expreso.ini.ejemplo`](../expreso.ini.ejemplo)).

Una decisión consciente: `runs/exports` y `runs/reports` crecen con cada carga y no se podan. Borrar los viejos queda en manos de quien opera hasta que valga la pena automatizarlo; como el puente es idempotente, borrar un export viejo es seguro.

## Tests y lo que no se verificó

- `python3 -m unittest` desde la raíz corre 187 tests. Los de `bridge` y `server` levantan solos la API de prueba del kit en un puerto libre y recorren la primera corrida (19 cargados, 1 ya estaba, 1 duplicado en el export, 3 para corregir) y la segunda (0 cargados, 20 ya estaban), con los eventos en orden, el resumen escrito y cada motivo de «no se pudo correr».
- Los de `phrases` tienen un test por fila de la tabla de frases, con el texto exacto.
- Los del lanzador cubren la lectura de `expreso.ini`, el puerto ocupado, el modo prueba y los mensajes de error.
- **Sin verificar:** Safari (WebKit no corre en la máquina de desarrollo), el doble clic en Windows y la reconexión de la página si se corta la red a mitad de una carga.
