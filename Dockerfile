# Use lightweight Python image
FROM python:3.11-slim

# Install system dependencies (IMPORTANT: fixes unzip error on Sevalla)
RUN apt-get update && apt-get install -y \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside container
WORKDIR /app

# Copy all project files into container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Reflex default port
EXPOSE 3000

# Start Reflex in production mode
CMD ["reflex", "run", "--env", "prod"]