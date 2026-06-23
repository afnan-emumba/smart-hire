SELECT 'CREATE DATABASE temporal'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'temporal'
)\gexec