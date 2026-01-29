FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Make start.sh executable
RUN chmod +x start.sh

# Expose port (Railway will override with $PORT)
EXPOSE 5000

# Run the app with Gunicorn (production-ready)
CMD ["./start.sh"]
