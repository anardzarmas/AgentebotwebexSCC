"""
Fuerza la reconexión de Zoho para el entity de Ana.
Elimina la conexión existente (de Diana) y genera una nueva URL de autorización.

Uso:
  python reconectar_zoho.py
"""
import os
from dotenv import load_dotenv
from composio import Composio
from composio_anthropic import AnthropicProvider

load_dotenv()

ENTITY_ID = "pg-test-9vk8GTz7Le0dQ00HghFWasyO53tNRbaw"

composio = Composio(provider=AnthropicProvider())
entity   = composio.get_entity(id=ENTITY_ID)

# 1. Ver conexiones actuales y eliminar la de Zoho
print("Conexiones actuales:")
try:
    connections = entity.get_connections()
    for conn in connections:
        name = getattr(conn, "appName", "") or getattr(conn, "app_name", "") or str(conn)
        print(f"  - {name}")
        if "zoho" in name.lower():
            conn_id = getattr(conn, "id", None)
            if conn_id:
                try:
                    composio.connected_accounts.delete(connection_id=conn_id)
                    print(f"    ✓ Conexión Zoho eliminada (id: {conn_id})")
                except Exception as e:
                    print(f"    ⚠ No se pudo eliminar: {e}")
except Exception as e:
    print(f"  Error listando conexiones: {e}")

# 2. Generar nueva URL de autorización
print("\nGenerando nueva URL de autorización para Zoho...")
try:
    conn = entity.initiate_connection(app_name="zohocrm")
    print(f"\n{'='*60}")
    print("Abre esta URL en una ventana INCÓGNITO:")
    print(f"\n  {conn.redirectUrl}\n")
    print("Inicia sesión con las credenciales de ANA (arodriguez@best.org.mx)")
    print(f"{'='*60}\n")
except Exception as e:
    print(f"Error generando URL: {e}")
    # Intentar con nombre alternativo
    try:
        conn = entity.initiate_connection(app_name="zoho")
        print(f"\nURL (zoho): {conn.redirectUrl}\n")
    except Exception as e2:
        print(f"También falló con 'zoho': {e2}")
