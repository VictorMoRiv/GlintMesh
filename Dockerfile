FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py mcp_server.py mcp_yahoo.py mcp_ecb.py mcp_mongodb.py mcp_servers.json .env.example ./
COPY database/ ./database/
COPY static/ ./static/

# Provide your key at runtime: -e GEMINI_API_KEY=... (or mount a .env file)
ENV GEMINI_MODEL=gemini-3.6-flash MCP_ENABLED=true
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
