import runpod
import os
import time
from dotenv import load_dotenv


# --- 3. CATÁLOGO DE IMÁGENES (Configuración) ---
# Definimos las imágenes aquí para no tener "números mágicos" por el código.
# Estrategia: Usamos tags específicos (v4.0.1) en lugar de 'latest' para evitar roturas.

IMAGENES_DOCKER = {
    "IMAGEN_ESTANDAR": "ashleykleynhans/runpod-comfyui:2.1.0", # Ejemplo de imagen popular de Comfy
    "VIDEO_HIGH_MEM":  "runpod/stable-diffusion:comfy-video-v1", # (Inventada para el ejemplo)
    "DEV_BASE":        "runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel"
}

# Variable de configuración actual (Esto permite el ROLLBACK rápido)
# Si la versión nueva falla, solo cambiamos esta línea a "DEV_BASE" y redeplegamos.
IMAGEN_ACTUAL_PRODUCCION = IMAGENES_DOCKER["IMAGEN_ESTANDAR"]


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

def create_worker_pod(tipo_trabajo="imagen"):
    """
    Crea un Pod usando la imagen definida en el catálogo.
    """
    # Selección inteligente de imagen
    if tipo_trabajo == "video":
        imagen_a_usar = IMAGENES_DOCKER["VIDEO_HIGH_MEM"]
        gpu_id = "NVIDIA A100 80GB PCIe" # Vídeo pide más VRAM
    else:
        imagen_a_usar = IMAGENES_DOCKER["IMAGEN_ESTANDAR"] # Usamos la versión "Pinned"
        gpu_id = "NVIDIA GeForce RTX 4090"

    print(f"🚀 Desplegando Worker para [{tipo_trabajo}] usando imagen: {imagen_a_usar}...")
    
    try:
        pod = runpod.create_pod(
            name=f"Worker-{tipo_trabajo.capitalize()}",
            image_name=imagen_a_usar,  # <--- AQUÍ USAMOS EL CATÁLOGO
            gpu_type_id=gpu_id, 
            cloud_type="COMMUNITY", 
            gpu_count=1,
            volume_in_gb=40,
            ports="8188/http",
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