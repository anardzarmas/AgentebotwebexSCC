---
name: herramienta-1-leads
description: "BEST H1 — seguimiento semanal de Leads. Lee vista My Leads, crea borradores en Outlook y registra notas CRM en lote. Integraciones vía Composio."
---

# H1 — Leads (BEST)

User: {{email}} · Org {{zoho_org_id}}

## Reglas
- Composio para Zoho y Outlook. Sin screenshots. Outlook = solo borradores (isDraft=true).
- **EFICIENCIA: Agrupa el máximo de tool calls en cada respuesta. Nunca llames una herramienta sola si puedes llamar varias al mismo tiempo.**

## FASE 1 — Obtener leads
Llama UNA VEZ usando el view "My Leads" (ya filtrado por usuario en Zoho):
`ZOHO_GET_ZOHO_RECORDS(module=Leads, cvid="{{zoho_view_leads}}", fields="id,First_Name,Last_Name,Company,Email,Lead_Status,Phone,Owner", per_page=20)`

Verificación adicional: conservar SOLO registros donde `Owner.email == "{{email}}"`. Descartar cualquier otro.
Omitir Lead_Status ∈ {Sin interes, Descartado, Lead desechado}. Guardar lista de leads activos.

## FASE 2 — Obtener notas (TODO EN UNA SOLA RESPUESTA)
En una sola respuesta, llama `ZOHO_GET_RELATED_RECORDS` para TODOS los leads activos simultáneamente:
```
ZOHO_GET_RELATED_RECORDS(module_api_name=Leads, record_id=ID_1, related_list_api_name=Notes, fields="id,Note_Title,Note_Content,Created_Time", per_page=2, sort_by=Created_Time, sort_order=desc)
ZOHO_GET_RELATED_RECORDS(module_api_name=Leads, record_id=ID_2, related_list_api_name=Notes, fields="id,Note_Title,Note_Content,Created_Time", per_page=2, sort_by=Created_Time, sort_order=desc)
... (un bloque por cada lead activo, todos en la misma respuesta)
```

## FASE 3 — Borradores Outlook (TODO EN UNA SOLA RESPUESTA)
En una sola respuesta, llama `OUTLOOK_CREATE_DRAFT` para TODOS los leads con Email al mismo tiempo:
```
OUTLOOK_CREATE_DRAFT(to_recipients=[Email_1], subject=ASUNTO_1, body=CUERPO_1)
OUTLOOK_CREATE_DRAFT(to_recipients=[Email_2], subject=ASUNTO_2, body=CUERPO_2)
... (un bloque por cada lead con email, todos en la misma respuesta)
```

Asunto: conciso, referencia última interacción.
Cuerpo: 3 párrafos (nota CRM reciente · pregunta/siguiente paso · oferta de llamada) + firma:
`{{name}} / {{title}} - {{company}} / {{email}}`

## FASE 4 — Notas CRM (TODO EN UNA SOLA RESPUESTA)
En una sola respuesta, llama `ZOHO_CREATE_ZOHO_RECORD` para TODOS los leads al mismo tiempo:
```
ZOHO_CREATE_ZOHO_RECORD(module=Notes, data={
  "Note_Title": "Seguimiento preparado - <FECHA> (Herramienta 1 - <DIA>)",
  "Note_Content": "Contexto: Lead_Status <STATUS>. <resumen nota reciente>\nAccion <FECHA>: borrador a <email> con asunto \"<ASUNTO>\".\nSiguiente paso: ...",
  "se_module": "Leads",
  "Parent_Id": "LEAD_ID"
})
```
- `Parent_Id` es un string con el ID del lead (NO un objeto, NO `{id: ...}`).
- `se_module` sin el símbolo `$`.
- Un bloque por cada lead, TODOS en la misma respuesta.

## Errores
- Sin email → incluir nota CRM igual, omitir Outlook.
- CREATE_RECORDS falla → continuar con siguiente lead.

## Output
```
H1 [FECHA] · procesados:N · borradores:X · notas:X · sin_email:X · errores:X
```
