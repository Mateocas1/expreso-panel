# Brief · Result screen of an upload run

Working notes for T1 (`odd/tasks/panel-operaciones.md`). Not shipped in any artboard.

## Shape (impeccable)

- **Job and audience.** The person who runs shipments at LogiSur opens the panel after the daily export is loaded. They know clients, remitos and LogiSur's system. They do not know HTTP, APIs or error codes.
- **Outcome and proof.** In five seconds they can answer "¿Tengo que hacer algo?". Proof: the first sentence on screen answers it, and every pending item says what is missing, for whom and where to fix it.
- **Scope.** One screen (the result) in full; the two earlier moments (pick the export, upload in progress) only as hints.
- **States and ranges.** Data from the kit: 51 remitos in the export, 24 for Expreso Andino; 19 loaded (one of them confirmed on the second attempt), 1 already existed, 1 repeated in the export, 3 rejected. A second run gives 0 loaded, 20 already existed, the same 3 rejected. Directions must survive 0 pending and many pending.
- **Constraints.** Self-contained HTML, system fonts, no external URLs. Mode: Operate (impeccable): ambition shows as precision and restraint. Color strategy: Restrained, neutrals tinted toward each direction's world plus one accent and the status colors actually used.

## Shared content decisions

- **The answer comes first, as a sentence.** No metric hero, no greeting, no eyebrow.
- **Rejected is attention, not danger.** The shipments are not lost and the user did nothing wrong, so amber marks them, never red fills.
- **The client is shown next to the recipient.** The bridge result carries the recipient (`destinatario.razon_social`); the LogiSur client comes from the export. For the operations person the client is who you call.
- **The remito's own note is used.** R-10000477 says "Cliente no informó CP": that tells the user whom to ask, which is better than any generic phrase.
- **The retry is not news.** Pinturerías del Oeste (R-10000612) appears as loaded; "confirmado en el intento 2" lives only in the technical detail.
- **Technical detail is kept, not deleted.** The HTTP status, the API field path and message, the report file and the exit code sit behind "Ver detalle técnico".
- **Voice.** Spanish with voseo and no slang: it is how Argentine software talks to its users (argentina.gob.ar does too). One form across the whole flow.

## Directions (unslop: Product / Character / World / Moments / Signature)

### 01 · La nota
- Character: a colleague who leaves you a note before going home.
- World: warm paper, ink, a serif answer, one narrow column.
- Moments: the answer sentence; the three fixes written as prose.
- Signature: no cards and no table on the first screen; everything reads top to bottom like a short letter.

### 02 · La bandeja
- Character: a calm checklist that tracks your work.
- World: app shell with navigation (Cargar, Corridas, Atrasados), cool neutrals, list and detail.
- Moments: the selected fix with its steps; the "0 de 3 corregidos" counter that unlocks reloading.
- Signature: "Ya lo corregí" checkboxes; the primary action becomes prominent when all three are marked.

### 03 · El mapa
- Character: the whole batch at a glance.
- World: each of the 23 shipments is a tile (24 remitos minus the one repeated in the export); the three that need a fix stand out.
- Moments: the map; the same tiles fill in during the upload, so progress and result look like one object.
- Signature: one tile per remito, from the export preview to the progress to the result.
