---
name: herramienta-2-oportunidades
description: "BEST H2 — seguimiento semanal de Oportunidades. Lee vista My Oportunidades, obtiene emails de contactos en lote, crea borradores en Outlook y registra notas CRM en lote. Integraciones vía Composio."
---

# H2 — Oportunidades (BEST)

User: {{email}} · Org {{zoho_org_id}}

## Reglas
- Composio para Zoho y Outlook. Sin screenshots. Outlook = solo borradores (isDraft=true).
- **EFICIENCIA: Agrupa el máximo de tool calls en cada respuesta. Nunca llames una herramienta sola si puedes llamar varias al mismo tiempo.**

## FASE 1 — Obtener oportunidades
Llama UNA VEZ con filtro por owner:
`ZOHO_GET_ZOHO_RECORDS(module=Potentials, criteria="(Owner.email:equals:{{email}})", fields="id,Deal_Name,Stage,Amount,Closing_Date,Account_Name,Contact_Name,Owner", per_page=20)`

Si criteria devuelve error, intentar sin criteria pero con per_page=20. El filtro por Owner.email se aplica automáticamente en el sistema — NO pagines más allá de la primera página.
Omitir Stage ∈ {Closed Lost, Terminado}. Procesar ∈ {Negotiate, Comprar, Entregar}.
Recolectar todos los Contact_Name.id de las oportunidades activas.

## FASE 2 — Contactos y notas (TODO EN UNA SOLA RESPUESTA)
En una sola respuesta, llama SIMULTÁNEAMENTE:
1. Un `ZOHO_GET_ZOHO_RECORDS(module=Contacts, ids=[id1,id2,...], fields="id,Full_Name,Email")` para TODOS los contactos a la vez.
2. Un `ZOHO_GET_RELATED_RECORDS` por cada oportunidad activa:
```
ZOHO_GET_RELATED_RECORDS(module_api_name=Potentials, record_id=ID_1, related_list_api_name=Notes, fields="id,Note_Title,Note_Content,Created_Time", per_page=2, sort_by=Created_Time, sort_order=desc)
ZOHO_GET_RELATED_RECORDS(module_api_name=Potentials, record_id=ID_2, related_list_api_name=Notes, fields="id,Note_Title,Note_Content,Created_Time", per_page=2, sort_by=Created_Time, sort_order=desc)
... (todos en la misma respuesta)
```

## FASE 3 — Borradores Outlook (TODO EN UNA SOLA RESPUESTA)
En una sola respuesta, llama `OUTLOOK_CREATE_DRAFT` para TODAS las oportunidades con Email resuelto:
```
OUTLOOK_CREATE_DRAFT(to_recipients=[Email_1], subject=ASUNTO_1, body=CUERPO_1)
OUTLOOK_CREATE_DRAFT(to_recipients=[Email_2], subject=ASUNTO_2, body=CUERPO_2)
... (todos en la misma respuesta)
```

Asunto/tono por Stage:
- Negotiate → "Seguimiento propuesta [Producto] - [Empresa]" · cierre, dudas/ajustes, llamada.
- Comprar → "Confirmación pedido [Producto] - [Empresa]" · datos orden, facturación/entrega.
- Entregar → "Coordinación entrega [Producto] - [Empresa]" · fechas, contacto técnico, accesos.

Cuerpo: 3 párrafos (nota CRM reciente · acción del stage · propuesta concreta) + firma:
`{{name}} / {{title}} - {{company}} / {{email}}`

N Technology → contacto único Erendira Sánchez <emartinez@n.technology>. Un borrador por oportunidad.

## FASE 4 — Notas CRM (TODO EN UNA SOLA RESPUESTA)
En una sola respuesta, llama `ZOHO_CREATE_ZOHO_RECORD` para TODAS las oportunidades al mismo tiempo:
```
ZOHO_CREATE_ZOHO_RECORD(module=Notes, data={
  "Note_Title": "Seguimiento preparado - <FECHA> (Herramienta 2 - <DIA>)",
  "Note_Content": "Contexto: stage <STAGE>, $<AMOUNT>, cierre <CLOSING_DATE>. <resumen nota reciente>\nAccion <FECHA>: borrador a <email> con asunto \"<ASUNTO>\".",
  "se_module": "Potentials",
  "Parent_Id": "OPPORTUNITY_ID"
})
```
- `Parent_Id` es un string con el ID de la oportunidad (NO un objeto, NO `{id: ...}`).
- `se_module` sin el símbolo `$`.
- Un bloque por cada oportunidad, TODOS en la misma respuesta.

## Errores
- Sin email tras lookup en lote → nota CRM sin Outlook. Stage desconocido → tratar como Negotiate.

## Output
```
H2 [FECHA] · procesadas:N · borradores:X · notas:X · sin_email:X · errores:X
```
