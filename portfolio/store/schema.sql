-- Portfolio DB: universe + allocation answers.
-- Prices stay in MarketData DuckDB (read-only).

CREATE TABLE IF NOT EXISTS instruments (
    ticker TEXT PRIMARY KEY,
    sector TEXT,
    tags TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS universes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS universe_members (
    universe_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    PRIMARY KEY (universe_id, ticker),
    FOREIGN KEY (universe_id) REFERENCES universes(id),
    FOREIGN KEY (ticker) REFERENCES instruments(ticker)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    universe TEXT NOT NULL,
    strategy TEXT,
    params_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    as_of TEXT,
    lookback_days INTEGER,
    n_symbols INTEGER,
    source TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS allocations (
    run_id INTEGER NOT NULL,
    strategy TEXT NOT NULL,
    ticker TEXT NOT NULL,
    weight REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, strategy, ticker),
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (ticker) REFERENCES instruments(ticker)
);
