# Understanding RAD - Route Restrictions Database

Flight route planning system with PostgreSQL-backed restriction database for European FRA (Free Route Airspace) compliance.

## 🚀 Quick Start with Docker

```bash
./start-docker.sh
```

This will set up PostgreSQL database and create the schema automatically.

For detailed Docker instructions, see [`docker/DOCKER_SETUP.md`](docker/DOCKER_SETUP.md)

---

## 📁 Project Structure

```
Understanding-RAD/
├── docker/                    # Docker configuration
│   ├── docker-compose.yml     # Service orchestration
│   ├── Dockerfile             # Python app image
│   └── DOCKER_SETUP.md        # Docker documentation
├── src/
│   ├── db/                    # Database layer
│   │   ├── schema.sql         # PostgreSQL schema (8 tables)
│   │   └── connection.py      # Connection manager
│   ├── etl/                   # ETL pipeline (to be implemented)
│   └── config/                # Configuration
├── route_engine/              # Route finding A* algorithm
├── scripts/                   # Utility scripts
│   ├── 01_create_schema.py    # Create DB schema
│   ├── 02_load_data.py        # Load ANNEX data (TBD)
│   └── 03_verify_data.py      # Verify data (TBD)
├── Annex_*.csv                # ANNEX restriction data (9 files, 73K rows)
└── download_11487/
    └── FRA_Points.csv         # FRA waypoint master data
```

---

### Technology Stack
- **Database**: PostgreSQL 18.1 (latest stable, Nov 2025)
- **Language**: Python 3.14.2 (latest stable, Dec 2025)
- **Container**: Docker + Docker Compose
- **Libraries**: psycopg2, pandas, python-dotenv

---

## 🗄️ Database

**PostgreSQL Schema**:
- 8 tables (airports, waypoints, airways, airspaces, restrictions, procedures, groups)
- 15+ indexes optimized for A* queries
- 3 helper views
- ~150K rows (after ETL)

**Connection** (from Docker):
```
Host:     localhost
Port:     5432
Database: route_restrictions
User:     postgres
Password: postgres
```

---

## 🛠️ Development

### Run Scripts
```bash
cd docker
docker-compose exec app python scripts/01_create_schema.py
```

### Access Database
```bash
cd docker
docker-compose exec postgres psql -U postgres -d route_restrictions
```

### View Logs
```bash
cd docker
docker-compose logs -f
```

---

## 📊 Data Sources

- **FRA Points**: `download_11487/FRA_Points.csv` (~5,000 waypoints)
- **ANNEX Files**: 9 CSV files with route restrictions
  - Annex_1: Airport groups (117 rows)
  - Annex_2A: Flight level caps (1,654 rows)
  - Annex_2B: Route utilization (46,181 rows)
  - Annex_2C: Restricted airspace (5,427 rows)
  - Annex_3A_ARR: Arrival procedures (4,667 rows)
  - Annex_3A_DEP: Departure procedures (5,277 rows)
  - Annex_3A_Conditions: RAD conditions (226 rows)
  - Annex_3B_DCT: Direct route restrictions (9,968 rows)
  - Annex_3B_FRA_LIM: FRA limitations (637 rows)

---

## 🎯 Next Steps

1. ✅ Database schema created
2. ⏳ Implement ETL parsers (`src/etl/parsers.py`)
3. ⏳ Load ANNEX data (`scripts/02_load_data.py`)
4. ⏳ Integrate with `route_engine`
5. ⏳ Test route finding with restrictions

---

## 📚 Documentation

- [Docker Setup Guide](docker/DOCKER_SETUP.md)
- [Route Engine README](route_engine/README.md)
- [Planning Documents](docs/planning/):
  - `rdb_implementation_plan.md` - Full RDB design
  - `rdb_comparison.md` - Design approach analysis
  - `text_parsing_strategy.md` - Text field parsing
  - `postgresql_implementation.md` - PostgreSQL setup
  - `docker_setup_walkthrough.md` - Docker walkthrough

---

## 🔧 Requirements

- Docker Desktop
- 2GB free disk space
- Ports 5432 (PostgreSQL) and 5050 (pgAdmin, optional)

---

## 📝 License

[Add your license here]
