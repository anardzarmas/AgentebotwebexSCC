"""
Asistente de Ventas BEST — Bot de Webex
Escucha mensajes de cualquier AM de BEST y ejecuta H1/H2/H3 usando su cuenta.

Variables de entorno:
  WEBEX_BOT_TOKEN     — token del bot en developer.webex.com
  ANTHROPIC_API_KEY   — Claude API key
  COMPOSIO_API_KEY    — Composio API key
"""

import os
import threading
from dotenv import load_dotenv
from webex_bot.webex_bot import WebexBot
from webex_bot.models.command import Command
from webex_bot.models.response import Response
from webexteamssdk import WebexTeamsAPI

from agent import run_herramienta, find_am_by_email

load_dotenv()

webex_api = WebexTeamsAPI(access_token=os.environ["WEBEX_BOT_TOKEN"])

AYUDA = """
👋 **Asistente de Ventas BEST**

Comandos disponibles:
| Comando | Acción |
|---------|--------|
| `H1` | Seguimiento de Leads — borradores en Outlook |
| `H2` | Seguimiento de Oportunidades — borradores en Outlook |
| `H3` | Reporte del día (resumen H1 + H2) |
| `todo` | Ejecuta H1 + H2 + H3 en secuencia |
| `ayuda` | Muestra este mensaje |

Solo escribe el comando y yo me encargo del resto 🚀
"""


def responder_en_background(room_id: str, am_email: str, herramientas: list[str]):
    """Corre el agente en un hilo separado y manda los resultados al chat."""
    cfg = find_am_by_email(am_email)
    if not cfg:
        webex_api.messages.create(
            roomId=room_id,
            markdown=(
                f"⚠️ No encontré tu configuración para **{am_email}**.\n\n"
                "Pide al administrador que agregue tu perfil en `config/`."
            ),
        )
        return

    for h in herramientas:
        webex_api.messages.create(
            roomId=room_id,
            markdown=f"⏳ Ejecutando **{h}** para {cfg['name']}... (1-3 minutos)",
        )
        try:
            resultado = run_herramienta(h, cfg)
            webex_api.messages.create(
                roomId=room_id,
                markdown=f"✅ **{h} completado**\n\n```\n{resultado}\n```",
            )
        except Exception as e:
            webex_api.messages.create(
                roomId=room_id,
                markdown=f"❌ Error en **{h}**: {e}",
            )


# ── Comando base ──────────────────────────────────────────────────────────────
class HerramientaCommand(Command):
    def __init__(self, keyword: str, herramientas: list[str], descripcion: str):
        super().__init__(
            command_keyword=keyword,
            help_message=descripcion,
            chained_commands=[],
        )
        self.herramientas = herramientas

    def execute(self, message, attachment_actions, activity):
        room_id   = activity["target"]["globalId"]
        am_email  = activity["actor"]["emailAddress"]
        threading.Thread(
            target=responder_en_background,
            args=(room_id, am_email, self.herramientas),
            daemon=True,
        ).start()
        return Response()  # respuesta vacía — el hilo manda los mensajes


class AyudaCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="ayuda",
            help_message="Muestra los comandos disponibles",
            chained_commands=[],
        )

    def execute(self, message, attachment_actions, activity):
        r = Response()
        r.text = AYUDA
        return r


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot = WebexBot(
        teams_bot_token=os.environ["WEBEX_BOT_TOKEN"],
        bot_name="Asistente Ventas BEST",
    )
    bot.add_command(HerramientaCommand("H1",   ["H1"],           "Seguimiento de Leads"))
    bot.add_command(HerramientaCommand("H2",   ["H2"],           "Seguimiento de Oportunidades"))
    bot.add_command(HerramientaCommand("H3",   ["H3"],           "Reporte del día"))
    bot.add_command(HerramientaCommand("todo", ["H1","H2","H3"], "Ejecuta H1 + H2 + H3"))
    bot.add_command(AyudaCommand())

    print("Bot BEST iniciado. Escuchando mensajes en Webex...")
    bot.run()
