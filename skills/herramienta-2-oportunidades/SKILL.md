---
name: herramienta-2-oportunidades
description: "BEST H2 — seguimiento semanal de Oportunidades. Lee vista My Oportunidades, obtiene emails de contactos en lote, crea borradores en Outlook y registra notas CRM en lote. Integraciones vía Composio."
---

# H2 — Oportunidades (BEST)

User: agarcen@best.org.mx · Org 651658110

## Reglas
- Composio para Zoho y Outlook. Sin screenshots. Outlook = solo borradores (isDraft=true).

## F1 — Datos
1. `ZOHOCRM_LIST_RECORDS(module=Potentials, cvid="2680941000000087569", fields="id,Deal_Name,Stage,Amount,Closing_Date,Account_Name,Contact_Name", per_page=100)`
2. Omitir Stage ∈ {Closed Lost, Terminado}. Procesar ∈ {Negotiate, Comprar, Entregar}.
3. Recolectar todos los Contact_Name.id de las oportunidades activas → una sola llamada:
   `ZOHOCRM_LIST_RECORDS(module=Contacts, ids=[id1,id2,...], fields="id,Full_Name,Email")`
4. Notas (paralelo): por cada oportunidad activa:
   `ZOHOCRM_GET_RELATED_RECORDS(module=Potentials, id=ID, related=Notes, per_page=3, sort_by=Created_Time, sort_order=desc)`

## F2 — Borradores Outlook (solo oportunidades con Email resuelto)
```
MICROSOFT_OUTLOOK_CREATE_DRAFT(
  to=Email, subject=ASUNTO, body=CUERPO, isDraft=true
)
```
Asunto/tono por Stage:
- Negotiate → "Seguimiento propuesta [Producto] - [Empresa]" · cierre, dudas/ajustes, llamada.
- Comprar → "Confirmación pedido [Producto] - [Empresa]" · datos orden, facturación/entrega.
- Entregar → "Coordinación entrega [Producto] - [Empresa]" · fechas, contacto técnico, accesos.

Cuerpo: 3 párrafos (nota CRM reciente · acción del stage · propuesta concreta) + firma:
`Aline Garcén / Account Manager - BEST Typhoon Technologies / agarcen@best.org.mx`

N Technology → contacto único Erendira Sánchez <emartinez@n.technology>. Un borrador por oportunidad.

## F3 — Notas CRM (una sola llamada en lote)
```
ZOHOCRM_CREATE_RECORDS(module=Notes, data=[
  {
    Note_Title: "Seguimiento preparado - <FECHA> (Herramienta 2 - <DIA>)",
    Note_Content: "Contexto: stage <STAGE>, $<AMOUNT>, cierre <CLOSING_DATE>. <resumen nota reciente>\nAccion <FECHA>: borrador a <email> con asunto \"<ASUNTO>\".",
    $se_module: "Potentials",
    Parent_Id: {id: OPPORTUNITY_ID}
  },
  ... (un objeto por cada oportunidad procesada)
])
```

## Errores
- Sin email tras lookup en lote → nota CRM sin Outlook. Stage desconocido → tratar como Negotiate.

## Output
```
H2 [FECHA] · procesadas:N · borradores:X · notas:X · sin_email:X · errores:X
```
