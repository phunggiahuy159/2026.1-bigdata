SHELL := /bin/bash
BIGD_DATA ?= $(HOME)/bigd/data

STRIMZI_VERSION := 1.3.0
MINIO_VERSION := 5.4.0
LAKEKEEPER_VERSION := 0.12.0

.PHONY: help helm-repos render-core storage-dirs secrets deploy-storage deploy-kafka deploy-minio \
	deploy-catalog deploy-core

help:
	@echo "render-core    helm template cho Kafka, MinIO, catalog (không đụng cụm)"
	@echo "storage-dirs   tạo thư mục dữ liệu trên máy chủ (không đụng cụm)"
	@echo "secrets        tạo K8s Secret từ .env, không ghi đè Secret đã có (đụng cụm)"
	@echo "deploy-core    cài namespace, storage, Kafka, MinIO, catalog (đụng cụm)"

helm-repos:
	helm repo add strimzi https://strimzi.io/charts/
	helm repo add minio https://charts.min.io/
	helm repo add lakekeeper https://lakekeeper.github.io/lakekeeper-charts/
	helm repo update

render-core:
	helm template strimzi strimzi/strimzi-kafka-operator --version $(STRIMZI_VERSION) -n kafka \
		-f deploy/kafka/strimzi-operator-values.yaml > /dev/null
	helm template minio minio/minio --version $(MINIO_VERSION) -n minio \
		-f deploy/minio/values.yaml > /dev/null
	helm template iceberg-catalog lakekeeper/lakekeeper --version $(LAKEKEEPER_VERSION) -n iceberg \
		-f deploy/iceberg-catalog/values.yaml > /dev/null

storage-dirs:
	mkdir -p $(BIGD_DATA)
	chmod 0700 $(BIGD_DATA)
	mkdir -p -m 0777 $(BIGD_DATA)/kafka $(BIGD_DATA)/minio $(BIGD_DATA)/catalog-postgres

secrets:
	bash deploy/scripts/create-secrets.sh

deploy-storage: storage-dirs
	kubectl apply -f deploy/namespaces.yaml
	kubectl apply -f deploy/storage/bigd-data.yaml

deploy-kafka:
	helm upgrade --install strimzi strimzi/strimzi-kafka-operator --version $(STRIMZI_VERSION) \
		-n kafka -f deploy/kafka/strimzi-operator-values.yaml --wait --timeout 5m
	kubectl apply -n kafka -f deploy/kafka/kafka-cluster.yaml
	kubectl wait kafka/bigd-kafka -n kafka --for=condition=Ready --timeout=10m

deploy-minio:
	helm upgrade --install minio minio/minio --version $(MINIO_VERSION) -n minio \
		-f deploy/minio/values.yaml --wait --timeout 5m

deploy-catalog:
	helm upgrade --install iceberg-catalog lakekeeper/lakekeeper --version $(LAKEKEEPER_VERSION) \
		-n iceberg -f deploy/iceberg-catalog/values.yaml --wait --timeout 10m

deploy-core: deploy-storage secrets deploy-kafka deploy-minio deploy-catalog
