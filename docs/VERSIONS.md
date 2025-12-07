# Version Information

## Current Versions (as of December 2025)

### PostgreSQL
- **Version**: 18.1
- **Released**: November 13, 2025
- **Image**: `postgres:18.1-alpine`
- **Source**: [PostgreSQL Official](https://www.postgresql.org/docs/release/18.1/)

**Key Features in PostgreSQL 18**:
- Major performance improvements
- Enhanced JSON/JSONB capabilities
- Improved query parallelism
- Better memory management
- Advanced partitioning features
- Incremental backup improvements

### Python
- **Version**: 3.14.2
- **Released**: December 5, 2025
- **Image**: `python:3.14-slim`
- **Source**: [Python Official](https://www.python.org/downloads/release/python-3142/)

**Key Features in Python 3.14**:
- Faster startup and import times
- Memory management optimizations
- Enhanced debugging and traceback
- Better multi-interpreter management
- Continued performance improvements
- Improved error messages

### Docker Images
- **PostgreSQL**: `postgres:18.1-alpine` (~95MB)
- **Python**: `python:3.14-slim` (~135MB)
- **pgAdmin**: `dpage/pgadmin4:latest`

### Python Dependencies
```
psycopg2-binary==2.9.9
pandas==2.1.4
python-dotenv==1.0.0
```

## Version History

| Date | PostgreSQL | Python | Notes |
|------|------------|--------|-------|
| Dec 2025 | 18.1 | 3.14.2 | Latest stable versions |
| Nov 2025 | 18.1 | 3.14.1 | PostgreSQL 18 major release |
| Oct 2025 | 17.7 | 3.14.0 | Python 3.14 major release |
| Dec 2024 | 17.2 | 3.13.1 | Previous stable versions |

## Upgrade Notes

### PostgreSQL 18.1
- **Major release** with significant new features
- Includes security fixes and 50+ bug fixes
- Safe to upgrade from PostgreSQL 17.x
- Review [migration guide](https://www.postgresql.org/docs/18/release-18.html) for breaking changes
- Recommended to test in development first

### Python 3.14.2
- Second maintenance release of 3.14 series
- Faster startup and import times
- Memory management optimizations
- Backward compatible with 3.13 for most code
- Some C extensions may need recompilation

## Checking Versions

### In Docker Container
```bash
# PostgreSQL version
docker-compose exec postgres psql -U postgres -c "SELECT version();"

# Python version
docker-compose exec app python --version
```

### Expected Output
```
PostgreSQL 18.1 on x86_64-pc-linux-musl, compiled by gcc ...
Python 3.14.2
```

## Update Strategy

To update to newer versions in the future:

1. **Check for updates**:
   - PostgreSQL: https://www.postgresql.org/support/versioning/
   - Python: https://www.python.org/downloads/

2. **Update docker-compose.yml**:
   ```yaml
   postgres:
     image: postgres:18.1-alpine  # Update version here
   ```

3. **Update Dockerfile**:
   ```dockerfile
   FROM python:3.14-slim  # Update version here
   ```

4. **Rebuild containers**:
   ```bash
   cd docker
   docker-compose down
   docker-compose up -d --build
   ```

## Compatibility

### PostgreSQL 18.1
- ✅ Compatible with psycopg2 2.9.9
- ✅ Compatible with pgAdmin 4
- ✅ Supports all PostgreSQL 17 features
- ✅ Can restore from PostgreSQL 17 dumps
- ⚠️ Review breaking changes from 17 to 18

### Python 3.14.2
- ✅ Compatible with psycopg2-binary 2.9.9
- ✅ Compatible with pandas 2.1.4
- ✅ Compatible with python-dotenv 1.0.0
- ✅ Most packages now have 3.14 wheels
- ⚠️ Some older C extensions may need updates

## Known Issues

### Python 3.14
- Most packages now support 3.14
- If you encounter compatibility issues, can fall back to Python 3.13:
  ```dockerfile
  FROM python:3.13-slim
  ```

### PostgreSQL 18
- New major version - test thoroughly before production
- Review migration guide for any breaking changes
- All features we use are stable and well-supported

## References

- [PostgreSQL 18 Release Notes](https://www.postgresql.org/docs/18/release-18.html)
- [Python 3.14 What's New](https://docs.python.org/3.14/whatsnew/3.14.html)
- [Docker Hub - PostgreSQL](https://hub.docker.com/_/postgres)
- [Docker Hub - Python](https://hub.docker.com/_/python)
