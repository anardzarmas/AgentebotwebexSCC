# BEST — Master de Herramientas

User: {{name}} · {{email}} · Org Zoho {{zoho_org_id}}

## Skills
- `skills/herramienta-1-leads/SKILL.md` — H1 Leads
- `skills/herramienta-2-oportunidades/SKILL.md` — H2 Oportunidades
- `skills/herramienta-3-reporte/SKILL.md` — H3 Reporte

## Reglas globales
- Integraciones vía Composio (Zoho CRM + Outlook). Entity ID Composio: {{composio_entity_id}}
- Nunca enviar correo: Outlook = solo borradores (isDraft=true).
- Nunca screenshots. Procesar: datos → borradores → notas CRM.

## Firma de correos
{{name}} / {{title}} - {{company}} / {{email}}

## Referencia rápida Composio
| Op | Acción Composio |
|----|----------------|
| Leads activos | `ZOHOCRM_LIST_RECORDS(module=Leads, cvid="{{zoho_view_leads}}", entity_id="{{composio_entity_id}}")` |
| Oportunidades | `ZOHOCRM_LIST_RECORDS(module=Potentials, cvid="{{zoho_view_potentials}}", entity_id="{{composio_entity_id}}")` |
| Emails por IDs | `ZOHOCRM_LIST_RECORDS(module=Contacts, ids=[...], fields="id,Full_Name,Email", entity_id="{{composio_entity_id}}")` |
| Notas recientes | `ZOHOCRM_GET_RELATED_RECORDS(module=<mod>, id=ID, related=Notes, per_page=3, sort_by=Created_Time, sort_order=desc, entity_id="{{composio_entity_id}}")` |
| Crear notas (lote) | `ZOHOCRM_CREATE_RECORDS(module=Notes, data=[{...}], entity_id="{{composio_entity_id}}")` |
| Borrador Outlook | `MICROSOFT_OUTLOOK_CREATE_DRAFT(to=EMAIL, subject=ASUNTO, body=CUERPO, isDraft=true, entity_id="{{composio_entity_id}}")` |

## Filtros
- H1 omitir Lead_Status: Sin interes · Descartado · Lead desechado.
- H2 omitir Stage: Closed Lost · Terminado. Procesar: Negotiate · Comprar · Entregar.

## Formato de notas CRM
Título: `Seguimiento preparado - <FECHA> (Herramienta <N> - <DIA>)` · Fecha: en inglés · Día: en español.
