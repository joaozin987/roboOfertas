# Usa uma imagem oficial do Python slim como base
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema necessárias para o Playwright e compilação
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libasound2-data \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos de dependência e instala os pacotes Python PRIMEIRO
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# AGORA o pacote playwright está instalado e o binário pode ser executado
RUN playwright install chromium
RUN playwright install-deps chromium

# Copia todo o código fonte para dentro do container
COPY . .

# Cria a pasta data caso ela não exista (onde o volume será montado)
RUN mkdir -p /app/data

# Comando padrão para iniciar o bot
CMD ["python", "main.py"]