FROM python:3.11-slim

WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

CMD ["watchmedo", "auto-restart", "--ignore-patterns=*.pyc;__pycache__", "--directory=.", "--pattern=*.py", "--recursive", "--", "python", "bot.py"]
