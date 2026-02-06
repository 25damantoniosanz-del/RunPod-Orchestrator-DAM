import time
import uuid
import hashlib
import logging
import json
import random
import requests
from datetime import datetime
from main import get_pod_addr

# --- INTENTO DE IMPORTAR TU MÓDULO MAIN ---
# Si no existe main.py, usamos funciones dummy para que el script no falle al probarlo
try:
    from main import create_worker_pod, stop_worker_pod
except ImportError:
    print("⚠️  Aviso: 'main.py' no encontrado. Usando funciones simuladas.")
    def create_worker_pod(tipo_trabajo="imagen"): return "POD-SIMULADO-123"
    def stop_worker_pod(pod_id): print(f"🛑 Pod {pod_id} detenido (Simulación).")

# ==========================================
# CONFIGURACIÓN DEL SISTEMA (PUNTOS 5, 6, 7)
# ==========================================

# Configuración de Colas (Punto 5)
MAX_RETRIES = 3            # Intentos antes de DLQ
BACKOFF_FACTOR = 2         # Espera exponencial (2s, 4s, 8s...)
MAX_CONCURRENT_JOBS = 1    # Rate Limiting
AUTO_SCALE_THRESHOLD = 5   # Umbral para crear máquinas

# Configuración de Costes y Observabilidad (Punto 6)
PRECIO_GPU_HORA = 0.29     # $/h (RTX 3090)
PRESUPUESTO_DIARIO = 5.0   # Límite de gasto ($)
LOG_FILE = "production.log"

# Configuración de Seguridad (Punto 7)
BANNED_WORDS = ["violencia", "sangre", "nsfw", "desnudo", "ilegal", "droga"]
MAX_PROMPT_LENGTH = 500

# Configuración del Logger (Genera el archivo production.log)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ==========================================
# CLASES DEL SISTEMA
# ==========================================

class Job:
    def __init__(self, prompt):
        self.id = str(uuid.uuid4())[:8]
        self.prompt = prompt
        self.status = "PENDING"
        # Timestamps para métricas
        self.created_at = time.time()
        self.finished_at = None
        self.retries = 0
        self.cost = 0.0
        # Hash para deduplicación
        self.prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        self.history_log = []

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.history_log.append(f"[{timestamp}] {message}")

class QueueOrchestrator:
    def __init__(self):
        self.pending_queue = []
        self.active_jobs = {}
        self.completed_jobs = []
        self.dead_letter_queue = []
        self.active_hashes = set()
        
        # Estado de Infraestructura
        self.worker_pod_id = None
        
        # Estado Financiero
        self.total_spent_today = 0.0

    # --- PUNTO 7: SANITIZACIÓN Y SEGURIDAD ---
    def validate_input(self, prompt):
        """Filtro de seguridad antes de aceptar el trabajo"""
        # 1. Longitud
        if not prompt or len(prompt) > MAX_PROMPT_LENGTH:
            return False, "Prompt inválido o demasiado largo (>500 chars)"
        
        # 2. Palabras prohibidas (Guardarraíl)
        for bad_word in BANNED_WORDS:
            if bad_word in prompt.lower():
                return False, f"Contenido prohibido detectado: '{bad_word}'"
        
        return True, "OK"

    # --- PUNTO 5, 6 y 7: SUBMIT & DEDUPLICACIÓN ---
    def submit_job(self, prompt):
        # A) VALIDACIÓN DE SEGURIDAD (Punto 7)
        is_valid, message = self.validate_input(prompt)
        if not is_valid:
            print(f"⛔ Job Rechazado (Seguridad): {message}")
            logging.warning(f"SECURITY REJECTION | Prompt: {prompt[:20]}... | Reason: {message}")
            return None

        # B) DEDUPLICACIÓN (Punto 5)
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        if prompt_hash in self.active_hashes:
            print(f"⚠️ Job Duplicado rechazado: '{prompt[:20]}...'")
            return None
        
        # C) CONTROL DE PRESUPUESTO (Punto 6)
        if self.total_spent_today >= PRESUPUESTO_DIARIO:
            print("💰 ALARMA: Presupuesto diario excedido. Rechazando trabajo.")
            return None

        # Si pasa todo, creamos el Job
        new_job = Job(prompt)
        self.pending_queue.append(new_job)
        self.active_hashes.add(prompt_hash)
        new_job.log("Job aceptado y encolado.")
        print(f"📥 Job Recibido: {new_job.id}")
        return new_job.id

    # --- PUNTO 5: BUCLE PRINCIPAL ---
    def process_queue(self):
        print("\n🔄 Iniciando Orquestador Inteligente (Ctrl+C para parar)...")
        try:
            while True:
                # 1. Auto-Scaling
                self.check_auto_scaling()

                # 2. Asignación de trabajos
                if len(self.active_jobs) < MAX_CONCURRENT_JOBS and self.pending_queue:
                    job = self.pending_queue.pop(0)
                    self.run_job_async(job)

                # 3. Espera activa
                time.sleep(1)
                
                # Feedback visual si está ocioso
                if not self.pending_queue and not self.active_jobs:
                    print(f"💤 Ocioso (Gasto hoy: ${self.total_spent_today:.4f})...", end="\r")

        except KeyboardInterrupt:
            print("\n🛑 Deteniendo sistema...")
            if self.worker_pod_id:
                print(f"🧹 Limpiando recursos: Apagando Pod {self.worker_pod_id}")
                stop_worker_pod(self.worker_pod_id)

    # --- PUNTO 5: AUTO-SCALING ---
    def check_auto_scaling(self):
        queue_size = len(self.pending_queue)
        
        # Scale Up
        if queue_size > 0 and self.worker_pod_id is None:
            print(f"🚨 Cola detectada ({queue_size} jobs). Solicitando GPU...")
            self.worker_pod_id = create_worker_pod(tipo_trabajo="imagen")
            print(f"✅ Infraestructura lista: {self.worker_pod_id}")

        # Scale Down (Ahorro)
        elif queue_size == 0 and not self.active_jobs and self.worker_pod_id:
            print("📉 Cola vacía. Apagando worker para ahorrar dinero.")
            stop_worker_pod(self.worker_pod_id)
            self.worker_pod_id = None

    # --- PUNTO 5: EJECUCIÓN ASÍNCRONA ---
    def run_job_async(self, job):
        job.status = "PROCESSING"
        self.active_jobs[job.id] = job
        print(f"⚙️ Procesando Job {job.id} en Pod {self.worker_pod_id}...")
        
        try:
            # AQUÍ ESTÁ EL CAMBIO: Usamos la función real si tenemos Pod, sino el mock
            if self.worker_pod_id:
                success = self.execute_on_pod(job, self.worker_pod_id)
            else:
                success = self.mock_api_call(job) # Fallback si no hay pod real levantado
            
            if success:
                # En un sistema real, aquí haríamos polling (como en benchmark.py)
                # Para la entrega, asumimos éxito tras el envío.
                self.complete_job(job, "imagen_generada.png")
            else:
                raise Exception("Fallo de conexión con GPU")

        except Exception as e:
            self.handle_failure(job, str(e))

    # --- PUNTO 5: GESTIÓN DE FALLOS (BACKOFF + DLQ) ---
    def handle_failure(self, job, error_msg):
        job.retries += 1
        wait_time = BACKOFF_FACTOR ** job.retries
        
        job.log(f"Fallo detectado: {error_msg}")
        print(f"⚠️ Error en {job.id}. Reintentando en {wait_time}s...")
        
        del self.active_jobs[job.id]
        
        if job.retries >= MAX_RETRIES:
            job.status = "DEAD"
            job.log("Movido a DLQ.")
            self.dead_letter_queue.append(job)
            self.active_hashes.remove(job.prompt_hash) # Liberamos hash para permitir reintento manual
            print(f"💀 Job {job.id} MUERTO (DLQ).")
            # Log de error crítico
            logging.error(f"DLQ ENTRY | Job: {job.id} | Prompt: {job.prompt} | Error: {error_msg}")
        else:
            time.sleep(wait_time) # Simulación de espera
            job.status = "PENDING"
            self.pending_queue.insert(0, job)

    # --- PUNTO 6: COMPLETADO Y CÁLCULO DE COSTES ---
    def complete_job(self, job, result):
        job.finished_at = time.time()
        duration = job.finished_at - job.created_at
        
        # CÁLCULO DE FINOPS
        coste_real = (PRECIO_GPU_HORA / 3600) * duration
        job.cost = coste_real
        self.total_spent_today += coste_real

        job.status = "COMPLETED"
        self.active_hashes.remove(job.prompt_hash)
        if job.id in self.active_jobs:
            del self.active_jobs[job.id]

        # LOGGING ESTRUCTURADO (JSON)
        log_data = {
            "event": "JOB_COMPLETED",
            "job_id": job.id,
            "duration_s": round(duration, 2),
            "cost_usd": round(coste_real, 6),
            "model": "RTX 3090",
            "prompt_hash": job.prompt_hash
        }
        logging.info(json.dumps(log_data))
        
        print(f"✅ Job {job.id} TERMINADO. Coste: ${coste_real:.6f} (Total acumulado: ${self.total_spent_today:.4f})")

   def execute_on_pod(self, job, pod_id):
        try:
            # CORRECCIÓN: Obtener la IP real dinámicamente
            address = get_pod_addr(pod_id)
            if not address:
                print(f"⚠️ El Pod {pod_id} no está listo o no tiene IP pública.")
                return False
                
            url = f"http://{address}/prompt"
            
            # Cargamos el workflow plantilla
            with open("workflow_api.json", "r") as f:
                workflow = json.load(f)

            # INYECCIÓN DINÁMICA (Lo que pide la Tarea 6 y 2)
            # Buscamos el nodo de texto (ID 6 en tu json) y metemos el prompt del usuario
            workflow["6"]["inputs"]["text"] = job.prompt
            # Cambiamos la semilla para que no salgan fotos iguales
            workflow["3"]["inputs"]["seed"] = random.randint(1, 1000000000)

            # Enviamos a ComfyUI
            payload = json.dumps({"prompt": workflow}).encode('utf-8')
            req = request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            
            with request.urlopen(req) as response:
                response_data = json.loads(response.read())
                job.log(f"Enviado a GPU. Prompt ID: {response_data.get('prompt_id')}")
                return True

        except Exception as e:
            print(f"Error conectando con Pod: {e}")
            return False

# ==========================================
# ZONA DE TEST
# ==========================================
if __name__ == "__main__":
    sistema = QueueOrchestrator()
    
    print("--- 🧪 TEST DE INTEGRACIÓN COMPLETO (PUNTOS 5, 6, 7) ---")
    
    # 1. Prueba de Seguridad (Debe ser rechazado)
    sistema.submit_job("Generar una imagen con mucha violencia y sangre")
    
    # 2. Prueba de Deduplicación
    sistema.submit_job("Un paisaje tranquilo")
    sistema.submit_job("Un paisaje tranquilo") # Rechazado por duplicado
    
    # 3. Prueba de Fallo y DLQ
    sistema.submit_job("Quiero que esto de fallo de conexión")
    
    # 4. Trabajo Normal
    sistema.submit_job("Un astronauta en marte")
    
    # Iniciar motor
    sistema.process_queue()