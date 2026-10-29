"""全部表结构（SQLAlchemy Core），同时是 Alembic 的 target_metadata。

运行时不用 ORM，仍走原生 sqlite3；这里只负责「表长什么样」这一件事，
让 `alembic check` 有可比对的元数据。

FTS5 虚拟表无法用 Table 表达，由 db.FTS_SQL 直接建；Alembic 的 env.py
用 include_object 忽略 fts 及其影子表，否则 check 会把它们判成待删除。
"""
from sqlalchemy import (Column, ForeignKey, Index, Integer, MetaData, Table,
                        Text)

metadata = MetaData()

# ---------- 内容表（由 import_meta.py 从元数据 JSON 导入，只读） ----------

subject = Table(
    "subject", metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("score", Integer),
    Column("status", Text),
    Column("generated_at", Text),
    Column("source_file", Text),
    Column("sort", Integer, nullable=False, default=0),
)

chapter = Table(
    "chapter", metadata,
    Column("id", Text, primary_key=True),
    Column("subject_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("module", Text, nullable=False),
    Column("tier", Integer, nullable=False),
    Column("weight_center", Integer, nullable=False),
    Column("weight_range", Text),          # JSON [lo, hi] 或 NULL
    Column("weight_basis", Text, nullable=False),
    Column("entry_count", Integer, nullable=False),
    Column("note", Text),
    Column("sort", Integer, nullable=False, default=0),
)
Index("idx_chapter_subject", chapter.c.subject_id, chapter.c.sort)

point = Table(
    "point", metadata,
    Column("id", Text, primary_key=True),
    Column("subject_id", Text, nullable=False),
    Column("chapter_id", Text, nullable=False),
    Column("ord", Integer, nullable=False, default=0),
    Column("point", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("explain", Text, nullable=False),
    Column("exam", Text, nullable=False),
    Column("keywords", Text, nullable=False),      # JSON 数组
    Column("priority", Text, nullable=False),
    Column("tags", Text, nullable=False, default="[]"),
    Column("exam_types", Text, nullable=False, default="[]"),
    # 溯源
    Column("source_ref", Text),
    Column("source_file", Text),
    Column("source_section", Text),
    Column("source_basis", Text),
    Column("source_kind", Text),
    # 朗读
    Column("spoken", Text, nullable=False, default=""),
    Column("listen_script", Text, nullable=False, default=""),
    Column("listen_card_id", Text),
    Column("listen_kind", Text),
    Column("tts_enabled", Integer, nullable=False, default=0),
    Column("tts_est_sec", Integer),
    # 证据
    Column("evidence_level", Text, nullable=False, default="pending"),
    Column("evidence_basis", Text, nullable=False, default=""),
    Column("evidence_sources", Text, nullable=False, default="[]"),
)
Index("idx_point_chapter", point.c.chapter_id, point.c.ord)
Index("idx_point_subject", point.c.subject_id)

unit = Table(
    "unit", metadata,
    Column("point_id", Text, nullable=False, primary_key=True),
    Column("idx", Integer, nullable=False, primary_key=True),
    Column("text", Text, nullable=False),
)

card = Table(
    "card", metadata,
    Column("card_id", Text, primary_key=True),
    Column("point_id", Text, nullable=False),
    Column("ord", Integer, nullable=False, default=0),
    Column("kind", Text, nullable=False),
    Column("card_type", Text, nullable=False),
    Column("question", Text, nullable=False),
    Column("answer", Text, nullable=False),
    Column("options", Text, nullable=False, default="[]"),
    Column("answer_points", Text, nullable=False, default="[]"),
    Column("analysis", Text, nullable=False, default=""),
    Column("unit_refs", Text, nullable=False, default="[]"),
    Column("difficulty", Integer),
)
Index("idx_card_point", card.c.point_id, card.c.ord)

media = Table(
    "media", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("point_id", Text, nullable=False),
    Column("idx", Integer, nullable=False),
    Column("kind", Text, nullable=False),
    Column("caption", Text, nullable=False, default=""),
    Column("alt", Text, nullable=False, default=""),
    Column("svg", Text, nullable=False),
)
Index("idx_media_point", media.c.point_id, media.c.idx)

relation = Table(
    "relation", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("point_id", Text, nullable=False),
    Column("kind", Text, nullable=False),      # prerequisite / related / confusable
    Column("target_id", Text),                 # confusable 可空
    Column("name", Text, nullable=False, default=""),
    Column("distinction", Text, nullable=False, default=""),
    Column("idx", Integer, nullable=False, default=0),
)
Index("idx_relation_point", relation.c.point_id, relation.c.kind, relation.c.idx)

# ---------- 运行时表（应用写入） ----------

point_progress = Table(
    "point_progress", metadata,
    Column("point_id", Text, primary_key=True),
    Column("read_at", Text),
    Column("listen_at", Text),
)

unit_progress = Table(
    "unit_progress", metadata,
    Column("point_id", Text, primary_key=True),
    Column("idx", Integer, primary_key=True),
    Column("mastered_at", Text, nullable=False),
)

card_progress = Table(
    "card_progress", metadata,
    Column("card_id", Text, primary_key=True),
    Column("stage", Integer, nullable=False, default=0),
    Column("ease", Integer, nullable=False, default=3),
    Column("interval", Integer, nullable=False, default=0),
    Column("due_at", Text),
    Column("lapses", Integer, nullable=False, default=0),
    Column("reviews", Integer, nullable=False, default=0),
    Column("last_result", Text),
    Column("updated_at", Text, nullable=False),
)

listen_progress = Table(
    "listen_progress", metadata,
    Column("point_id", Text, primary_key=True),
    Column("listen_count", Integer, nullable=False, default=0),
    Column("updated_at", Text, nullable=False),
)

card_listen = Table(
    "card_listen", metadata,
    Column("card_id", Text, primary_key=True),
    Column("listen_count", Integer, nullable=False, default=0),
    Column("updated_at", Text, nullable=False),
)

settings = Table(
    "settings", metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
)

favorites = Table(
    "favorites", metadata,
    Column("kind", Text, primary_key=True),      # point / card
    Column("ref_id", Text, primary_key=True),
    Column("created_at", Text, nullable=False),
)

# ---------- AI 会话表 ----------

conversations = Table(
    "conversations", metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False, default=""),
    Column("point_id", Text),
    #: 绑定到具体题目时按题目归档，一张卡的问答不与其他卡混在一起
    Column("card_id", Text),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("msg_count", Integer, nullable=False, default=0),
)
Index("idx_conv_updated", conversations.c.updated_at)
Index("idx_conv_card", conversations.c.card_id)

messages = Table(
    "messages", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Text,
           ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("related_point_ids", Text, nullable=False, default="[]"),
    Column("source_refs", Text, nullable=False, default="[]"),
    Column("model", Text, nullable=False, default=""),
    Column("truncated", Integer, nullable=False, default=0),
    Column("created_at", Text, nullable=False),
)
Index("idx_msg_conv", messages.c.conversation_id, messages.c.id)

message_points = Table(
    "message_points", metadata,
    Column("message_id", Integer,
           ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
    Column("point_id", Text, primary_key=True),
)
Index("idx_msgpt_point", message_points.c.point_id)


ALL_TABLES = [
    subject, chapter, point, unit, card, media, relation,
    point_progress, unit_progress, card_progress, listen_progress, card_listen, settings,
    favorites, conversations, messages, message_points,
]
