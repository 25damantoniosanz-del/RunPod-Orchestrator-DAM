import time
import uuid
import hashlib
import random
from datetime import datetime
import runpod

# --- IMPORTAMOS TU LÓGICA DE PROVISIÓN DEL PUNTO 2 ---
# Asegúrate de que en main.py o donde tengas la función, se pueda importar.
# Si no, puedes pegar la función create_worker_pod aquí arriba.
from main import create_worker_pod, stop_worker_pod

# --- CONFIGURACIÓN DEL SISTEMA ---
MAX_RETRIES = 3            # Si falla 3 veces, a la basura (DLQ)
BACKOFF_FACTOR = 2         # Espera exponencial (2s, 4s, 8s...)
MAX_CONCURRENT_JOBS = 1    # Rate Limiting: 1 trabajo por GPU a la vez
AUTO_SCALE_THRESHOLD = 5   # Si hay más de 5 trabajos, creamos nueva máquina

class Job:
    def __init__(self, prompt):
        self.id = str(uuid.uuid4())[:8]
        self.prompt = prompt
        self.status = "PENDING"  # PENDING, PROCESSING, COMPLETED, FAILED, DEAD
        self.created_at = datetime.now()
        self.retries = 0
        self.result = None
        # Generamos un HASH del prompt para detectar duplicados
        self.prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        self.history_log = []

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.history_log.append(f"[{timestamp}] {message}")

class QueueOrchestrator:
    def __init__(self):
        self.pending_queue = []       # Cola de espera
        self.active_jobs = {}         # Trabajos ejecutándose ahora
        self.completed_jobs = []      # Historial de éxitos
        self.dead_letter_queue = []   # Cementerio de trabajos fallidos
        self.active_hashes = set()    # Para deduplicación (evitar trabajos repetidos)
        
        # Estado de la Infraestructura (Provisioning)
        self.worker_pod_id = None     # ID del Pod en RunPod

    # --- 1. SUBMIT & DEDUPLICACIÓN ---
    def submit_job(self, prompt):
        # Calculamos hash para ver si ya existe
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        
        if prompt_hash in self.active_hashes:
            print(f"⚠️ Job Duplicado rechazado: '{prompt[:20]}...'")
            return None
        
        new_job = Job(prompt)
        self.pending_queue.append(new_job)
        self.active_hashes.add(prompt_hash)
        new_job.log("Job creado y encolado.")
        print(f"📥 Job recibido: {new_job.id}")
        return new_job.id

    # --- 2. CONTROL DE CONCURRENCIA Y ESCALADO ---
    def process_queue(self):
        print("\n🔄 Iniciando bucle de orquestación (Ctrl+C para parar)...")
        try:
            while True:
                # A) MONITORIZACIÓN DE SALUD
                self.check_auto_scaling()

                # B) ASIGNACIÓN DE TRABAJOS (Rate Limiting)
                # Solo entramos si hay hueco (Semáforo)
                if len(self.active_jobs) < MAX_CONCURRENT_JOBS and self.pending_queue:
                    job = self.pending_queue.pop(0)
                    self.run_job_async(job)

                # C) Simulación de espera (Polling loop)
                time.sleep(1)
                
                # Si no hay nada que hacer, avisamos
                if not self.pending_queue and not self.active_jobs:
                    print("💤 Sistema ocioso...", end="\r")

        except KeyboardInterrupt:
            print("\n🛑 Deteniendo sistema...")
            if self.worker_pod_id:
                print(f"🧹 Limpiando recursos: Apagando Pod {self.worker_pod_id}")
                stop_worker_pod(self.worker_pod_id)

    # --- 3. AUTO-ESCALADO (PROVISIÓN API) ---
    def check_auto_scaling(self):
        # Lógica simple: Si hay mucha cola y no tenemos máquina, la creamos.
        queue_size = len(self.pending_queue)
        
        if queue_size > 0 and self.worker_pod_id is None:
            print(f"🚨 Cola detectada ({queue_size} jobs). Provisionando GPU...")
            # Aquí llamamos a tu función del Punto 2
            # self.worker_pod_id = create_worker_pod() 
            self.worker_pod_id = "POD-SIMULADO-123" # Simulación para no gastar saldo
            print(f"✅ Worker asignado: {self.worker_pod_id}")

        elif queue_size == 0 and not self.active_jobs and self.worker_pod_id:
            # Lógica de Scale-Down (Ahorro de costes)
            print("📉 Cola vacía. Apagando worker para ahorrar dinero.")
            # stop_worker_pod(self.worker_pod_id)
            self.worker_pod_id = None

    # --- 4. EJECUCIÓN ASÍNCRONA Y REINTENTOS ---
    def run_job_async(self, job):
        job.status = "PROCESSING"
        self.active_jobs[job.id] = job
        print(f"⚙️ Enviando Job {job.id} a RunPod...")
        
        # SIMULACIÓN DE LLAMADA ASYNC (Aquí iría requests.post a ComfyUI)
        # Usamos try/except para manejar fallos y Backoff
        try:
            success = self.mock_api_call(job) # Simula el tiempo de la GPU
            
            if success:
                self.complete_job(job, "imagen_output.png")
            else:
                raise Exception("Error de conexión GPU")

        except Exception as e:
            self.handle_failure(job, str(e))

    def handle_failure(self, job, error_msg):
        job.retries += 1
        wait_time = BACKOFF_FACTOR ** job.retries # Backoff Exponencial (2, 4, 8s)
        
        job.log(f"Fallo ({job.retries}/{MAX_RETRIES}): {error_msg}")
        print(f"⚠️ Error en {job.id}. Reintentando en {wait_time}s...")
        
        del self.active_jobs[job.id] # Lo sacamos de activo
        
        if job.retries >= MAX_RETRIES:
            # DEAD LETTER QUEUE
            job.status = "DEAD"
            job.log("Movido a DLQ por exceso de fallos.")
            self.dead_letter_queue.append(job)
            self.active_hashes.remove(job.prompt_hash) # Permitimos reintentar si el usuario quiere
            print(f"💀 Job {job.id} MUERTO (DLQ).")
        else:
            # Reencolar con retraso (Backoff)
            time.sleep(wait_time) # Bloqueante simple por demo (en real sería thread)
            job.status = "PENDING"
            self.pending_queue.insert(0, job) # Prioridad máxima

    def complete_job(self, job, result):
        job.status = "COMPLETED"
        job.result = result
        job.log("Finalizado correctamente.")
        self.completed_jobs.append(job)
        self.active_hashes.remove(job.prompt_hash) # Liberamos hash
        del self.active_jobs[job.id]
        print(f"✅ Job {job.id} TERMINADO.")

    def mock_api_call(self, job):
        """Simula la API de RunPod/ComfyUI"""
        time.sleep(2) # Tiempo de inferencia
        if "fallo" in job.prompt: return False # Simular error forzado
        return True

# --- ZONA DE PRUEBAS ---
if __name__ == "__main__":
    orchestrator = QueueOrchestrator()
    
    print("--- 🧪 TEST DE SISTEMA DE COLAS ---")
    
    # 1. Deduplicación
    orchestrator.submit_job("Un gato en el espacio")
    orchestrator.submit_job("Un gato en el espacio") # Debería ser rechazado
    
    # 2. Backoff y DLQ
    orchestrator.submit_job("Generar fallo intencionado") 
    
    # 3. Carga normal
    orchestrator.submit_job("Paisaje cyberpunk")
    
    # Arrancar procesador
    orchestrator.process_queue()