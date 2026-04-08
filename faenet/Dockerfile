FROM python:3.11-slim

# Instala dependências do sistema para psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Cria pasta de uploads
RUN mkdir -p static/uploads

# Porta padrão
EXPOSE 5000

# Inicializa o banco e roda com gunicorn
CMD python -c "from app import app, db, seed_db; \
    app.app_context().push(); \
    db.create_all(); \
    seed_db()" && \
    gunicorn app:app \
        --bind 0.0.0.0:${PORT:-5000} \
        --workers 2 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
