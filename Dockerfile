FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    git \
    libssl-dev \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# RUN curl -fsSL https://ollama.com/install.sh | sh

# RUN ollama serve & sleep 5 && ollama run smollm:135m  

COPY . .

EXPOSE 8000

# CMD ["sh", "-c", "ollama serve & sleep 10 && uvicorn main:app --host 0.0.0.0 --port 8000"]
CMD ["uvicorn main:app --host 0.0.0.0 --port 8000"]

