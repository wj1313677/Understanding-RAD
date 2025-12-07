"""
PostgreSQL Database Connection Manager
Handles connection pooling and query execution for route restrictions database
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os


class DatabaseConnection:
    """Singleton database connection manager"""
    
    def __init__(self, config=None):
        self.config = config or {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'route_restrictions'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
        }
        self._conn = None
    
    def connect(self):
        """Establish database connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**self.config)
        return self._conn
    
    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()
    
    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """
        Context manager for database cursor
        
        Args:
            dict_cursor: If True, return rows as dictionaries
        
        Yields:
            Database cursor
        """
        conn = self.connect()
        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def execute_script(self, sql_file_path):
        """
        Execute SQL script from file
        
        Args:
            sql_file_path: Path to SQL file
        """
        with open(sql_file_path, 'r') as f:
            sql = f.read()
        
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(sql)
        print(f"✅ Executed: {sql_file_path}")
    
    def execute_query(self, query, params=None, fetch=True):
        """
        Execute a single query
        
        Args:
            query: SQL query string
            params: Query parameters (tuple or dict)
            fetch: If True, return results
        
        Returns:
            Query results if fetch=True, else None
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
    
    def execute_many(self, query, params_list):
        """
        Execute query with multiple parameter sets (bulk insert)
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.executemany(query, params_list)


# Singleton instance
db = DatabaseConnection()
