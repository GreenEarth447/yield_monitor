#!/usr/bin/env bash
# Idempotent PostgreSQL setup for the Yield Monitor project.
# Creates the role and database if they don't already exist.
#
# Requires sudo access to the local `postgres` superuser (the default on Ubuntu
# after `apt install postgresql`).
#
# Usage:
#   ./setup_db.sh

set -euo pipefail

DB_USER="${DB_USER:-sitewise_admin}"
DB_PASS="${DB_PASS:-sitewise_dev_2026}"
DB_NAME="${DB_NAME:-yield_monitor}"

echo "Setting up PostgreSQL: user=$DB_USER db=$DB_NAME"

# 1. Make sure the service is up.
if ! sudo systemctl is-active --quiet postgresql; then
  echo "Starting postgresql service..."
  sudo systemctl start postgresql
fi

# 2. Create the role if it doesn't exist.
ROLE_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")
if [[ "$ROLE_EXISTS" != "1" ]]; then
  echo "Creating role $DB_USER..."
  sudo -u postgres psql -c "CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS' CREATEDB;"
else
  echo "Role $DB_USER already exists — updating password."
  sudo -u postgres psql -c "ALTER ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS' CREATEDB;"
fi

# 3. Create the database if it doesn't exist.
DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")
if [[ "$DB_EXISTS" != "1" ]]; then
  echo "Creating database $DB_NAME owned by $DB_USER..."
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
else
  echo "Database $DB_NAME already exists."
fi

# 4. Make sure the user can do everything inside the DB.
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# 5. Smoke-test the connection.
echo "Verifying connection..."
PGPASSWORD="$DB_PASS" psql -h localhost -U "$DB_USER" -d "$DB_NAME" -c "SELECT 'connected as ' || current_user || ' to ' || current_database();"

echo
echo "Done. Connection string:"
echo "  postgresql+psycopg2://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"
