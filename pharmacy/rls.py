"""PostgreSQL row-level security policies for tenant-owned tables."""

from django.db import connections

TENANT_TABLES = (
    "pharmacy_membership",
    "pharmacy_manufacturer",
    "pharmacy_generic",
    "pharmacy_brand",
    "pharmacy_medicine",
    "pharmacy_stockbatch",
    "pharmacy_customer",
    "pharmacy_sale",
    "pharmacy_saleitem",
    "pharmacy_dueledger",
    "pharmacy_stockmovement",
    "pharmacy_cashsession",
)


def install_postgres_tenant_policies(sender: object, using: str, **kwargs: object) -> None:
    """Enable forced RLS and trigram search indexes after tables are created."""
    connection = connections[using]
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for table in TENANT_TABLES:
            cursor.execute(
                f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'
            )
            cursor.execute(
                f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'
            )
            policy = f"{table}_tenant_isolation"
            cursor.execute(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"')
            cursor.execute(
                f"""
                CREATE POLICY "{policy}" ON "{table}"
                USING (
                    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                )
                WITH CHECK (
                    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                )
                """
            )
        for column in ("name_en", "name_bn"):
            index = f"pharmacy_medicine_{column}_trgm"
            cursor.execute(
                f'CREATE INDEX IF NOT EXISTS "{index}" '
                f'ON "pharmacy_medicine" USING gin ("{column}" gin_trgm_ops)'
            )
