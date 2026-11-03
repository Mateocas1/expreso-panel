Panel web para que operaciones (no técnica) entienda las corridas del puente LogiSur → Expreso Andino (`~/code/caso-expreso`).
Diseño primero (3 direcciones), después implementación. Razonamiento y decisiones en `docs/bitacora.md`.

## Specs

- S1. Una interfaz para el puente, pensada para que "alguien no técnico tiene que poder entender lo que está pasando".
- S2. Los códigos de error o de devolución pasan a frases: "Pasar los códigos de error o de devolución a frases. Que expliquen lo que está pasando."
- S3. "Todo bastante visible. Pero de todas formas que no sea tanta información, que esté lo justo y necesario, que sea amigable, agradable a la vista. Entendible, trabajar sobre el UX."
- S4. Empezar con "las tres primeras direcciones visuales", aplicando "todo lo que es de Better UI. La última versión de Impeccable. Y también [...] Unslop".
- S5. Persistir "todos los pensamientos, justificaciones, decisiones y demás. Para poder después mandar el mail de seguimiento" (`docs/bitacora.md`).

## Tasks

- [ ] T1 · S1-S5 · Tres direcciones visuales en `design/<slug>/` con gentle-design, abiertas en el canvas; Mateo elige una. Registrar decisiones en la bitácora. Estado: tres direcciones en `design/resultado-corrida/` (01-la-nota, 02-la-bandeja, 03-el-mapa), abiertas en el canvas. Mateo eligió 03-el-mapa (L5); se pule con animaciones sutiles al estilo Emil Kowalski, y las otras dos quedan como alternativas.
- [ ] T2 · S2 · Tabla final de frases por resultado y por campo rechazado, revisada con better-writing; registrar en la bitácora.
- [ ] T3 · S1-S3 · Implementar la dirección elegida sobre el puente, sin cambiar su lógica, con tests de que cada resultado muestra su frase.
- [ ] T4 · S1-S3 · Prueba real contra la API del kit (primera y segunda corrida) y revisión final de UX.
- [ ] T5 · S5 · Borrador del mail de seguimiento a partir de la bitácora (el envío lo decide Mateo).

## Log

- L1 (2026-11-03, Mateo, verbatim): "Me preguntó también si tuviera que vender esta API o automatización que hicimos a un cliente como lo haría. Y me sugirió como una UI. Crees que podríamos construir algo así. Que se vea lindo, que esté bien. [...] él me planteaba que quizás alguien no técnico tiene que poder entender lo que está pasando. Y evidentemente en la terminal o con los códigos 409, 5023, no se llega a comprender tanto para alguien no técnico. Entonces la idea es hacerlo muy amigable a la gente no técnica. Con prácticamente textos. Pasar los códigos de error o de devolución a frases. Que expliquen lo que está pasando. Todo bastante visible. Pero de todas formas que no sea tanta información, que esté lo justo y necesario, que sea amigable, agradable a la vista. Entendible, trabajar sobre el UX."
- L2 (2026-11-03, Mateo, verbatim): "me gustaría ir de alguna forma. Persistiendo toda esta info. [...] Todos los pensamientos, justificaciones, decisiones y demás. Para poder después mandar el mail de seguimiento. [...] me gustaría arrancar esto directamente en un directorio repo nuevo. [...] ya arrancar con los tres diseños. O con las tres primeras direcciones visuales. Que me gustaría también ahí aplicar lo que es el stack que estamos usando. Últimamente. Que es todo lo que es de Better UI. La última versión de Impeccable. Y también teníamos por ahí dando vueltas. Unslop."
- L3 (2026-11-03, parent): plan acordado con Mateo: persona = operaciones de LogiSur; lo que requiere acción primero; frase que dice qué pasó y qué hacer; detalle técnico en "ver detalle"; el panel es una capa sobre el puente, sin tocar su lógica. Unslop viene de https://github.com/heydamir/unslop.
- L4 (2026-11-03, T1): diseño `design/resultado-corrida/` con tres artboards: `01-la-nota.html` (La nota), `02-la-bandeja.html` (La bandeja), `03-el-mapa.html` (El mapa). Datos reales de la corrida del kit. Hallazgo: Panadería La Espiga, Sanitarios Rivera y Carnicería El Gaucho son destinatarios; los clientes son Textil Del Plata SRL y Ferretería Industrial Norte SA. Se cuentan 23 envíos (R-10000507 viene repetido). Decisiones en `docs/bitacora.md` §9-§10.
- L5 (2026-11-03, Mateo, verbatim): "yo diria el mapa, vos que decis? cual te parece la mejor? objetivamente y entendiendo el problema y con la impronta inicial, digamos me gustaria construir sobre esta base, y entiendo que se puede pulir mucho muchisimo mas, podemos agregar el flujo de animaciones de emil kowalski, para agregar algunas sutiles, que agreguen sensacion de premium, bien cuidado, sutiles pero que agreguen sensacion de fluidez tambien"
- L6 (2026-11-03, T1): artboard elegido `design/resultado-corrida/03-el-mapa.html`; `01-la-nota.html` y `02-la-bandeja.html` quedan como alternativas. Se itera 03 en el lugar con animaciones con propósito (carga en vivo, selección, desplegables), respetando "reducir movimiento".
