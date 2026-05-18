"""
Asistente de Ventas BEST — arquitectura simplificada
Python orquesta todo vía Composio HTTP. LLM solo genera texto de emails (1 llamada).

Providers soportados:
  - Anthropic Claude  → si ANTHROPIC_API_KEY está en .env
  - Groq (gratis)     → si GROQ_API_KEY está en .env
"""

import os, sys, json, re, argparse, datetime, httpx
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

# ── Detectar provider ──────────────────────────────────────────────────────────
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GROQ_KEY      = os.getenv("GROQ_API_KEY", "").strip()

if ANTHROPIC_KEY:
    import anthropic
    PROVIDER = "anthropic"
    MODEL    = "claude-haiku-4-5-20251001"
    print("[Provider] Anthropic Claude Haiku")
elif GROQ_KEY:
    from openai import OpenAI
    PROVIDER   = "groq"
    MODEL      = "llama-3.3-70b-versatile"
    OPENAI_URL = "https://api.groq.com/openai/v1"
    OPENAI_KEY = GROQ_KEY
    print(f"[Provider] Groq — {MODEL}")
else:
    from openai import OpenAI
    PROVIDER   = "ollama"
    MODEL      = "qwen2.5:7b"
    OPENAI_URL = "http://localhost:11434/v1"
    OPENAI_KEY = "ollama"
    print("[Provider] Ollama local")

# ── Rutas ──────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent
CONFIG_DIR   = ROOT / "config"
COMPOSIO_KEY = os.environ["COMPOSIO_API_KEY"]

# ── Composio HTTP directo (sin SDK, sin LLM) ───────────────────────────────────
def _composio(slug: str, arguments: dict, entity_id: str) -> dict:
    """Llama a Composio directamente via HTTP. Sin pasar por el LLM."""
    url     = f"https://backend.composio.dev/api/v3.1/tools/execute/{slug}"
    headers = {"x-api-key": COMPOSIO_KEY, "Content-Type": "application/json"}
    payload = {"arguments": arguments, "entity_id": entity_id}
    with httpx.Client(timeout=45) as client:
        resp = client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"{slug} HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if not data.get("successful", True):
        raise RuntimeError(f"{slug} falló: {str(data)[:300]}")
    return data

def _extract_records(data: dict) -> list:
    """Extrae lista de registros del JSON de Composio (estructura data.data o data)."""
    inner = data.get("data", {})
    if isinstance(inner, dict):
        recs = inner.get("data")
        if isinstance(recs, list):
            return recs
    if isinstance(inner, list):
        return inner
    return []

# ── Config AM ──────────────────────────────────────────────────────────────────
def load_am_config(am_id: str) -> dict:
    path = CONFIG_DIR / f"{am_id}.json"
    if not path.exists():
        sys.exit(f"[ERROR] No existe config para '{am_id}'. Crea config/{am_id}.json")
    return json.loads(path.read_text(encoding="utf-8"))

def list_all_ams() -> list:
    return [p.stem for p in CONFIG_DIR.glob("*.json") if p.stem != "am_example"]

def find_am_by_email(email: str) -> dict | None:
    for path in CONFIG_DIR.glob("*.json"):
        if path.stem == "am_example":
            continue
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if cfg.get("email", "").lower() == email.lower():
            return cfg
    return None

# ── PASO 1: Fetch leads / oportunidades del AM ─────────────────────────────────
_FIELDS = {
    "H1": "id,First_Name,Last_Name,Company,Email,Lead_Status,Phone,Owner",
    "H2": "id,Deal_Name,Stage,Amount,Closing_Date,Account_Name,Contact_Name,Owner",
}
_MODULES    = {"H1": "Leads", "H2": "Potentials"}
EXCLUDE_H1  = {"Sin interes", "Descartado", "Lead desechado"}
INCLUDE_H2  = {"Negotiate", "Comprar", "Entregar"}

def fetch_records(herramienta: str, cfg: dict) -> list:
    module      = _MODULES[herramienta]
    owner_email = cfg["email"]
    entity_id   = cfg["composio_entity_id"]

    all_records = []
    page = 1
    while page <= 5:                        # máx 5 páginas × 200 = 1 000 registros org
        data    = _composio("ZOHO_GET_ZOHO_RECORDS", {
            "module_api_name": module,
            "fields": _FIELDS[herramienta],
            "per_page": 200,
            "page": page,
        }, entity_id)
        records = _extract_records(data)

        mine = [r for r in records
                if isinstance(r.get("Owner"), dict)
                and r["Owner"].get("email","").lower() == owner_email.lower()]
        all_records.extend(mine)

        try:
            more = data["data"]["info"].get("more_records", False)
        except (KeyError, TypeError):
            more = False

        print(f"  [fetch] p{page}: {len(records)} org, {len(mine)} propios, more={more}")
        if not more or len(records) == 0:
            break
        page += 1

    # Filtrar por status / stage
    if herramienta == "H1":
        active = [r for r in all_records if r.get("Lead_Status","") not in EXCLUDE_H1]
    else:
        active = [r for r in all_records if r.get("Stage","") in INCLUDE_H2]

    print(f"  [fetch] {len(all_records)} totales → {len(active)} activos")
    return active

# ── PASO 2: Fetch notas CRM de cada registro ───────────────────────────────────
def fetch_notes(record_id: str, module: str, entity_id: str) -> list:
    try:
        data = _composio("ZOHO_GET_RELATED_RECORDS", {
            "module_api_name": module,
            "record_id": record_id,
            "related_list_api_name": "Notes",
            "fields": "id,Note_Title,Note_Content,Created_Time",
            "per_page": 2,
            "sort_by": "Created_Time",
            "sort_order": "desc",
        }, entity_id)
        return _extract_records(data)
    except Exception as e:
        print(f"  [notes] {record_id}: {e}")
        return []

# ── PASO 2b: Fetch emails de contactos (solo H2) ───────────────────────────────
def fetch_contact_emails(contact_ids: list, entity_id: str) -> dict:
    if not contact_ids:
        return {}
    try:
        data    = _composio("ZOHO_GET_ZOHO_RECORDS", {
            "module_api_name": "Contacts",
            "ids": list(set(contact_ids)),
            "fields": "id,Full_Name,Email",
        }, entity_id)
        records = _extract_records(data)
        return {r["id"]: r.get("Email","") for r in records if r.get("id")}
    except Exception as e:
        print(f"  [contacts] {e}")
        return {}

# ── PASO 3: UNA sola llamada al LLM para generar texto ─────────────────────────
def generate_content(herramienta: str, cfg: dict, records: list, fecha: str) -> list:
    """Genera asuntos, cuerpos de email y notas CRM para todos los registros de una vez."""

    tipo  = "Lead" if herramienta == "H1" else "Oportunidad"
    firma = f"{cfg['name']} / {cfg['title']} - {cfg['company']} / {cfg['email']}"

    # Construir descripción compacta de cada registro
    items_text = ""
    for r in records:
        if herramienta == "H1":
            items_text += (
                f"\nID:{r['id']} | {r.get('First_Name','')} {r.get('Last_Name','')} | "
                f"{r.get('Company','')} | {r.get('Email','')} | Status:{r.get('Lead_Status','')}\n"
            )
        else:
            items_text += (
                f"\nID:{r['id']} | {r.get('Deal_Name','')} | {r.get('Account_Name','')} | "
                f"Stage:{r.get('Stage','')} | ${r.get('Amount','')} | "
                f"Cierre:{r.get('Closing_Date','')} | Email:{r.get('contact_email','')}\n"
            )
        notes = r.get("notes", [])
        if notes:
            for n in notes[:2]:
                titulo   = n.get("Note_Title","")
                contenido = str(n.get("Note_Content",""))[:200]
                fecha_n   = str(n.get("Created_Time",""))[:10]
                items_text += f"  Nota [{fecha_n}] {titulo}: {contenido}\n"
        else:
            items_text += "  Sin notas CRM previas\n"

    system_prompt = (
        f"Eres asistente de ventas de {cfg['name']}, {cfg['title']} en {cfg['company']}.\n"
        f"Fecha: {fecha}. Firma: {firma}\n"
        f"Responde SOLO con JSON válido (array), sin markdown ni texto adicional."
    )

    user_prompt = f"""Genera email de seguimiento y nota CRM para cada {tipo}.

{items_text}

Devuelve este array JSON exacto (un objeto por {tipo}):
[
  {{
    "id": "ID_EXACTO",
    "subject": "Asunto del email (conciso, referencia contexto real)",
    "body": "Cuerpo del email: 3 párrafos (contexto CRM + acción según status/stage + siguiente paso). Firma al final: {firma}",
    "crm_note": "Texto breve: qué se preparó y por qué"
  }}
]

Reglas: usa info real de notas CRM si existen. Stage Negotiate=cierre/ajustes, Comprar=orden/facturación, Entregar=coordinación. Español profesional."""

    print(f"  [LLM] Generando contenido para {len(records)} registros...")

    try:
        if PROVIDER == "anthropic":
            client   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            response = client.messages.create(
                model=MODEL, max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            text = response.content[0].text

        else:  # groq / ollama
            client   = OpenAI(base_url=OPENAI_URL, api_key=OPENAI_KEY)
            response = client.chat.completions.create(
                model=MODEL, max_tokens=4000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ]
            )
            text = response.choices[0].message.content or ""

        # Extraer array JSON de la respuesta
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        return json.loads(text)

    except Exception as e:
        print(f"  [LLM] Error: {e} — usando contenido genérico")
        return [
            {
                "id": r["id"],
                "subject": f"Seguimiento - {r.get('Company', r.get('Account_Name',''))}",
                "body": f"Estimado/a,\n\nEspero que se encuentre bien. Me pongo en contacto para dar seguimiento.\n\nQuedo a su disposición.\n\n{firma}",
                "crm_note": f"Seguimiento preparado - {fecha}",
            }
            for r in records
        ]

# ── PASO 4: Crear borradores en Outlook ───────────────────────────────────────
def create_draft(to_email: str, subject: str, body: str, entity_id: str) -> bool:
    try:
        _composio("OUTLOOK_CREATE_DRAFT", {
            "to_recipients": [to_email],
            "subject": subject,
            "body": body,
        }, entity_id)
        return True
    except Exception as e:
        print(f"  [draft] Error: {e}")
        return False

# ── PASO 5: Crear notas CRM en Zoho ───────────────────────────────────────────
def create_crm_note(module: str, record_id: str, title: str, content: str, entity_id: str) -> bool:
    try:
        _composio("ZOHO_CREATE_ZOHO_RECORD", {
            "module_api_name": "Notes",
            "data": {
                "Note_Title": title,
                "Note_Content": content,
                "se_module": module,
                "Parent_Id": record_id,
            }
        }, entity_id)
        return True
    except Exception as e:
        print(f"  [crm_note] Error: {e}")
        return False

# ── Runner principal ───────────────────────────────────────────────────────────
def run_herramienta(herramienta: str, cfg: dict) -> str:
    if herramienta not in ("H1", "H2"):
        return f"[ERROR] Herramienta {herramienta} no soportada en esta versión."

    fecha     = datetime.date.today().strftime("%Y-%m-%d")
    entity_id = cfg["composio_entity_id"]
    module    = _MODULES[herramienta]
    h_num     = "1" if herramienta == "H1" else "2"

    print(f"\n[{fecha}] {herramienta} → {cfg['name']} ({cfg['email']})")

    # PASO 1: Obtener registros activos del AM
    active = fetch_records(herramienta, cfg)
    if not active:
        return f"{herramienta} [{fecha}] · procesados:0 · sin registros activos para {cfg['email']}"

    # PASO 2: Notas CRM en paralelo (ahorra tiempo)
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_notes, r["id"], module, entity_id): r for r in active}
        for future in as_completed(futures):
            futures[future]["notes"] = future.result()

    # PASO 2b: Emails de contactos para H2
    if herramienta == "H2":
        contact_ids = [
            r["Contact_Name"]["id"]
            for r in active
            if isinstance(r.get("Contact_Name"), dict) and r["Contact_Name"].get("id")
        ]
        email_map = fetch_contact_emails(contact_ids, entity_id)
        for r in active:
            cn = r.get("Contact_Name")
            r["contact_email"] = email_map.get(cn.get("id","") if isinstance(cn, dict) else "", "")

    # PASO 3: UNA llamada al LLM para generar todo el contenido
    content_list = generate_content(herramienta, cfg, active, fecha)
    content_map  = {c["id"]: c for c in content_list}

    # PASO 4 + 5: Crear borradores y notas CRM
    borradores = notas = sin_email = errores = 0
    output_lines = []

    for r in active:
        rid     = r["id"]
        content = content_map.get(rid, {})

        if herramienta == "H1":
            name    = f"{r.get('First_Name','')} {r.get('Last_Name','')}".strip()
            company = r.get("Company","")
            status  = r.get("Lead_Status","")
            email   = r.get("Email","")
        else:
            name    = r.get("Deal_Name","")
            company = r.get("Account_Name","")
            status  = r.get("Stage","")
            email   = r.get("contact_email","")

        subject  = content.get("subject", f"Seguimiento - {company}")
        body     = content.get("body","")
        crm_text = content.get("crm_note", f"Seguimiento preparado - {fecha}")

        # Borrador Outlook
        if email:
            if create_draft(email, subject, body, entity_id):
                borradores += 1
            else:
                errores += 1
        else:
            sin_email += 1

        # Nota CRM
        note_title = f"Seguimiento preparado - {fecha} (Herramienta {h_num})"
        if create_crm_note(module, rid, note_title, crm_text, entity_id):
            notas += 1
        else:
            errores += 1

        output_lines.append(
            f"• {name} — {company} — {status}\n"
            f"  📧 Borrador: \"{subject}\"\n"
            f"  📝 Nota CRM: \"{crm_text[:100]}\""
        )

    summary = (
        f"{herramienta} [{fecha}] · procesados:{len(active)} · "
        f"borradores:{borradores} · notas:{notas} · "
        f"sin_email:{sin_email} · errores:{errores}"
    )
    detail = "\n\n".join(output_lines)
    result = f"{summary}\n\nRegistros procesados:\n{detail}"
    print(result)
    return result


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Asistente de Ventas BEST")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--am",  help="ID del AM (nombre del JSON en config/)")
    group.add_argument("--all", action="store_true", help="Todos los AMs")
    parser.add_argument("--herramienta", default="H1",
                        help="H1, H2 o combinaciones como H1,H2")
    args = parser.parse_args()

    herramientas = [h.strip().upper() for h in args.herramienta.split(",")]
    ams = list_all_ams() if args.all else [args.am]
    for am_id in ams:
        cfg = load_am_config(am_id)
        for h in herramientas:
            run_herramienta(h, cfg)

if __name__ == "__main__":
    main()
