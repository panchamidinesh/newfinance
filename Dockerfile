# Use official Python image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory inside container
WORKDIR /app

# Copy requirements file first (for caching Docker layers)
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install pandas reportlab

# Copy the entire project into the container
COPY . .

# Expose port (optional — depends if you're running a web server like Flask)
EXPOSE 5000

# Command to run your application
CMD ["python", "main.py"]
