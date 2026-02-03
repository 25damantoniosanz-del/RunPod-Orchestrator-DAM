import runpod
import os
import time
from dotenv import load_dotenv

# --- CONFIGURACIÓN INICIAL ---
# Cargar variables de entorno desde .env
load_dotenv()
api_key = os.getenv("RUNPOD_API_KEY")

if not api_key:
    raise ValueError("❌ ERROR: No se encontró RUNPOD_API_KEY en el archivo .env")

runpod.api_key = api_key

# --- FUNCIONES DE ORQUESTACIÓN ---

def test_connection():
    """Verifica que la API Key funciona y tenemos saldo/acceso."""
    try:
        user = runpod.get_user()
        print(f"✅ Conexión ÉXITO. Saldo: ${user.get('credit', 0)}")
        
        # Listar GPUs
        gpus = runpod.get_gpus()
        if gpus:
            # Cogemos la primera para ver qué tiene dentro
            gpu_ejemplo = gpus[0]
            
            # INTENTO DE RECUPERAR PRECIO DE FORMA SEGURA
            # RunPod a veces cambia 'communityPrice' por 'communitySpotPrice' o similar.
            # Esto busca el precio, y si no está, pone "N/A" en vez de fallar.
            precio = gpu_ejemplo.get('communityPrice', gpu_ejemplo.get('minSpotPrice', 'N/A'))
            nombre = gpu_ejemplo.get('id', 'GPU Desconocida')
            
            print(f"👀 GPU Detectada: {nombre} - Precio aprox: ${precio}/hr")
        else:
            print("⚠️ Conexión buena, pero no se devolvió lista de GPUs (¿Filtros activados?)")
            
        return True
    except Exception as e:
        # Imprimimos el error completo para debug
        print(f"❌ Error de conexión (Detalle): {e}")
        return False

def create_worker_pod():
    """
    Crea un Pod en Community Cloud.
    NOTA: Esta función GASTA SALDO real. Úsala con precaución.
    """
    print("🚀 Iniciando despliegue de Pod...")
    try:
        pod = runpod.create_pod(
            name="Worker-DAM-Proyecto",
            image_name="runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel",
            gpu_type_id="NVIDIA GeForce RTX 4090", 
            cloud_type="COMMUNITY", 
            gpu_count=1,
            volume_in_gb=20,
            ports="8188/http", # Puerto típico de ComfyUI
            # terminate_after=10 # OJO: Esto apagaría el pod a los 10 mins (seguridad)
        )
        print(f"✅ Pod creado con ID: {pod['id']}")
        return pod['id']
    except Exception as e:
        print(f"❌ Error al crear Pod: {e}")
        return None

def stop_worker_pod(pod_id):
    """Detiene un pod para no consumir GPU (aunque cobra disco)."""
    try:
        runpod.stop_pod(pod_id)
        print(f"🛑 Pod {pod_id} detenido correctamente.")
    except Exception as e:
        print(f"⚠️ No se pudo detener el pod: {e}")

# --- EJECUCIÓN DEL SCRIPT ---
if __name__ == "__main__":
    print("--- INICIANDO SISTEMA DE ORQUESTACIÓN ---")
    
    # 1. Test de conexión
    if test_connection():
        print("\n--- TEST SUPERADO: Entorno listo ---")
        
        # PASO CRITICO: Descomenta las siguientes líneas SOLO si quieres crear una máquina real
        # y tienes saldo en la cuenta ($5 min).
        
        # nuevo_pod_id = create_worker_pod()
        # if nuevo_pod_id:
        #     print("Esperando 10 segundos antes de apagar...")
        #     time.sleep(10)
        #     stop_worker_pod(nuevo_pod_id)
        
    else:
        print("Revisa tu API Key en el archivo .env")