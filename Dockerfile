# 1. Use the official Microsoft image that HAS the browsers already
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 2. Set the working directory
WORKDIR /app

# 3. Copy your requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your code
COPY . .

# 5. Tell Render which port to use
ENV PORT=5011
EXPOSE 5011

# 6. Start the app (This replaces your Start Command)
CMD ["gunicorn", "--bind", "0.0.0.0:5011", "--timeout", "120", "app:app"]