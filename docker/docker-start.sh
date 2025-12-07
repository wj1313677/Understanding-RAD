#!/bin/bash
# Quick start script for Docker setup

set -e

echo "=================================================="
echo "Route Restrictions Database - Docker Setup"
echo "=================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✅ Docker is running"

# Change to docker directory
cd "$(dirname "$0")"

# Build and start containers
echo ""
echo "🐳 Building and starting containers..."
docker-compose up -d --build

# Wait for PostgreSQL to be ready
echo ""
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Check if database is ready
docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL is ready"
else
    echo "⏳ Waiting a bit more..."
    sleep 5
fi

# Create schema
echo ""
echo "📊 Creating database schema..."
docker-compose exec -T app python scripts/01_create_schema.py

echo ""
echo "=================================================="
echo "✅ Setup Complete!"
echo "=================================================="
echo ""
echo "Services running:"
echo "  - PostgreSQL:  localhost:5432"
echo "  - Database:    route_restrictions"
echo "  - User:        postgres"
echo "  - Password:    postgres"
echo ""
echo "Useful commands:"
echo "  - View logs:           docker-compose logs -f"
echo "  - Stop containers:     docker-compose down"
echo "  - Restart:             docker-compose restart"
echo "  - Shell into app:      docker-compose exec app bash"
echo "  - Connect to DB:       docker-compose exec postgres psql -U postgres -d route_restrictions"
echo ""
echo "Optional: Start pgAdmin (web UI for database):"
echo "  docker-compose --profile tools up -d pgadmin"
echo "  Then open: http://localhost:5050"
echo "  Login: admin@admin.com / admin"
echo ""
