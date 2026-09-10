FROM python:3.11-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure basic network utilities (wget/curl) are available for readiness checks
RUN apt-get update && \
	apt-get install -y --no-install-recommends wget curl ca-certificates && \
	rm -rf /var/lib/apt/lists/*

COPY . .
RUN chmod +x run_once.sh

ENTRYPOINT ["./run_once.sh"]
