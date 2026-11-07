"""radar-online tables, registered on SQLModel.metadata when imported (FEAT-037 adds them).

Never import radar_core.models here or in Alembic: radar-online must not host the local
audit data (ADR 0014).
"""
