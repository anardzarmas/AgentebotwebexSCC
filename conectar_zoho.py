"""
Conecta Zoho CRM al entity correcto — Composio 0.13.0
Corre UNA SOLA VEZ por AM.
"""
from dotenv import load_dotenv
from composio import Composio
from composio_anthropic import AnthropicProvider

load_dotenv()

ENTITY_ID = "pg-test-9vk8GTz7Le0dQ00HghFWasyO53tNRbaw"  # mismo entity que Outlook

composio = Composio(provider=AnthropicProvider())
session  = composio.create(user_id=ENTITY_ID)
conn     = session.authorize(toolkit="zoho")

print(f"\n✅ Abre esta URL en tu navegador para autorizar Zoho:\n")
print(f"   {conn.redirect_url}\n")
print("Después de autorizar, verifica en Composio → Users que el entity")
print(f"'{ENTITY_ID}' tenga Zoho y Outlook activos.\n")
