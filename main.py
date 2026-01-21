from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import httpx
import os

app = FastAPI()

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
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json; charset=UTF-8",
        "Referer": "https://www.tse.go.cr/dondevotar/",
        "Origin": "https://www.tse.go.cr",
        "Host": "www.tse.go.cr",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: Visit home to get cookies (ASP.NET_SessionId, etc)
            # We don't strictly need the content, just the cookie jar update
            await client.get(tse_url_home, headers=headers)
            
            # Step 2: Make the POST request with the session cookies
            payload = {"numeroCedula": request.cedula}
            response = await client.post(tse_url_api, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            # The API usually returns implicit JSON d: {...} or similar structure depending on ASP.NET version
            # Let's return exactly what it sends for now so frontend can parse
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

# CORS middleware (optional for local dev but good practice as per user request)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
