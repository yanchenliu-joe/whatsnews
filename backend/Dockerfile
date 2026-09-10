FROM python:3.13-slim

WORKDIR /app

# psycopg2-binary and trafilatura's lxml dependency ship manylinux wheels for
# this base image — no system build toolchain needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render (and most PaaS hosts) inject $PORT at runtime — must bind to it,
# not a hardcoded port. media/audio/ is only used when VOICE_AUDIO_STORAGE=
# local (dev default); in production VOICE_AUDIO_STORAGE=supabase means
# nothing is ever written to this ephemeral container filesystem.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
