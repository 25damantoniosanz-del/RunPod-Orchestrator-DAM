import json
import time
import numpy as np
import random 
from urllib import request, error

# --- CONFIGURACIÓN ---
ITERACIONES = 10               

# --- CONFIGURACIÓN DE URL ---
url_input = input("Introduce la URL del Pod (Enter para local 127.0.0.1:8188): ").strip()

if not url_input:
    COMFY_URL = "http://127.0.0.1:8188"
else:
    COMFY_URL = url_input.rstrip("/")
    if not COMFY_URL.startswith("http"):
        COMFY_URL = f"https://{COMFY_URL}"

print(f"🎯 Apuntando a: {COMFY_URL}")

# HEADERS (Disfraz de navegador)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "*/*"
}

def get_available_model():
    """Pregunta al servidor qué modelos tiene instalados."""
    try:
        req = request.Request(f"{COMFY_URL}/object_info/CheckpointLoaderSimple", headers=HEADERS)
        with request.urlopen(req) as response:
            data = json.loads(response.read())
            # RunPod suele tener SDXL o v1.5. Cogemos el primero de la lista.
            modelos = data['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
            if modelos:
                print(f"✅ Modelo detectado en servidor: {modelos[0]}")
                return modelos[0]
            return None
    except Exception as e:
        print(f"⚠️ No pude detectar modelos automáticamente: {e}")
        return None

def build_workflow(model_name):
    """Crea un workflow básico en memoria usando el modelo detectado."""
    # Este es un flujo estándar Txt2Img que funciona en cualquier ComfyUI
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 8, "denoise": 1, "latent_image": ["5", 0], "model": ["4", 0],
                "negative": ["7", 0], "positive": ["6", 0], "sampler_name": "euler",
                "scheduler": "normal", "seed": 0, "steps": 20
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": { "ckpt_name": model_name }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": { "batch_size": 1, "height": 512, "width": 512 }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": { "clip": ["4", 1], "text": "landscape of a futuristic city, high quality" }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": { "clip": ["4", 1], "text": "bad quality, blurred" }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": { "samples": ["3", 0], "vae": ["4", 2] }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": { "filename_prefix": "Benchmark_RunPod", "images": ["8", 0] }
        }
    }

def queue_prompt(workflow):
    p = {"prompt": workflow}
    data = json.dumps(p).encode('utf-8')
    req = request.Request(f"{COMFY_URL}/prompt", data=data, headers=HEADERS)
    try:
        response = request.urlopen(req)
        return json.loads(response.read())
    except error.HTTPError as e:
        print(f"❌ Error HTTP {e.code}: {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"❌ Error conexión: {e}")
        return None

def get_history(prompt_id):
    try:
        req = request.Request(f"{COMFY_URL}/history/{prompt_id}", headers=HEADERS)
        with request.urlopen(req) as response:
            return json.loads(response.read())
    except:
        return {}

def run_benchmark():
    print("🔍 Analizando servidor remoto...")
    model_name = get_available_model()
    
    if not model_name:
        print("❌ No encontré ningún modelo checkpoints en el servidor. ¿Está vacío?")
        return

    # Generamos el workflow dinámicamente
    workflow = build_workflow(model_name)
    
    print(f"🚀 Iniciando Benchmark ({ITERACIONES} iteraciones)...")
    tiempos = []

    for i in range(ITERACIONES):
        # Anti-Caché: Cambiar semilla y texto
        semilla = int(time.time() * 1000) + i
        workflow["3"]["inputs"]["seed"] = semilla
        workflow["6"]["inputs"]["text"] = f"landscape of a futuristic city, high quality --no_cache_{semilla}"

        start_time = time.time()
        
        response = queue_prompt(workflow)
        if not response: 
            print("❌ Fallo al enviar prompt. Abortando.")
            break
            
        prompt_id = response['prompt_id']
        
        while True:
            history = get_history(prompt_id)
            if prompt_id in history:
                break
            time.sleep(0.1)
            
        duration = time.time() - start_time
        tiempos.append(duration)
        print(f"   Iteración {i+1}: {duration:.2f}s")

    if tiempos:
        avg_time = np.mean(tiempos)
        print("\n" + "="*40)
        print(f"📊 RESULTADOS FINALES ({model_name})")
        print("="*40)
        print(f"Tiempo Medio:   {avg_time:.2f} s")
        print("="*40)

if __name__ == "__main__":
    run_benchmark()