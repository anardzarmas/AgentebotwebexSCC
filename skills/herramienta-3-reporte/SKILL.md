---
name: herramienta-3-reporte
description: "BEST H3 — reporte diario consolidado de H1+H2. Genera Reporte_Herramientas_<FECHA>.md. Sin Outlook."
---

# H3 — Reporte (BEST)

## Input
Resúmenes en memoria de H1 y H2. Si faltan, recuperar notas de hoy:
```
ZOHO_SEARCH_ZOHO_RECORDS(module=Notes,
  criteria="(Note_Title:contains:Herramienta 1 - <DIA>)(Owner.email:equals:{{email}})",
  fields="Note_Title,Note_Content,Parent_Id,Created_Time", per_page=50)
```
Repetir para Herramienta 2.

## Output
Archivo: `Reporte_Herramientas_<YYYY-MM-DD>.md`

```markdown
# Reporte — <DIA>, <FECHA>
Ejecutado: {{name}} · H1 + H2

## Resumen
| Tool | Reg | Borr | Notas | Err |
|------|-----|------|-------|-----|
| H1   | X   | X    | X     | X   |
| H2   | X   | X    | X     | X   |

## H1 — Borradores
| # | Contacto | Empresa | Email | Asunto |
...
Sin email: ... | Inactivos: ...

## H2 — Borradores
| # | Op | Cuenta | Email | Stage | Monto | Asunto |
...
Sin email: ... | Inactivas: ...

## Errores
...

## Próximas acciones
- Revisar y enviar borradores en Outlook.
- <Cierres próximos / urgencias>.
```

## Output
```
H3 [FECHA] · reporte: <ruta>
```
