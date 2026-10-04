import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.core.config import settings
from app.models.base import Base
# Import all other models to ensure they are registered with Base.metadata
from app.models.teams import AITeam, InstalledApp, AgentMetric
from app.models.agents import ActivityLog, KnowledgeDocument
from app.models.verticals import ContentPost, Lead, Candidate, Contract, Transaction, Ticket, TicketMessage, AgentMeeting, BusinessProfile
from app.models.workflows import Workflow, WorkflowTask
from app.models.video import VideoProject, VideoAsset, VideoRender
from app.models.deal_room import DealRoom, BuyingCommitteeMember, AccountSignal, DealObjection, DealActivity, SuppressionRecord, EvidenceRecord, CompanySalesContext
from app.models.learning import DecisionRecord, StrategyPerformance, NegativePatternMemory, GlobalStrategyRegistry, GlobalFailurePattern, GlobalSkillPackage
from app.models.memory import GlobalMemory, EpisodicMemory, CrossAgentContext, ManagerFeedback
from app.models import enterprise  # noqa: F401 — registers enterprise tables on Base.metadata
from app.models.boardroom_events import MeetingEvent, MeetingEvidence, MeetingAction  # noqa: F401 — boardroom v2
from app.models import flow_engine  # noqa: F401 — Agent Studio, Flow Engine, Telemetry & Marketplace

target_metadata = Base.metadata

# Set database URL dynamically from app settings
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here will emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
