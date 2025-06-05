# Use the official Python image as the base image
FROM python:3.8.10-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app


# Install system dependencies
RUN apk update \
    && apk --update --upgrade add gcc musl-dev zlib-dev libffi-dev cmake tzdata\
    && apk add postgresql-dev \
    && pip install --upgrade pip setuptools wheel 

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]