FROM python:3.10-slim

# Create a non-root user for security (Hugging Face requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy requirements first (Layer Caching)
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the project
COPY --chown=user . /app

# Expose the port Hugging Face Spaces expects
EXPOSE 7860

# Launch the app
CMD ["python", "server/app.py"]