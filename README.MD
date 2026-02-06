# Orquestador de GPUs con RunPod API

Este proyecto implementa un sistema automatizado para gestionar colas de generación de imágenes utilizando la infraestructura de RunPod (Pods Community Cloud).

## 📋 Características
* **Auto-Scaling:** Levanta Pods GPU automáticamente cuando hay trabajos en cola y los apaga al terminar para ahorrar costes.
* **Gestión de Colas:** Sistema FIFO con reintentos (backoff exponencial) y Dead Letter Queue (DLQ).
* **Control de Costes:** Monitorización de gasto por sesión y límites diarios configurables.
* **Seguridad:** Filtrado de prompts y validación de inputs.

## 🚀 Instalación
1. Clonar el repositorio.
2. Instalar dependencias:
   ```bash
   pip install runpod python-dotenv requests numpy

3. Configurar el archivo .env:

RUNPOD_API_KEY=tu_api_key_aqui
⚙️ Uso
Para iniciar el orquestador (modo escucha):

Bash
python queue_system.py
El sistema comenzará a procesar los trabajos en cola.

Nota: Asegúrate de ejecutar benchmark.py primero para ver qué modelo (nombre exacto del archivo .safetensors) tiene tu Pod, y actualiza el workflow_api.json si es necesario.

🏗️ Arquitectura
Se ha optado por el uso de Pods Persistentes (Community Cloud) en lugar de Serverless.

Motivo: Permite mantener el estado de ComfyUI (modelos cargados en VRAM) entre generaciones consecutivas, eliminando el tiempo de "cold-start" y reduciendo el coste efectivo para lotes grandes.

🛠️ Troubleshooting
Error de conexión: Verificar que el Pod tiene el puerto 8188 expuesto públicamente.

Error "Node not found": Asegurarse de que el workflow_api.json solo usa nodos nativos o instalados en la imagen Docker.
