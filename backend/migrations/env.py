import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, models  # noqa: E402

config_obj = context.config
if config_obj.config_file_name is not None:
    fileConfig(config_obj.config_file_name)

target_metadata = models.metadata

# FTS5 虚拟表及其影子表由 db.FTS_SQL 直接建，不归 Alembic 管；
# 不排除的话 `alembic check` 会把它们判成「库里多出来的表」。
FTS_PREFIXES = ("point_fts", "card_fts")


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and any(name.startswith(p) for p in FTS_PREFIXES):
        return False
    return True


def _url() -> str:
    return f"sqlite:///{config.DB_PATH}"


def run_migrations_offline() -> None:
    context.configure(
        url=_url(), target_metadata=target_metadata, literal_binds=True,
        render_as_batch=True, include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config_obj.get_section(config_obj.config_ini_section) or {}
    section["sqlalchemy.url"] = _url()
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            render_as_batch=True, include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
