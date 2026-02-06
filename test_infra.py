import time
import runpod
# Importamos tus funciones del archivo main.py
from main import create_worker_pod, stop_worker_pod

def probar_infraestructura():
    print("--- ☁️ PRUEBA DE INFRAESTRUCTURA REAL (RUNPOD) ---")
    print("⚠️  AVISO: Esto creará una máquina real y costará unos céntimos.")
    
    # 1. Crear Máquina
    print("\n1. Solicitando Pod a RunPod (Esto puede tardar 2-3 min)...")
    try:
        # Usamos la función de tu librería main.py
        pod_id = create_worker_pod()
        print(f"✅ POD CREADO CON ÉXITO. ID: {pod_id}")
    except Exception as e:
        print(f"❌ Error creando Pod: {e}")
        return

    # 2. Esperar un poco (Simulación de uso)
    print("\n2. Esperando 30 segundos para verificar que no se apaga solo...")
    time.sleep(30)
    
    # 3. Destruir Máquina (IMPORTANTE)
    print(f"\n3. Destruyendo Pod {pod_id} para detener cobro...")
    stop_worker_pod(pod_id)
    print("✅ POD DESTRUIDO. Prueba finalizada correctamente.")

if __name__ == "__main__":
    # Asegúrate de que tu API Key esté configurada en main.py o en variables de entorno
    probar_infraestructura()