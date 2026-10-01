from sqlalchemy import JSON, Column, ForeignKey, ForeignKeyConstraint, Index, Integer, MetaData, String, Table, UniqueConstraint


metadata = MetaData()

campaigns = Table(
    "campaigns", metadata,
    Column("id", String, primary_key=True),
    Column("data", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("active_branch_id", String, nullable=False),
)

branches = Table(
    "branches", metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("parent_branch_id", String, nullable=True),
    Column("forked_at_seq", Integer, nullable=True),
    Column("label", String, nullable=False, default="main"),
)

events = Table(
    "events", metadata,
    Column("campaign_id", String, ForeignKey("campaigns.id"), primary_key=True),
    Column("seq", Integer, primary_key=True),
    Column("branch_id", String, nullable=False),
    Column("type", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("payload_version", Integer, nullable=False, default=1),
    Column("actor_kind", String, nullable=False),
    Column("actor_id", String),
    Column("turn_id", String),
    Column("created_at", String, nullable=False),
    ForeignKeyConstraint(["branch_id"], ["branches.id"]),
    Index("ix_events_branch_seq", "branch_id", "seq"),
    Index("ix_events_turn_id", "turn_id"),
)

turns = Table(
    "turns", metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("branch_id", String, nullable=False),
    Column("status", String, nullable=False),
    Column("started_seq", Integer, nullable=False),
    Column("ended_seq", Integer),
)

chat_messages = Table(
    "chat_messages", metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("branch_id", String, nullable=False),
    Column("seq", Integer, nullable=False),
    Column("session_id", String),
    Column("scene_id", String),
    Column("turn_id", String),
    Column("speaker_kind", String, nullable=False),
    Column("player_id", String),
    Column("character_id", String),
    Column("client_msg_id", String),
    Column("data", JSON, nullable=False),
    UniqueConstraint("campaign_id", "client_msg_id", name="uq_chat_client_msg"),
    Index("ix_chat_branch_seq", "branch_id", "seq"),
    Index("ix_chat_scene", "scene_id"),
    Index("ix_chat_character", "character_id"),
)

players = Table(
    "players", metadata,
    Column("id", String, primary_key=True),
    Column("data", JSON, nullable=False),
)

memberships = Table(
    "memberships", metadata,
    Column("campaign_id", String, ForeignKey("campaigns.id"), primary_key=True),
    Column("player_id", String, ForeignKey("players.id"), primary_key=True),
    Column("data", JSON, nullable=False),
)

play_sessions = Table(
    "play_sessions", metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("data", JSON, nullable=False),
)

scenes = Table(
    "scenes", metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("branch_id", String, nullable=False),
    Column("data", JSON, nullable=False),
)

dice_rolls = Table(
    "dice_rolls", metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("branch_id", String, nullable=False),
    Column("seq", Integer, nullable=False),
    Column("session_id", String),
    Column("scene_id", String),
    Column("turn_id", String),
    Column("character_id", String),
    Column("data", JSON, nullable=False),
    Index("ix_dice_branch_seq", "branch_id", "seq"),
    Index("ix_dice_character", "character_id"),
)

character_sheets = Table(
    "character_sheets", metadata,
    Column("id", String, primary_key=True),
    Column("character_id", String, nullable=False),
    Column("ruleset_id", String, nullable=False),
    Column("ruleset_version", String, nullable=False),
    Column("version", Integer, nullable=False),
    Column("data", JSON, nullable=False),
    Column("derived", JSON, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("updated_by_kind", String, nullable=False),
    Column("updated_by_id", String),
)

sheet_versions = Table(
    "sheet_versions", metadata,
    Column("sheet_id", String, primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("data", JSON, nullable=False),
    Column("reason", String, nullable=False),
    Column("event_seq", Integer),
)