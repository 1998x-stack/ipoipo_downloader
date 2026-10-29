-- v3.1: one producer per category with recoverable lease.
CREATE TABLE IF NOT EXISTS category_leases (
  category_id TEXT PRIMARY KEY REFERENCES categories(category_id),
  owner TEXT NOT NULL,
  lease_until REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_category_leases_expiry ON category_leases(lease_until);
