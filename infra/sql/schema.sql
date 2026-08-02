-- Continuum schema. Source of truth for the table definitions is SRS.md §6 --
-- keep this file and that section in sync; don't let them drift.
--
-- The database-level multi-region prerequisite lives in DEPLOYMENT.md §2, not
-- here, since it's a one-time cluster setup step rather than part of the table
-- schema itself, and running it unconditionally on every schema apply would
-- error on a database that's already configured. Don't skip it: a database
-- that never ran ALTER DATABASE ... SURVIVE REGION FAILURE will accept every
-- statement below without complaint and just stay silently single-region --
-- see .archive/LOG.md, 2026-08-01, for exactly how that went unnoticed once.

-- Working memory: short-lived session state
CREATE TABLE IF NOT EXISTS working_memory (
    session_id   UUID NOT NULL,
    key          STRING NOT NULL,
    value        JSONB NOT NULL,
    actor_id     STRING NOT NULL,
    source_tool  STRING NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, key)
) WITH (ttl_expire_after = '30 minutes', ttl_expiration_expression = 'expires_at');

-- Episodic memory: durable interaction log
CREATE TABLE IF NOT EXISTS episodic_memory (
    episode_id   UUID NOT NULL DEFAULT gen_random_uuid(),
    actor_id     STRING NOT NULL,
    session_id   UUID NOT NULL,
    turn_index   INT NOT NULL,
    role         STRING NOT NULL,         -- 'user' | 'agent'
    content      STRING NOT NULL,
    outcome      STRING,                  -- e.g. 'resolved' | 'escalated' | NULL
    source_tool  STRING NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (episode_id),
    INDEX idx_episodic_actor_time (actor_id, created_at DESC)
);

-- Semantic memory: long-term facts/preferences, embedding-indexed
CREATE TABLE IF NOT EXISTS semantic_memory (
    memory_id    UUID NOT NULL DEFAULT gen_random_uuid(),
    actor_id     STRING NOT NULL,
    content      STRING NOT NULL,
    embedding    VECTOR(1024) NOT NULL,   -- amazon.titan-embed-text-v2:0's default output dimension
    confidence   FLOAT NOT NULL DEFAULT 1.0,
    source_tool  STRING NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (memory_id),
    INDEX idx_semantic_actor (actor_id),
    VECTOR INDEX idx_semantic_embedding (embedding vector_cosine_ops)  -- must match recall_memory's <=> operator
);
