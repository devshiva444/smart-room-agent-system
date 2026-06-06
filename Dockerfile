FROM python:3.10-slim

WORKDIR /app

# Requirements install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Saari files copy karo
COPY . .

# Port expose
EXPOSE 7860

# CMD: Naye folder path
CMD ["python", "server/app.py"]