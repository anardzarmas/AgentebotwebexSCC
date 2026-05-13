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
| Leads activos | `ZOHO_GET_ZOHO_RECORDS(module=Leads, cvid="{{zoho_view_leads}}", fields="id,First_Name,Last_Name,Company,Email,Lead_Status,Phone")` |
| Oportunidades | `ZOHO_GET_ZOHO_RECORDS(module=Potentials, cvid="{{zoho_view_potentials}}", fields="id,Deal_Name,Stage,Amount,Closing_Date,Account_Name,Contact_Name")` |
| Emails contactos (lote) | `ZOHO_GET_ZOHO_RECORDS(module=Contacts, ids=[id1,id2,...], fields="id,Full_Name,Email")` |
| Notas recientes | `ZOHO_GET_RELATED_RECORDS(module=<mod>, record_id=ID, related_list_api_name=Notes, per_page=3, sort_by=Created_Time, sort_order=desc)` |
| Crear nota/registro | `ZOHO_CREATE_ZOHO_RECORD(module=Notes, data={Note_Title, Note_Content, $se_module, Parent_Id})` |
| Buscar registros | `ZOHO_SEARCH_ZOHO_RECORDS(module=Notes, criteria="(Note_Title:contains:...)")` |
| Borrador Outlook | `MICROSOFT_OUTLOOK_CREATE_DRAFT(to=EMAIL, subject=ASUNTO, body=CUERPO, isDraft=true)` |

## Filtros
- H1 omitir Lead_Status: Sin interes · Descartado · Lead desechado.
- H2 omitir Stage: Closed Lost · Terminado. Procesar: Negotiate · Comprar · Entregar.

## Formato de notas CRM
Título: `Seguimiento preparado - <FECHA> (Herramienta <N> - <DIA>)` · Fecha: en inglés · Día: en español.
