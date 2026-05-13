---
name: herramienta-1-leads
description: "BEST H1 — seguimiento semanal de Leads. Lee vista My Leads, crea borradores en Outlook y registra notas CRM en lote. Integraciones vía Composio."
---

# H1 — Leads (BEST)

User: agarcen@best.org.mx · Org 651658110

## Reglas
- Composio para Zoho y Outlook. Sin screenshots. Outlook = solo borradores (isDraft=true).

## F1 — Datos
1. `ZOHO_GET_ZOHO_RECORDS(module=Leads, cvid="{{zoho_view_leads}}", fields="id,First_Name,Last_Name,Company,Email,Lead_Status,Phone", per_page=100)`
2. Omitir Lead_Status ∈ {Sin interes, Descartado, Lead desechado}.
3. Por cada lead activo: `ZOHO_GET_RELATED_RECORDS(module=Leads, record_id=ID, related_list_api_name=Notes, per_page=3, sort_by=Created_Time, sort_order=desc)`

## F2 — Borradores Outlook (solo leads con Email)
```
MICROSOFT_OUTLOOK_CREATE_DRAFT(
  to=Email, subject=ASUNTO, body=CUERPO, isDraft=true
)
```
Asunto: conciso, referencia última interacción.
Cuerpo: 3 párrafos (nota CRM reciente · pregunta/siguiente paso · oferta de llamada) + firma:
`Aline Garcén / Account Manager - BEST Typhoon Technologies / agarcen@best.org.mx`

## F3 — Notas CRM (una sola llamada en lote)
```
ZOHO_CREATE_ZOHO_RECORD(module=Notes, data={
  Note_Title: "Seguimiento preparado - <FECHA> (Herramienta 1 - <DIA>)",
  Note_Content: "Contexto: ...\nAccion <FECHA>: borrador a <email> con asunto \"<ASUNTO>\".\nSiguiente paso: ...",
  $se_module: "Leads",
  Parent_Id: {id: LEAD_ID}
})
```
Llamar una vez por cada lead (en secuencia).

## Errores
- Sin email → incluir nota CRM igual, omitir Outlook.
- CREATE_RECORDS falla → 1 reintento; si falla de nuevo, continuar con siguiente.

## Output
```
H1 [FECHA] · procesados:N · borradores:X · notas:X · sin_email:X · errores:X
```
