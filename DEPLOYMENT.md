# Guía de Despliegue en AWS Lightsail

Esta guía te ayudará a desplegar tu agente de IA en un servidor AWS Lightsail de manera rápida y sencilla.

## Prerrequisitos
- Una cuenta en AWS.
- Acceso a este repositorio (GitHub).

## Pasos para el Despliegue

### 1. Obtener la URL del Repositorio
1. Ve a la página principal de tu repositorio en GitHub.
2. Haz clic en el botón verde **Code**.
3. Copia la URL HTTPS. (Ejemplo: `https://github.com/TU-USUARIO/codigofacilito-demo.git`).

### 2. Crear la Instancia en Lightsail
1. Entra a la [Consola de AWS Lightsail](https://lightsail.aws.amazon.com/).
2. Haz clic en **Create instance**.
3. **Ubicación**: Elige la región más cercana a tus usuarios (ej. `us-east-1`).
4. **Imagen**: 
   - Plataforma: **Linux/Unix**
   - Blueprint: **OS Only** -> **Ubuntu 22.04 LTS**
5. **Launch Script** (Configuración Automática):
   - Haz clic en **Add launch script**.
   - Copia y pega el siguiente script. **IMPORTANTE**: Reemplaza `TU_REPO_URL` con la URL que copiaste en el paso 1.

```bash
#!/bin/bash
# === SETUP AUTOMÁTICO ===

# 1. Actualizar e instalar dependencias del sistema
apt-get update
apt-get install -y python3-pip python3-venv git nginx

# 2. Clorar el repositorio
# REEMPLAZA LA SIGUIENTE LINEA CON TU URL
git clone https://github.com/TU-USUARIO/agente-avanza.git /home/ubuntu/app

# Cambiar permisos
chown -R ubuntu:ubuntu /home/ubuntu/app

# 3. Configurar entorno Python
cd /home/ubuntu/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configurar servicio del sistema (Systemd)
cat > /etc/systemd/system/agente.service <<EOF
[Unit]
Description=Agente Avanza FastAPI
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/app
Environment="PATH=/home/ubuntu/app/venv/bin"
# Configuración de entorno (Opcional, si main.py lo requiere)
Environment="N8N_WEBHOOK_URL=https://gscode.app.n8n.cloud/webhook/ask"
ExecStart=/home/ubuntu/app/venv/bin/fastapi run main.py --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Iniciar servicio
systemctl daemon-reload
systemctl start agente
systemctl enable agente

# 5. Configurar Nginx (Reverse Proxy)
rm /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/agente <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

ln -s /etc/nginx/sites-available/agente /etc/nginx/sites-enabled/
systemctl restart nginx

# === FIN SETUP ===
```

6. **Plan**: Selecciona el plan deseado (el de $3.50 o $5 USD suele ser suficiente para demos).
7. **Nombre**: Asigna un nombre único a tu instancia (ej. `agente-bot`).
8. Haz clic en **Create instance**.

### 3. Verificar el Despliegue
1. Espera unos minutos a que la instancia inicie y el script termine de ejecutarse.
2. Copia la **IP Pública** de tu instancia desde la consola de Lightsail.
3. Abre esa IP en tu navegador. Deberías ver tu aplicación funcionando.

## Solución de Problemas
Si no puedes acceder:
1. Conéctate via SSH (botón terminal naranja en Lightsail).
2. Verifica el estado del servicio: `sudo systemctl status agente`.
3. Verifica los logs de Nginx: `sudo tail -f /var/log/nginx/error.log`.
