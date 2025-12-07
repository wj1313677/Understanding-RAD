# Planning Documents

This directory contains comprehensive planning and design documents for the ANNEX Data RDB conversion project.

## 📋 Documents

### 1. **`rdb_implementation_plan.md`** - Main Implementation Plan
**73K rows, 5.5MB of ANNEX data → Normalized PostgreSQL Database**

- Complete schema design (12 tables)
- Data inventory of all 9 ANNEX files
- 4-phase implementation roadmap
- Technology comparison (SQLite vs PostgreSQL)
- Performance estimates

**Key Sections**:
- Database schema with DDL
- Query optimization strategy
- Integration with route_engine
- Advanced features (time-based filtering, groups)

---

### 2. **`rdb_comparison.md`** - Design Approach Analysis
**Original vs Simplified Normalized Approach**

Compares 3 database design approaches:
1. **Original** (ID/Group-based): 12 tables, 73K rows, preserves CSV structure
2. **Simplified** (Normalized): 6 tables, ~150K rows, pre-expanded groups
3. **Hybrid** (Recommended): Materialized views for best of both

**Key Findings**:
- Simplified approach: **10x faster queries** for A*
- Data explosion: 73K → 150K rows (2x)
- Memory trade-off: 2x memory for 10x speed
- **Recommendation**: Use Simplified for route_engine

---

### 3. **`text_parsing_strategy.md`** - Text Field Parsing
**Hybrid Keyword Extraction Approach**

Strategy for parsing complex text descriptions in ANNEX data:
- `"NOT AVBL FOR TFC EXC ARR EDDB & VIA BATEL"`
- `"ABV FL245 AT (KOMOB DCT IBESA)"`

**5 Key Parsing Patterns**:
1. Availability status (`NOT AVBL`, `ONLY AVBL`)
2. Exception airports (`EXC ARR (EDDK, EDGS)`)
3. Flight level constraints (`ABV FL245`, `BTN FL305-FL660`)
4. VIA waypoints (`VIA (KOMOB DCT IBESA)`)
5. Aircraft types (`TYP (A320, B738)`)

**Expected Results**:
- 84% coverage with 95% accuracy
- Python regex-based parsers
- Hybrid schema (original text + parsed fields)
- Alternative: AST parser for 100% coverage

---

### 4. **`postgresql_implementation.md`** - PostgreSQL Setup
**Phase 1: Database Setup & Schema Creation**

Complete PostgreSQL implementation guide:
- Installation instructions (macOS)
- Directory structure
- Complete DDL schema (8 tables, 15+ indexes)
- Python connection manager
- Requirements and dependencies

**Includes**:
- Schema SQL with all tables, indexes, views, triggers
- Connection manager with context managers
- Configuration with environment variables
- Schema creation script

---

### 5. **`docker_setup_walkthrough.md`** - Docker Implementation
**Complete Docker Containerization Walkthrough**

Documents the Docker setup with:
- 3 services (PostgreSQL, Python app, pgAdmin)
- Volume mounts for live development
- Health checks and dependencies
- Quick start automation

**Covers**:
- All files created (docker-compose.yml, Dockerfile, etc.)
- Database schema highlights
- Usage examples
- Development workflow
- Troubleshooting guide

---

## 🎯 Implementation Status

| Phase | Status | Documents |
|-------|--------|-----------|
| **Planning** | ✅ Complete | All 5 documents |
| **Phase 1: Setup** | ✅ Complete | Docker + PostgreSQL |
| **Phase 2: ETL** | ⏳ Pending | Text parsing + Data loaders |
| **Phase 3: Integration** | ⏳ Pending | route_engine integration |
| **Phase 4: Testing** | ⏳ Pending | Verification + Optimization |

---

## 📊 Quick Reference

### Database Schema Summary
- **Tables**: 8 core tables
- **Indexes**: 15+ (partial, GIN, composite)
- **Views**: 3 helper views
- **Rows**: ~150K (after ETL)
- **Size**: ~30-40MB

### Technology Stack
- **Database**: PostgreSQL 18
- **Language**: Python 3.14
- **Container**: Docker + Docker Compose
- **Libraries**: psycopg2, pandas, python-dotenv

### Key Design Decisions
1. **Simplified normalized approach** for A* performance
2. **Hybrid text parsing** (84% coverage, 95% accuracy)
3. **PostgreSQL** for production features (GIN indexes, arrays)
4. **Docker** for easy deployment and development

---

## 🔗 Related Documentation

- [Docker Setup Guide](../../docker/DOCKER_SETUP.md)
- [Route Engine README](../../route_engine/README.md)
- [Project README](../../README.md)

---

## 📝 Notes

These documents were created during the planning phase and serve as:
- Technical specifications for implementation
- Design rationale and trade-off analysis
- Reference for future development
- Onboarding material for new developers

All documents are also available in the `.gemini` directory (hidden by default).
