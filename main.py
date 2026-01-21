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

app = FastAPI()

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
    payload = {"numeroCedula": cedula_limpia}

    # Proxy configuration
    proxy_url = os.getenv("TSE_PROXY_URL")
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    
    if proxy_url:
        print(f"Using proxy: {proxy_url}")

    def scrape_tse():
        # Step 1: Visit home naturally to get Cloudflare cookies
        # Using a newer fingerprint (Chrome 124)
        print("DEBUG: Visiting home page...")
        requests.get(
            tse_url_home, 
            proxies=proxies,
            impersonate="chrome124",
            timeout=10
        )
        
        # Step 2: POST request with the payload
        print("DEBUG: Posting to API...")
        response = requests.post(
            tse_url_api, 
            json=payload, 
            proxies=proxies, 
            impersonate="chrome124",
            timeout=15,
            # Add Referer explicitly as some WAFs check it match the previous page
            headers={"Referer": tse_url_home}
        )
        return response

    try:
        # Run blocking scraper in a thread to avoid blocking the event loop
        response = await asyncio.to_thread(scrape_tse)
        
        if response.status_code != 200:
            print(f"DEBUG: TSE Error {response.status_code}")
            print(f"DEBUG: Body: {response.text[:500]}")
            
            if response.status_code == 403:
                 raise HTTPException(status_code=403, detail="Error 403: Bloqueado por Cloudflare")
            
            response.raise_for_status()
            
        data = response.json()
        return JSONResponse(content=data)

    except Exception as e:
        print(f"Error validating cedula: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error validando la cédula en el TSE")


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
            return ChatResponse(
                answer=n8n_data.get("answer") or n8n_data.get("output") or "No se recibió respuesta",
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
