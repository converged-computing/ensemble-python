# Image URL to use all building/pushing image targets
IMG ?= ghcr.io/converged-computing/ensemble-python
ARMIMG ?= ghcr.io/converged-computing/ensemble-python:arm

.PHONY: python
python: python ## Generate python proto files in python
	# pip install grpcio-tools
	# pip freeze | grep grpcio-tools
	mkdir -p ensemble/protos
	cd ensemble/protos
	# We run python first, then protoc to get around https://github.com/protocolbuffers/protobuf/issues/18096
	python -m grpc_tools.protoc -I./protos --python_out=./ensemble/protos --pyi_out=./ensemble/protos --grpc_python_out=./ensemble/protos ./protos/ensemble-service.proto
	protoc -I=./protos --python_out=./ensemble/protos ./protos/ensemble-service.proto
	sed -i 's/import ensemble_service_pb2 as ensemble__service__pb2/from . import ensemble_service_pb2 as ensemble__service__pb2/' ./ensemble/protos/ensemble_service_pb2_grpc.py

.PHONY: docker-build
docker-build:
	docker build -t ${IMG} .

.PHONY: arm-build
arm-build:
	docker buildx build --platform linux/arm64 -t ${ARMIMG} .

.PHONY: arm-deploy
arm-deploy:
	docker buildx build --platform linux/arm64 --push -t ${ARMIMG} .

.PHONY: docker-push
docker-push: ## Push docker image with the manager.
	docker push ${IMG}

# Setting SHELL to bash allows bash commands to be executed by recipes.
# Options are set to exit when a recipe line exits non-zero or a piped command fails.
SHELL = /usr/bin/env bash -o pipefail
.SHELLFLAGS = -ec

.PHONY: all
all: python

##@ General

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
