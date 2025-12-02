# Use the official Python Alpine image as the base image
FROM python:3.8.10-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system and build dependencies
RUN apk update && apk add --no-cache \
# RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    zlib-dev \
    libffi-dev \
    cmake \
    tzdata \
    postgresql-dev \
    poppler-utils \
    jpeg-dev \
    py3-pillow \
    python3-dev \
    libxml2-dev \
    libxslt-dev \
    bash \
    curl \
    git


# Upgrade pip, setuptools, wheel
RUN pip install --upgrade pip setuptools wheel

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files into the container
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
