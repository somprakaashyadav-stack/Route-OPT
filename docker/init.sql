-- docker/init.sql
-- PostGIS initialisation for Route-OPT

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS routes (
    id          SERIAL PRIMARY KEY,
    job_id      UUID NOT NULL,
    algorithm   VARCHAR(20),
    cost        FLOAT,
    runtime_s   FLOAT,
    co2_kg      FLOAT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS route_nodes (
    id        SERIAL PRIMARY KEY,
    route_id  INTEGER REFERENCES routes(id),
    vehicle   INTEGER,
    sequence  INTEGER,
    node_id   INTEGER
);
