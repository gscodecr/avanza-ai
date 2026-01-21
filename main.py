from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import httpx
import os
from curl_cffi import requests
import asyncio
from datetime import datetime, timedelta
import random
import re

import csv

# ... (previous imports)

# --- MEJORA 4: LOGGING DE USUARIOS ÚNICOS ---
LOG_FILE = "usuarios_unicos.csv"
LOGGED_USERS = set()

def load_logged_users():
    """Carga los usuarios existentes al iniciar para no duplicarlos"""
    if not os.path.exists(LOG_FILE):
        # Crear archivo con cabeceras si no existe
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Fecha", "Hora", "Cedula", "Nombre", "Origen"])
        return

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None) # Saltar cabecera
            for row in reader:
                if row:
                    LOGGED_USERS.add(row[2]) # La columna 2 es la cédula
        print(f"DEBUG: Loaded {len(LOGGED_USERS)} unique users from log.")
    except Exception as e:
        print(f"Error loading log file: {e}")

def log_unique_user(cedula, data, source="TSE"):
    if cedula in LOGGED_USERS:
        return # Ya existe, no hacemos nada

    try:
        nombre = data.get("n", "Desconocido") # TSE suele devolver 'n' como nombre o similar
        # Intentar extraer nombre más limpio si la estructura varía
        # Ajustar según la respuesta real del TSE
            
        now = datetime.now()
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                cedula,
                nombre,
                source
            ])
        
        LOGGED_USERS.add(cedula)
        print(f"DEBUG: New unique user logged: {cedula}")
    except Exception as e:
        print(f"Error logging user: {e}")

# --- MEJORA 5: LOGGING DE CHAT ---
CHAT_LOG_FILE = "historial_chat.csv"

def log_chat_message(session_id, question, answer):
    """Guarda la conversación para análisis"""
    if not os.path.exists(CHAT_LOG_FILE):
        with open(CHAT_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Fecha", "Hora", "SessionID", "Pregunta", "Respuesta"])

    try:
        now = datetime.now()
        with open(CHAT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                session_id,
                question,
                answer
            ])
    except Exception as e:
        print(f"Error logging chat: {e}")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    load_logged_users()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# URL del webhook de n8n
N8N_WEBHOOK_URL = "https://gscode.app.n8n.cloud/webhook/ask"

# --- MEJORA 1: SISTEMA DE CACHÉ ---
CACHE_VALIDACIONES = {}
CACHE_DURACION = timedelta(hours=24) # Guardar por 24 horas

def get_cached_response(cedula):
    if cedula in CACHE_VALIDACIONES:
        entry = CACHE_VALIDACIONES[cedula]
        if datetime.now() < entry["expires"]:
            print(f"DEBUG: Cache hit for {cedula}")
            return entry["data"]
        else:
            del CACHE_VALIDACIONES[cedula] # Expiró
    return None

def save_to_cache(cedula, data):
    CACHE_VALIDACIONES[cedula] = {
        "data": data,
        "expires": datetime.now() + CACHE_DURACION
    }

# --- MEJORA 2: POOL DE PROXIES INTELIGENTE ---
def get_random_proxy_config():
    """
    Analiza la URL del proxy actual y trata de rotar el usuario (Webshare)
    para usar múltiples 'hilos' o sesiones diferentes.
    """
    base_url = os.getenv("TSE_PROXY_URL")
    if not base_url:
        return None
        
    # Detectar si es un proxy de Webshare con patrón numérico (ej: -401)
    # Regex busca: (cualquier_cosa)-(numero)(:password...)
    match = re.search(r"(.*-)(\d+)(:.*@.*)", base_url)
    
    if match:
        prefix = match.group(1) # "http://user-cr-"
        current_num = int(match.group(2)) # 401
        suffix = match.group(3) # ":pass@host..."
        
        # Rotamos entre el usuario actual y 5 más (ej: 401 al 406) para distribuir carga
        # Basado en tu screenshot que muestra del 401 en adelante
        new_num = random.randint(401, 406) 
        
        new_proxy_url = f"{prefix}{new_num}{suffix}"
        print(f"DEBUG: Using Proxy User #{new_num}")
        return {"http": new_proxy_url, "https": new_proxy_url}
        
    # Si no tiene el patrón, usamos el original
    return {"http": base_url, "https": base_url}

# --- MEJORA 3: ROTACIÓN DE NAVEGADORES ---
def get_random_impersonation():
    # Alternar entre Chrome y Safari para parecer usuarios distintos
    return random.choice(["chrome124", "safari15_5"])

class ChatRequest(BaseModel):
    question: str
    session_id: str
    user_context: dict | None = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str

class LoginRequest(BaseModel):
    cedula: str

@app.get("/")
async def read_root():
    return FileResponse('static/index.html')

@app.post("/api/validate-cedula")
async def validate_cedula(request: LoginRequest):
    tse_url_home = "https://www.tse.go.cr/dondevotar/"
    tse_url_api = "https://www.tse.go.cr/dondevotar/prRemoto.aspx/ObtenerDondeVotar"
    
    # Clean cedula
    cedula_limpia = request.cedula.replace("-", "").strip()
    
    # 1. Check Cache first
    cached_data = get_cached_response(cedula_limpia)
    if cached_data:
        # También registramos si viene del caché, por si es la primera vez que inicia el servidor 
        # y el caché estaba en memoria (aunque el caché se borra al reiniciar, el log persiste).
        # La función log_unique_user ya comprueba si existe en el CSV, así que es seguro llamar aquí.
        log_unique_user(cedula_limpia, cached_data, source="Cache")
        return JSONResponse(content=cached_data)

    payload = {"numeroCedula": cedula_limpia}
    
    # 2. Get Random Proxy from Pool
    proxies = get_random_proxy_config()
    
    # 3. Get Random Browser Fingerprint
    impersonation = get_random_impersonation()

    def scrape_tse():
        print(f"DEBUG: Starting scrape with {impersonation}...")
        
        with requests.Session(impersonate=impersonation) as s:
            s.proxies = proxies
            
            # GET Home (cookie set)
            try:
                s.get(tse_url_home, timeout=10)
            except Exception as e:
                print(f"Warning: Home visit failed ({e}), trying API directly...")

            # Small human pause
            import time
            time.sleep(random.uniform(1.0, 3.0)) # Random pause 1-3s
            
            # POST API
            response = s.post(
                tse_url_api, 
                json=payload, 
                timeout=15,
                headers={"Referer": tse_url_home}
            )
            return response

    try:
        # Run in thread
        response = await asyncio.to_thread(scrape_tse)
        
        if response.status_code != 200:
            print(f"DEBUG: TSE Error {response.status_code}")
            if response.status_code == 403:
                 raise HTTPException(status_code=403, detail="Error 403: Bloqueado por seguridad")
            response.raise_for_status()
            
        data = response.json()
        
        # Save success to cache
        save_to_cache(cedula_limpia, data)
        # Log unique user (This was missing!)
        log_unique_user(cedula_limpia, data, source="TSE")
        
        return JSONResponse(content=data)

    except Exception as e:
        print(f"Error validating cedula: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error en validación TSE")


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Recibe pregunta y session_id del frontend,
    los envía a n8n y devuelve la respuesta
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                N8N_WEBHOOK_URL,
                json={
                    "question": request.question,
                    "session_id": request.session_id
                }
            )
            response.raise_for_status()
            
            # n8n devuelve la respuesta del agente
            n8n_data = response.json()
            
            # Mapeamos la respuesta de n8n al formato esperado por el frontend
            # Asumimos que n8n devuelve { "output": "respuesta..." } o similar
            final_answer = n8n_data.get("answer") or n8n_data.get("output") or "No se recibió respuesta"
            
            # Log the conversation
            log_chat_message(request.session_id, request.question, final_answer)

            return ChatResponse(
                answer=final_answer,
                session_id=request.session_id
            )
            
    except httpx.TimeoutException:
        print("Timeout connecting to n8n webhook")
        raise HTTPException(status_code=504, detail="Timeout al consultar el agente")
    except httpx.HTTPError as e:
        print(f"HTTP Error connecting to n8n: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al comunicarse con n8n: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
