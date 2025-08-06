# database/Dockerfile
FROM pgvector/pgvector:pg15

# Install wget and unzip for downloading and extracting files
RUN apt-get update && apt-get install -y wget unzip && rm -rf /var/lib/apt/lists/*

# The init scripts will be mounted from the host
# No need to copy them here