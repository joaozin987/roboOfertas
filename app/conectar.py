import requests
import base64
import os
import subprocess
import sys

URL = "https://evolution-api-production-f6c0.up.railway.app"
APIKEY = "JpzPromo2026"
INSTANCE = "robo_ofertas"

headers = {
    "apikey": APIKEY
}

# 1. Pede o QR code atualizado
res = requests.get(f"{URL}/instance/connect/{INSTANCE}", headers=headers)
data = res.json()

base64_img = data.get("base64")

if not base64_img and "qrcode" in data:
    base64_img = data["qrcode"].get("base64")

if base64_img:
    # Remove o cabeçalho data:image/png;base64, se existir
    if "," in base64_img:
        base64_img = base64_img.split(",")[1]

    with open("qrcode.png", "wb") as fh:
        fh.write(base64.b64decode(base64_img))
    
    print("QR Code salvo como 'qrcode.png'! Abrindo...")
    
    # Abre a imagem no visualizador padrão do sistema
    if sys.platform.startswith("win"):
        os.startfile("qrcode.png")
    elif sys.platform.startswith("darwin"):
        subprocess.run(["open", "qrcode.png"])
    else:
        subprocess.run(["xdg-open", "qrcode.png"])
else:
    print("Resposta recebida:")
    print(data)