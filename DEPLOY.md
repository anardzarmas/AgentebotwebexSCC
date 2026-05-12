# Pasos para independizar el agente del equipo local

## Resumen de la arquitectura objetivo

```
[Cron cloud] → [agent.py en Railway/Render] → [Composio] → [Zoho CRM + Outlook]
```

El agente corre en la nube, sin Chrome, sin Cowork, sin que la PC de Aline esté encendida.

---

## Paso 1 — Cuentas necesarias (gratuitas)

| Servicio | Para qué | URL |
|---|---|---|
| Anthropic | API key de Claude | console.anthropic.com |
| Composio | Conectores Zoho + Outlook | app.composio.dev |
| Railway | Hosting + cron scheduler | railway.app |
| GitHub | Repositorio del código | github.com |

---

## Paso 2 — Configurar Composio

1. Crear cuenta en **app.composio.dev**
2. Ir a **Apps** → buscar **Zoho CRM** → conectar con OAuth (cuenta de Aline)
3. Ir a **Apps** → buscar **Microsoft Outlook** → conectar con OAuth (cuenta de Aline)
4. Copiar tu **Composio API Key** desde Settings → API Keys

> Composio guarda los tokens OAuth. El agente nunca necesita credenciales de Aline directamente.

---

## Paso 3 — Subir código a GitHub

```bash
# En la carpeta del proyecto
git init
git add agent.py requirements.txt skills/ .env.example
git commit -m "Asistente ventas BEST — agente autónomo"
git remote add origin https://github.com/TU_USUARIO/best-sales-agent.git
git push -u origin main
```

> **No subir el archivo `.env`** (tiene tus API keys). Solo subir `.env.example`.

---

## Paso 4 — Deploy en Railway

1. Ir a **railway.app** → New Project → Deploy from GitHub repo
2. Seleccionar el repositorio `best-sales-agent`
3. En **Variables** (Settings → Variables), agregar:
   ```
   ANTHROPIC_API_KEY = sk-ant-...
   COMPOSIO_API_KEY  = ...
   ```
4. Railway detecta `requirements.txt` automáticamente (Python)

---

## Paso 5 — Configurar los cron jobs en Railway

En Railway → tu proyecto → **New Service → Cron**:

| Job | Comando | Horario (cron) | Días |
|---|---|---|---|
| H1 Leads | `python agent.py H1` | `0 21 * * 1,3` | Lun, Mié 9pm |
| H2 Oportunidades | `python agent.py H2` | `0 21 * * 2,4` | Mar, Jue 9pm |
| H3 Reporte | `python agent.py H3` | `7 23 * * *` | Diario 11:07pm |

> Nota: los horarios son UTC. México (CDT) = UTC-5. Para 9pm CDT usar `0 2 * * *` del día siguiente.
> Ajustar según zona horaria configurada en Railway.

---

## Paso 6 — Verificar que funciona

```bash
# Prueba local antes de hacer deploy
pip install -r requirements.txt
cp .env.example .env   # llenar con tus keys reales
python agent.py H1
```

Railway también permite ejecutar cualquier job manualmente desde el dashboard.

---

## Resultado

- El agente corre automáticamente en la nube según el calendario
- Aline solo abre Outlook para revisar y enviar los borradores que ya están listos
- Sin Chrome, sin Cowork, sin que la PC esté encendida
- Los reportes H3 se pueden guardar en un bucket S3 o enviar a Aline por email (mejora futura)

---

## Mejoras opcionales (fase 2)

| Mejora | Cómo |
|---|---|
| Notificación a Aline cuando termina | Agregar `MICROSOFT_OUTLOOK_SEND_EMAIL` al final de H3 con el reporte |
| Guardar reportes en la nube | Composio + Google Drive o S3 |
| Dashboard de actividad | Logtail o Railway Metrics |
