# Agente Avanza

Agente Avanza es una aplicación de chat impulsada por IA diseñada para interactuar con los ciudadanos, responder preguntas sobre propuestas políticas y validar la identidad de los usuarios mediante el padrón electoral (TSE).

## Características

- **Chat Inteligente**: Interfaz de chat amigable conectada a un agente de IA (vía n8n).
- **Validación de Identidad**: Verificación de cédula costarricense utilizando el servicio del TSE.
- **Identidad de Marca**: Diseño personalizado con los colores y logos del partido "Avanza".
- **Diseño Responsivo**: Funciona perfectamente en dispositivos móviles y de escritorio.

## Tecnologías

- **Backend**: FastAPI (Python)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Integración**: n8n (Webhooks)
- **Infraestructura**: AWS Lightsail, Nginx, Systemd

## Instalación Local

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/TU-USUARIO/avanza-ai.git
    cd avanza-ai
    ```

2.  **Crear un entorno virtual**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ejecutar la aplicación**:
    ```bash
    # Desarrollo
    python main.py
    # O usando fastapi cli
    fastapi dev main.py
    ```
    La aplicación estará disponible en `http://localhost:8000`.

## Despliegue

Para desplegar esta aplicación en producción usando AWS Lightsail, consulta la guía detallada de despliegue:

👉 [Guía de Despliegue (DEPLOYMENT.md)](DEPLOYMENT.md)

## Estructura del Proyecto

- `main.py`: Aplicación backend FastAPI y endpoints.
- `static/`: Archivos estáticos (HTML, CSS, JS, imágenes).
- `requirements.txt`: Dependencias de Python.
- `DEPLOYMENT.md`: Instrucciones de despliegue.
