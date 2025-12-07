# Route Restrictions Database - Docker Setup

## 📁 Project Structure

All Docker-related files are now in the `docker/` directory:

```
Understanding-RAD/
├── docker/
│   ├── docker-compose.yml    # Service orchestration
│   ├── Dockerfile             # Python app image
│   ├── .dockerignore          # Build exclusions
│   ├── docker-start.sh        # Quick start script
│   └── DOCKER_SETUP.md        # This file
├── start-docker.sh            # Convenience wrapper (run from root)
├── src/
├── scripts/
└── ...
```

---

## 🚀 Quick Start

### Option 1: From Project Root
```bash
./start-docker.sh
```

### Option 2: From Docker Directory
```bash
cd docker
./docker-start.sh
```

Both commands will:
- Build the Python application container
- Start PostgreSQL database
- Create database schema automatically
- Set up networking between containers

---

## 📋 Manual Commands

All `docker-compose` commands must be run from the `docker/` directory:

```bash
cd docker

# Start containers
docker-compose up -d

# Stop containers
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

---

## 🐍 Run Python Scripts

```bash
cd docker

# Create schema
docker-compose exec app python scripts/01_create_schema.py

# Load data (when implemented)
docker-compose exec app python scripts/02_load_data.py

# Verify data
docker-compose exec app python scripts/03_verify_data.py
```

---

## 🗄️ Access Database

```bash
cd docker

# PostgreSQL CLI
docker-compose exec postgres psql -U postgres -d route_restrictions

# Or from app container
docker-compose exec app psql -h postgres -U postgres -d route_restrictions
```

---

## 🔧 Access Application Shell

```bash
cd docker
docker-compose exec app bash
```

---

## 🌐 Optional: pgAdmin (Database Web UI)

### Start pgAdmin
```bash
cd docker
docker-compose --profile tools up -d pgadmin
```

### Access pgAdmin
1. Open browser: http://localhost:5050
2. Login: `admin@admin.com` / `admin`
3. Add server:
   - **Name**: Route Restrictions
   - **Host**: `postgres` (container name)
   - **Port**: `5432`
   - **Database**: `route_restrictions`
   - **Username**: `postgres`
   - **Password**: `postgres`

---

## 📊 Services

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Database server |
| pgAdmin | 5050 | Database web UI (optional) |

---

## 🔐 Environment Variables

Default configuration (can be changed in `docker-compose.yml`):

```
DB_HOST=postgres
DB_PORT=5432
DB_NAME=route_restrictions
DB_USER=postgres
DB_PASSWORD=postgres
```

---

## 💾 Data Persistence

Database data is persisted in Docker volumes:
- `postgres_data`: PostgreSQL data
- `pgadmin_data`: pgAdmin settings

To reset database:
```bash
cd docker
docker-compose down -v  # Warning: deletes all data
docker-compose up -d
```

---

## 🛠️ Troubleshooting

### PostgreSQL not starting
```bash
cd docker

# Check logs
docker-compose logs postgres

# Restart
docker-compose restart postgres
```

### Schema not created
```bash
cd docker

# Manually run schema creation
docker-compose exec app python scripts/01_create_schema.py
```

### Connection refused
```bash
cd docker

# Wait for PostgreSQL to be ready
docker-compose exec postgres pg_isready -U postgres

# If not ready, wait a few seconds and try again
```

### Clean restart
```bash
cd docker

# Stop and remove everything
docker-compose down -v

# Start fresh
./docker-start.sh
```

---

## 💻 Development Workflow

1. **Code changes**: Edit files locally (they're mounted as volumes)
2. **Python changes**: No rebuild needed (volumes are live)
3. **Dependency changes**: Rebuild container
   ```bash
   cd docker
   docker-compose up -d --build app
   ```
4. **Schema changes**: Re-run schema script
   ```bash
   cd docker
   docker-compose exec app python scripts/01_create_schema.py
   ```

---

## 📝 Next Steps

After setup is complete:

1. **Implement ETL parsers** (`src/etl/parsers.py`)
2. **Load ANNEX data** (`scripts/02_load_data.py`)
3. **Integrate with route_engine**
4. **Test route finding with restrictions**
