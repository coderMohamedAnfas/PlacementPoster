# Variables
IMAGE_NAME=placement-poster:latest
CONTAINER_NAME=placement-poster-container
PORT=8000
DOCKER_COMPOSE=$(shell command -v docker-compose >/dev/null 2>&1 && echo "docker-compose" || echo "docker compose")

init: build up logs ## For Initial run of the project, can be used for debugging also


build: ## Build the Docker image
	docker build -t $(IMAGE_NAME) .

restart: down up ## Restart the Docker containers

up: ## Run the Docker containers
	$(DOCKER_COMPOSE) up -d

down: ## Stop the Docker containers
	$(DOCKER_COMPOSE) down

logs: ## View logs from the container
	docker logs -f $(CONTAINER_NAME)

shell: ## Exec on the container
	docker exec -it $(CONTAINER_NAME) bash

clean: ## Clean up Docker (remove image and container)
	docker rm -f $(CONTAINER_NAME) || true
	docker rmi $(IMAGE_NAME) || true

.PHONY: help build restart up down logs shell clean
help: ## this is a help command
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {gsub("\\\\n",sprintf("\n%22c",""), $$2);printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)