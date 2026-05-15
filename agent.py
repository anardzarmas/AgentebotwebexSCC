"""
Asistente de Ventas BEST — Agente autónomo multi-AM
Composio >= 0.13.0

Providers soportados (detección automática):
  - Anthropic Claude  → si ANTHROPIC_API_KEY está en .env
  - Ollama local      → si no hay ANTHROPIC_API_KEY (requiere ollama corriendo)

Uso:
  python agent.py --am arodriguez --herramienta H1
  python agent.py --am arodriguez --herramienta H1,H2,H3
  python agent.py --all --herramienta H1
"""

import os
import sys
import json
import argparse
import datetime
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Detectar provider ──────────────────────────────────────────────────────────
# Prioridad: Anthropic → Groq → Ollama local
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GROQ_KEY      = os.getenv("GROQ_API_KEY", "").strip()

if ANTHROPIC_KEY:
    import anthropic
    from composio import Composio
    from composio_anthropic import AnthropicProvider
    PROVIDER = "anthropic"
    MODEL    = "claude-haiku-4-5-20251001"   # ~6x más barato que Sonnet, suficiente para tool use
    print("[Provider] Anthropic Claude Haiku")
elif GROQ_KEY:
    from openai import OpenAI
    from composio import Composio
    from composio_openai import OpenAIProvider
    PROVIDER   = "groq"
    MODEL      = "llama-3.3-70b-versatile"
    OPENAI_URL = "https://api.groq.com/openai/v1"
    OPENAI_KEY = GROQ_KEY
    print(f"[Provider] Groq — {MODEL}")
else:
    from openai import OpenAI
    from composio import Composio
    from composio_openai import OpenAIProvider
    PROVIDER   = "ollama"
    MODEL      = "llama3.2"
    OPENAI_URL = "http://localhost:11434/v1"
    OPENAI_KEY = "ollama"
    print("[Provider] Ollama local — llama3.2")

# ── Rutas ──────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
SKILLS_DIR = ROOT / "skills"
CONFIG_DIR = ROOT / "config"
MASTER_TPL = SKILLS_DIR / "HERRAMIENTAS-BEST-MASTER.md"
SKILL_FILES = {
    "H1": SKILLS_DIR / "herramienta-1-leads"        / "SKILL.md",
    "H2": SKILLS_DIR / "herramienta-2-oportunidades" / "SKILL.md",
    "H3": SKILLS_DIR / "herramienta-3-reporte"       / "SKILL.md",
}
MAX_TOKENS = 8192   # espacio suficiente para múltiples tool_use blocks en paralelo
MAX_ITER   = 25     # tope de seguridad para el agentic loop

_composio = None

def get_composio():
    global _composio
    if _composio is None:
        provider  = AnthropicProvider() if PROVIDER == "anthropic" else OpenAIProvider()
        _composio = Composio(provider=provider)
    return _composio


# Slugs por herramienta — solo se cargan los necesarios para ahorrar tokens
TOOL_SLUGS = {
    "H1": ["ZOHO_GET_ZOHO_RECORDS", "ZOHO_GET_RELATED_RECORDS",
           "ZOHO_CREATE_ZOHO_RECORD", "OUTLOOK_CREATE_DRAFT"],
    "H2": ["ZOHO_GET_ZOHO_RECORDS", "ZOHO_GET_RELATED_RECORDS",
           "ZOHO_CREATE_ZOHO_RECORD", "OUTLOOK_CREATE_DRAFT"],
    "H3": ["ZOHO_GET_ZOHO_RECORDS", "ZOHO_GET_RELATED_RECORDS",
           "ZOHO_SEARCH_ZOHO_RECORDS"],
}


# ── Config AM ──────────────────────────────────────────────────────────────────
def load_am_config(am_id: str) -> dict:
    path = CONFIG_DIR / f"{am_id}.json"
    if not path.exists():
        sys.exit(f"[ERROR] No existe config para '{am_id}'. Crea config/{am_id}.json")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    required = ["email","name","title","company","zoho_org_id",
                "zoho_view_leads","zoho_view_potentials","composio_entity_id"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        sys.exit(f"[ERROR] Faltan campos en config/{am_id}.json: {missing}")
    return cfg


def list_all_ams() -> list[str]:
    return [p.stem for p in CONFIG_DIR.glob("*.json") if p.stem != "am_example"]


def find_am_by_email(email: str) -> dict | None:
    for path in CONFIG_DIR.glob("*.json"):
        if path.stem == "am_example":
            continue
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if cfg.get("email", "").lower() == email.lower():
            return cfg
    return None


# ── Skill builder ──────────────────────────────────────────────────────────────
def build_system_prompt(herramienta: str, cfg: dict) -> str:
    master   = MASTER_TPL.read_text(encoding="utf-8")
    skill    = SKILL_FILES[herramienta].read_text(encoding="utf-8")
    combined = f"{master}\n\n---\n\n{skill}"
    for key, value in cfg.items():
        combined = combined.replace(f"{{{{{key}}}}}", str(value))
    return combined


# ── Loops por provider ─────────────────────────────────────────────────────────
def _apply_cache_control(tools: list) -> list:
    """Marca el último tool con cache_control para que Anthropic cachee todo el bloque."""
    import copy
    tools = copy.deepcopy(tools)
    if tools:
        tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools


def _run_anthropic(herramienta: str, cfg: dict, system_prompt: str,
                   user_prompt: str, composio, tools) -> str:
    import time, re
    from anthropic import RateLimitError

    client   = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_id  = cfg["composio_entity_id"]
    messages = [{"role": "user", "content": user_prompt}]
    iters    = 0

    # Cachear system prompt y tools entre iteraciones (90% descuento en lecturas)
    cached_system = [
        {"type": "text", "text": system_prompt,
         "cache_control": {"type": "ephemeral"}}
    ]
    cached_tools = _apply_cache_control(tools)

    while iters < MAX_ITER:
        iters += 1
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS,
                system=cached_system, tools=cached_tools, messages=messages,
            )
        except RateLimitError as e:
            msg = str(e)
            # Intentar extraer tiempo de espera del mensaje de error
            m = re.search(r"try again in (\d+)m(\d+(?:\.\d+)?)", msg)
            if m:
                wait = int(m.group(1)) * 60 + float(m.group(2)) + 5
            else:
                m2 = re.search(r"try again in (\d+(?:\.\d+)?)s", msg)
                wait = float(m2.group(1)) + 5 if m2 else 65
            print(f"[Rate limit Anthropic] Esperando {int(wait)}s antes de reintentar... (iter {iters})")
            time.sleep(wait)
            iters -= 1  # no contar el intento fallido
            continue

        if response.stop_reason == "tool_use":
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            # Forzar criteria y per_page en ZOHO_GET_ZOHO_RECORDS antes de ejecutar
            for block in tool_blocks:
                if block.name == "ZOHO_GET_ZOHO_RECORDS":
                    module = block.input.get("module_api_name", "")
                    if module in ("Leads", "Potentials"):
                        block.input.pop("cvid", None)          # cvid conflicta con criteria
                        block.input.pop("page_token", None)    # evitar paginación infinita
                        block.input["criteria"] = f"(Owner.email:equals:{cfg['email']})"
                        block.input["per_page"]  = 50
                        block.input["page"]      = 1           # siempre página 1 con criteria
                        print(f"  [force-filter] criteria inyectado → {module} owner={cfg['email']}")
            results     = composio.provider.handle_tool_calls(user_id=user_id, response=response)
            n_tools     = len(tool_blocks)
            print(f"  [iter {iters}] {n_tools} tool call(s): {[b.name for b in tool_blocks]}")
            # Filtrar por owner ANTES de que Claude vea los resultados
            filtered_results = []
            for i, r in enumerate(results):
                text = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
                if tool_blocks[i].name == "ZOHO_GET_ZOHO_RECORDS":
                    # LOG: qué argumentos mandó Claude a Zoho
                    print(f"  [DEBUG] args enviados a Zoho: {json.dumps(tool_blocks[i].input, ensure_ascii=False)}")
                    # LOG: qué viene exactamente en la respuesta de Zoho
                    try:
                        raw     = json.loads(text)
                        records = _extract_zoho_records(raw) or []
                        print(f"  [DEBUG] registros en respuesta: {len(records)}")
                        for rec in records[:5]:
                            owner = rec.get("Owner", {})
                            email = owner.get("email", "N/A") if isinstance(owner, dict) else str(owner)
                            print(f"  [DEBUG] lead: {rec.get('Last_Name','?')} | owner: {email}")
                    except Exception as e:
                        print(f"  [DEBUG] ERROR: {e} | raw: {str(text)[:300]}")
                    text = _filter_by_owner(text, cfg["email"])
                filtered_results.append(_truncate_result(text))
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": tool_blocks[i].id,
                     "content": filtered_results[i]}
                    for i in range(len(tool_blocks))
                ],
            })
            continue

        print(f"  [iter {iters}] stop_reason={response.stop_reason}")
        return next((b.text for b in response.content if hasattr(b, "text")), "")

    return f"[ERROR] Se alcanzó el límite de {MAX_ITER} iteraciones sin completar {herramienta}."


def _extract_zoho_records(parsed: dict) -> list | None:
    """Extrae la lista de registros del JSON de Composio (estructura data.data o data)."""
    # Composio envuelve: {"data": {"data": [...], ...}, "successful": ...}
    inner = parsed.get("data", {})
    if isinstance(inner, dict):
        records = inner.get("data")
        if isinstance(records, list):
            return records
    if isinstance(inner, list):
        return inner
    return None


def _filter_by_owner(result_text: str, owner_email: str) -> str:
    """Filtra resultados de Zoho para incluir SOLO registros del AM correcto.
    Se aplica en Python antes de que Claude vea los datos."""
    try:
        parsed = json.loads(result_text)
        records = _extract_zoho_records(parsed)
        if records is None:
            return result_text
        before   = len(records)
        filtered = [
            r for r in records
            if isinstance(r.get("Owner"), dict)
            and r["Owner"].get("email", "").lower() == owner_email.lower()
        ]
        removed = before - len(filtered)
        if removed > 0:
            print(f"  [owner-filter] Removidos {removed} registros de otros AMs "
                  f"(quedan {len(filtered)} de {owner_email})")
        # Reconstruir con la misma estructura
        parsed["data"]["data"] = filtered
        return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        pass
    return result_text


def _truncate_result(result, max_chars: int = 1500) -> str:
    """Recorta respuestas grandes de herramientas para no inflar el historial."""
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[resultado truncado para ahorrar tokens]"
    return text


_PROP_BLOAT = {"title", "examples", "human_parameter_name",
               "human_parameter_description", "file_uploadable",
               "description", "default", "enum"}   # para Groq: eliminar desc y enum para ahorrar tokens

def _slim_prop(prop: dict) -> dict:
    """Elimina campos de UI y descripciones — el LLM ya sabe qué hacer por el SKILL.md."""
    # Solo conservar type + estructura, sin descripciones ni bloat
    p = {}
    t = prop.get("type")
    if t:
        # Permitir integer o string: los LLMs open-source suelen devolver strings
        p["type"] = ["integer", "string"] if t == "integer" else t
    # Procesar anyOf / oneOf recursivamente (solo tipos)
    for key in ("anyOf", "oneOf"):
        if key in prop:
            p[key] = [_slim_prop(x) if isinstance(x, dict) else x for x in prop[key]]
    if "items" in prop and isinstance(prop["items"], dict):
        p["items"] = _slim_prop(prop["items"])
    if "properties" in prop and isinstance(prop["properties"], dict):
        p["properties"] = {k: _slim_prop(v) for k, v in prop["properties"].items()}
    return p


def _clean_tools(tools: list) -> list:
    """Limpia tools para Groq/Ollama: elimina strict, descripciones y reduce tokens al mínimo."""
    import copy
    cleaned = []
    for tool in copy.deepcopy(tools):
        if not isinstance(tool, dict) or "function" not in tool:
            continue
        fn = tool["function"]
        fn.pop("strict", None)
        # Descripción del tool: solo primeras 60 chars (ya describimos en SKILL.md)
        if isinstance(fn.get("description"), str):
            fn["description"] = fn["description"][:60]
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        params["properties"] = {k: _slim_prop(v) for k, v in props.items()}
        # Mantener solo type, properties y required
        for key in list(params.keys()):
            if key not in ("type", "properties", "required"):
                del params[key]
        cleaned.append(tool)
    return cleaned


def _run_ollama(herramienta: str, cfg: dict, system_prompt: str,
                user_prompt: str, composio, tools) -> str:
    import time, re
    from openai import RateLimitError
    client  = OpenAI(base_url=OPENAI_URL, api_key=OPENAI_KEY)
    tools   = _clean_tools(tools)
    user_id = cfg["composio_entity_id"]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]
    iters = 0

    while iters < MAX_ITER:
        iters += 1
        # Reintento automático si hay rate-limit con tiempo de espera en el mensaje
        try:
            response = client.chat.completions.create(
                model=MODEL, tools=tools, messages=messages,
            )
        except RateLimitError as e:
            msg = str(e)
            # Extraer segundos de "Please try again in Xm Ys"
            m = re.search(r"try again in (\d+)m(\d+(?:\.\d+)?)", msg)
            if m:
                wait = int(m.group(1)) * 60 + float(m.group(2)) + 5
            else:
                m2 = re.search(r"try again in (\d+(?:\.\d+)?)s", msg)
                wait = float(m2.group(1)) + 5 if m2 else 65
            print(f"[Rate limit] Esperando {int(wait)}s antes de reintentar...")
            time.sleep(wait)
            iters -= 1  # no contar el intento fallido
            continue

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls":
            results = composio.provider.handle_tool_calls(user_id=user_id, response=response)
            n_tools = len(choice.message.tool_calls)
            print(f"  [iter {iters}] {n_tools} tool call(s): {[tc.function.name for tc in choice.message.tool_calls]}")
            # Groq requiere content como string y tool_calls separado
            messages.append({
                "role": "assistant",
                "content": choice.message.content or "",
                "tool_calls": [tc.model_dump() for tc in choice.message.tool_calls],
            })
            for i, tool_call in enumerate(choice.message.tool_calls):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _truncate_result(results[i] if i < len(results) else {}),
                })
            continue

        print(f"  [iter {iters}] finish_reason={choice.finish_reason}")
        return choice.message.content or ""

    return f"[ERROR] Se alcanzó el límite de {MAX_ITER} iteraciones sin completar {herramienta}."


# ── Pre-fetch directo de Zoho (sin Claude) ────────────────────────────────────
_FIELDS = {
    "H1": "id,First_Name,Last_Name,Company,Email,Lead_Status,Phone,Owner",
    "H2": "id,Deal_Name,Stage,Amount,Closing_Date,Account_Name,Contact_Name,Owner",
}
_MODULES = {"H1": "Leads", "H2": "Potentials"}


def _prefetch_am_records(herramienta: str, cfg: dict) -> list:
    """
    Obtiene los registros del AM directamente desde Composio (HTTP),
    paginando hasta encontrar todos. Filtra por Owner.email en Python.
    Evita que Claude tenga que paginar y elimina alucinaciones.
    """
    module      = _MODULES[herramienta]
    fields      = _FIELDS[herramienta]
    owner_email = cfg["email"]
    entity_id   = cfg["composio_entity_id"]
    api_key     = os.environ["COMPOSIO_API_KEY"]

    url     = "https://backend.composio.dev/api/v3.1/tools/execute/ZOHO_GET_ZOHO_RECORDS"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    all_records = []
    page = 1

    with httpx.Client(timeout=30) as client:
        while page <= 15:                          # tope: 15 páginas × 200 = 3 000 registros
            payload = {
                "arguments": {
                    "module_api_name": module,
                    "fields": fields,
                    "per_page": 200,
                    "page": page,
                },
                "entity_id": entity_id,
            }
            try:
                resp = client.post(url, json=payload, headers=headers)
                print(f"  [prefetch] HTTP {resp.status_code} p{page}")
                if resp.status_code != 200:
                    print(f"  [prefetch] Error body: {resp.text[:300]}")
                    break
                data = resp.json()
                print(f"  [prefetch] keys: {list(data.keys())[:5]}")
            except Exception as e:
                print(f"  [prefetch] Excepción p{page}: {e}")
                break

            records = _extract_zoho_records(data) or []
            filtered = [
                r for r in records
                if isinstance(r.get("Owner"), dict)
                and r["Owner"].get("email", "").lower() == owner_email.lower()
            ]
            all_records.extend(filtered)

            info = {}
            try:
                info = data["data"]["info"]
            except (KeyError, TypeError):
                pass
            more = info.get("more_records", False) if isinstance(info, dict) else False
            print(f"  [prefetch] p{page}: {len(records)} registros org, "
                  f"{len(filtered)} de {owner_email}, more={more}")

            if not more or len(records) == 0:
                break
            page += 1

    print(f"  [prefetch] Total {herramienta}: {len(all_records)} registros de {owner_email}")
    return all_records


# ── Runner principal ───────────────────────────────────────────────────────────
def run_herramienta(herramienta: str, cfg: dict) -> str:
    composio = get_composio()
    user_id  = cfg["composio_entity_id"]
    # Solo las herramientas necesarias para esta herramienta (ahorra tokens)
    tools = composio.tools.get(user_id=user_id, tools=TOOL_SLUGS[herramienta])

    fecha         = datetime.date.today().strftime("%Y-%m-%d")
    system_prompt = build_system_prompt(herramienta, cfg)

    # Pre-fetch registros del AM directamente desde Zoho (sin Claude)
    records_inject = ""
    if herramienta in ("H1", "H2"):
        am_records = _prefetch_am_records(herramienta, cfg)
        if am_records:
            # Para Groq: limitar campos por registro para no inflar el prompt
            if PROVIDER in ("groq", "ollama"):
                keep_h1 = {"id","First_Name","Last_Name","Company","Email","Lead_Status"}
                keep_h2 = {"id","Deal_Name","Stage","Amount","Closing_Date","Account_Name","Contact_Name","Email"}
                keep    = keep_h1 if herramienta == "H1" else keep_h2
                am_records = [{k: v for k, v in r.items() if k in keep} for r in am_records]
            records_inject = (
                f"\n\nREGISTROS PRE-CARGADOS (ya filtrados, NO llamar ZOHO_GET_ZOHO_RECORDS):\n"
                + json.dumps(am_records, ensure_ascii=False, separators=(',', ':'))
            )
            # Quitar ZOHO_GET_ZOHO_RECORDS de las tools para esta ejecución
            tools = [t for t in tools
                     if not (isinstance(t, dict)
                             and t.get("function", {}).get("name") == "ZOHO_GET_ZOHO_RECORDS")]
        else:
            records_inject = f"\n\nNo se encontraron registros activos para {cfg['email']}."

    user_prompt = (
        f"Ejecuta {herramienta} para {cfg['email']}. Fecha de hoy: {fecha}.\n"
        f"Los registros ya están pre-cargados — salta la FASE 1 y empieza desde FASE 2.\n"
        f"En cada fase llama TODAS las herramientas necesarias en UNA SOLA respuesta.\n"
        f"No esperes confirmación entre registros. Al terminar muestra el reporte de salida."
        + records_inject
    )

    print(f"\n[{fecha}] {herramienta} -> {cfg['name']} ({cfg['email']})")

    if PROVIDER == "anthropic":
        final_text = _run_anthropic(herramienta, cfg, system_prompt, user_prompt, composio, tools)
    else:
        final_text = _run_ollama(herramienta, cfg, system_prompt, user_prompt, composio, tools)

    print(final_text)

    if herramienta == "H3":
        report_path = ROOT / f"Reporte_Herramientas_{user_id}_{fecha}.md"
        report_path.write_text(final_text, encoding="utf-8")
        print(f"Reporte guardado: {report_path}")

    return final_text


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Asistente de Ventas BEST")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--am",  help="ID del AM (nombre del JSON en config/)")
    group.add_argument("--all", action="store_true", help="Todos los AMs")
    parser.add_argument("--herramienta", default="H1",
                        help="H1, H2, H3 o combinaciones como H1,H2")
    args = parser.parse_args()

    herramientas = [h.strip().upper() for h in args.herramienta.split(",")]
    invalid = [h for h in herramientas if h not in SKILL_FILES]
    if invalid:
        sys.exit(f"[ERROR] Herramientas no reconocidas: {invalid}")

    ams = list_all_ams() if args.all else [args.am]
    for am_id in ams:
        cfg = load_am_config(am_id)
        for h in herramientas:
            run_herramienta(h, cfg)


if __name__ == "__main__":
    main()
