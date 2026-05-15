"""
Conecta Outlook al entity de Composio — corre UNA SOLA VEZ por AM.
"""
from dotenv import load_dotenv
from composio import Composio
from composio_openai import OpenAIProvider

load_dotenv()

ENTITY_ID = "pg-test-9vk8GTz7Le0dQ00HghFWasyO53tNRbaw"

composio = Composio(provider=OpenAIProvider())
session  = composio.create(user_id=ENTITY_ID)
conn     = session.authorize(toolkit="outlook")

print(f"\nAbre esta URL en tu navegador para autorizar Outlook:\n")
print(f"   {conn.redirect_url}\n")
print("Inicia sesion con el email de Ana: arodriguez@best.org.mx")
print("Despues vuelve a correr el agente.\n")
