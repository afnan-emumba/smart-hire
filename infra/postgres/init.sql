-- SmartHire — per-service logical databases
-- Runs once on first Postgres container start.
-- The default DB (POSTGRES_DB) is created by Docker; only additional service DBs are listed here.

CREATE DATABASE user_db;
CREATE DATABASE job_db;
CREATE DATABASE resume_db;
CREATE DATABASE application_db;
CREATE DATABASE notification_db;
