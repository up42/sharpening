## Configuration for Makefile.
SRC := .
UP42_DOCKERFILE := Dockerfile
UP42_MANIFEST := $(SRC)/UP42Manifest.json
DOCKER_TAG := sharpening
DOCKER_VERSION := latest
VALIDATE_ENDPOINT := https://api.up42.com/validate-schema/block
REGISTRY := registry.up42.com

install:
	pip install -r $(SRC)/requirements.txt

test:
	bash test.sh

test[live]:
	bash test.sh --live

clean:
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name ".mypy_cache" -exec rm -rf {} +
	find . -name ".pytest_cache" -exec rm -rf {} +
	find . -name ".coverage" -exec rm -f {} +

validate:
	curl -X POST -H 'Content-Type: application/json' -d @UP42Manifest.json $(VALIDATE_ENDPOINT)

build:
ifdef UID
	docker build --build-arg manifest='$(shell cat ${UP42_MANIFEST})' -f $(UP42_DOCKERFILE) -t $(REGISTRY)/$(UID)/$(DOCKER_TAG):$(DOCKER_VERSION) .
else
	docker build --build-arg manifest='$(shell cat ${UP42_MANIFEST})'  -f $(UP42_DOCKERFILE) -t $(DOCKER_TAG) .
endif

push:
	docker push $(REGISTRY)/$(UID)/$(DOCKER_TAG):$(DOCKER_VERSION)

login:
	docker login -u $(USER) https://$(REGISTRY)

e2e:
	python e2e.py

.PHONY: build login push test install e2e push login
