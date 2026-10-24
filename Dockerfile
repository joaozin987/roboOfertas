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

# Copia e instala todas as dependências do projeto
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# GARANTE explicitamente que o playwright está instalado no sistema global do container
RUN pip install --no-cache-dir playwright

# Agora executa a instalação dos binários do navegador sem erro de comando não encontrado
RUN playwright install chromium
RUN playwright install-deps chromium

# Copia o restante do código fonte
COPY . .

# Cria a pasta data para o volume persistente
RUN mkdir -p /app/data

# Comando para iniciar a aplicação
CMD ["python", "main.py"]