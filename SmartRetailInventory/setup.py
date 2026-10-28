"""Basic setup checker for Smart Retail Inventory.

Run from the project root with:
    python check_setup.py

This script only checks connectivity and schema; it does not insert, update,
or delete application data.
"""

from __future__ import annotations

import sys

from database import get_connection

REQUIRED_COLUMNS = {
    "products": {
        "product_id", "name", "category", "supplier", "supplier_contact",
        "price", "stock", "expiry_date",
    },
    "customers": {"customer_id", "name", "phone"},
    "sales": {
        "sale_id", "invoice_number", "product_id", "customer_id", "quantity",
        "price", "subtotal", "discount_percent", "discount_amount", "total",
        "sale_date",
    },
}


def main() -> int:
    connection = None
    cursor = None
    errors = 0

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT DATABASE()")
        row = cursor.fetchone()
        database_name = row[0] if row else "unknown"
        print(f"PASS: Connected to MySQL database: {database_name}")

        for table, required_columns in REQUIRED_COLUMNS.items():
            try:
                cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                existing_columns = {column[0] for column in cursor.fetchall()}
            except Exception as exc:
                print(f"FAIL: Could not inspect table '{table}': {exc}")
                errors += 1
                continue

            missing = sorted(required_columns - existing_columns)
            if missing:
                print(f"FAIL: Table '{table}' is missing columns: {', '.join(missing)}")
                errors += 1
            else:
                print(f"PASS: Table '{table}' has all required columns.")

        if errors:
            print("\nSetup check found problems. Do not delete or recreate the database.")
            print("Compare the missing columns with your existing database.py and schema.sql.")
            return 1

        print("\nSUCCESS: Basic database setup checks passed.")
        print("This check does not test every app route or sale transaction.")
        return 0

    except Exception as exc:
        print(f"FAIL: Could not connect to MySQL: {exc}")
        print("Check that MySQL is running and database.py has the correct connection settings.")
        return 1

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    sys.exit(main())