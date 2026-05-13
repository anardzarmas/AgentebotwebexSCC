"""
Asistente de Ventas BEST — Agente autónomo multi-AM
Uso:
  python agent.py --am agarcen --herramienta H1
  python agent.py --am agarcen --herramienta H1,H2,H3   # ejecuta en secuencia
  python agent.py --all --herramienta H1                 # todos los AMs

Variables de entorno requeridas:
  ANTHROPIC_API_KEY   — Claude API key
  COMPOSIO_API_KEY    — Composio API key
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from composio_anthropic import ComposioToolSet, App

load_dotenv()

# ── Rutas ────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
SKILLS_DIR = ROOT / "skills"
CONFIG_DIR = ROOT / "config"
MASTER_TPL = SKILLS_DIR / "HERRAMIENTAS-BEST-MASTER.md"
SKILL_FILES = {
    "H1": SKILLS_DIR / "herramienta-1-leads"        / "SKILL.md",
    "H2": SKILLS_DIR / "herramienta-2-oportunidades" / "SKILL.md",
    "H3": SKILLS_DIR / "herramienta-3-reporte"       / "SKILL.md",
}

MODEL      = "claude-sonnet-4-6"
MAX_TOKENS = 8096


# ── Config AM ─────────────────────────────────────────────────────────────────
def load_am_config(am_id: str) -> dict:
    """Carga config/{am_id}.json y valida campos requeridos."""
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
    """Lista todos los AMs configurados (excluye am_example.json)."""
    return [
        p.stem for p in CONFIG_DIR.glob("*.json")
        if p.stem != "am_example"
    ]


def find_am_by_email(email: str) -> dict | None:
    """Busca la config de un AM por su email. Usado por el bot de Webex."""
    for path in CONFIG_DIR.glob("*.json"):
        if path.stem == "am_example":
            continue
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if cfg.get("email", "").lower() == email.lower():
            return cfg
    return None


# ── Skill builder ─────────────────────────────────────────────────────────────
def build_system_prompt(herramienta: str, cfg: dict) -> str:
    """Combina MASTER.md + SKILL.md y sustituye {{placeholders}} con datos del AM."""
    master = MASTER_TPL.read_text(encoding="utf-8")
    skill  = SKILL_FILES[herramienta].read_text(encoding="utf-8")
    combined = f"{master}\n\n---\n\n{skill}"
    for key, value in cfg.items():
        combined = combined.replace(f"{{{{{key}}}}}", str(value))
    return combined


# ── Agentic loop ──────────────────────────────────────────────────────────────
def run_herramienta(herramienta: str, cfg: dict):
    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    toolset = ComposioToolSet(
        api_key=os.environ["COMPOSIO_API_KEY"],
        entity_id=cfg["composio_entity_id"],
    )
    tools   = toolset.get_tools(apps=[App.ZOHOCRM, App.OUTLOOK])

    fecha        = datetime.date.today().strftime("%Y-%m-%d")
    system_prompt = build_system_prompt(herramienta, cfg)
    user_prompt   = (
        f"Ejecuta {herramienta} para {cfg['email']}. "
        f"Fecha de hoy: {fecha}. "
        f"Genera el reporte de salida al finalizar."
    )

    messages = [{"role": "user", "content": user_prompt}]
    print(f"\n[{fecha}] {herramienta} → {cfg['name']} ({cfg['email']})")

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = toolset.handle_tool_calls(response)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})
            continue

        # Respuesta final
        final_text = next((b.text for b in response.content if hasattr(b, "text")), "")
        print(final_text)

        # Guardar reporte H3
        if herramienta == "H3":
            am_id       = cfg["composio_entity_id"]
            report_path = ROOT / f"Reporte_Herramientas_{am_id}_{fecha}.md"
            report_path.write_text(final_text, encoding="utf-8")
            print(f"Reporte guardado: {report_path}")

        return final_text  # ← devuelve el texto para que el bot lo mande al chat


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Asistente de Ventas BEST")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--am",  help="ID del AM (nombre del archivo JSON en config/)")
    group.add_argument("--all", action="store_true", help="Ejecutar para todos los AMs")
    parser.add_argument(
        "--herramienta", default="H1",
        help="Herramienta(s) a ejecutar: H1, H2, H3 o combinaciones como H1,H2"
    )
    args = parser.parse_args()

    herramientas = [h.strip().upper() for h in args.herramienta.split(",")]
    invalid = [h for h in herramientas if h not in SKILL_FILES]
    if invalid:
        sys.exit(f"[ERROR] Herramientas no reconocidas: {invalid}. Usa H1, H2 o H3.")

    ams = list_all_ams() if args.all else [args.am]

    for am_id in ams:
        cfg = load_am_config(am_id)
        for h in herramientas:
            run_herramienta(h, cfg)


if __name__ == "__main__":
    main()
