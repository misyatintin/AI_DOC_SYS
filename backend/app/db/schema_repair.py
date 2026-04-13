from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection


DOCUMENTS_COLUMNS = {
    "content_type": "ALTER TABLE documents ADD COLUMN content_type VARCHAR(255) NULL AFTER file_path",
    "file_size": "ALTER TABLE documents ADD COLUMN file_size INT NULL AFTER content_type",
    "error_message": "ALTER TABLE documents ADD COLUMN error_message TEXT NULL AFTER status",
}

EXTRACTIONS_COLUMNS = {
    "raw_text": "ALTER TABLE extractions ADD COLUMN raw_text TEXT NULL AFTER document_id",
    "missing_fields": "ALTER TABLE extractions ADD COLUMN missing_fields JSON NULL AFTER validation_errors",
    "manually_corrected": "ALTER TABLE extractions ADD COLUMN manually_corrected BOOLEAN NOT NULL DEFAULT FALSE AFTER prompt_version",
    "updated_at": "ALTER TABLE extractions ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER created_at",
}


async def reconcile_schema(connection: AsyncConnection) -> None:
    document_columns = await connection.run_sync(
        lambda sync_conn: {column["name"] for column in inspect(sync_conn).get_columns("documents")}
    )
    extraction_columns = await connection.run_sync(
        lambda sync_conn: {column["name"] for column in inspect(sync_conn).get_columns("extractions")}
    )

    for column_name, statement in DOCUMENTS_COLUMNS.items():
        if column_name not in document_columns:
            await connection.execute(text(statement))

    for column_name, statement in EXTRACTIONS_COLUMNS.items():
        if column_name not in extraction_columns:
            await connection.execute(text(statement))

    if "missing_fields" not in extraction_columns:
        await connection.execute(text("UPDATE extractions SET missing_fields = JSON_ARRAY() WHERE missing_fields IS NULL"))

