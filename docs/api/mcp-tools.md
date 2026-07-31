# Continuum MCP Tool Reference

Continuum exposes four [MCP](https://modelcontextprotocol.io/) tools. The schemas below match the contracts in [SRS.md §7](../../SRS.md#7-api--mcp-tool-contracts) exactly; what this document adds is worked examples and error behavior for anyone actually integrating against it.

All tools require the caller to be an authenticated MCP client with a valid connection to the Continuum MCP server. See [DEPLOYMENT.md](../../DEPLOYMENT.md) for how a client connects.

---

## `store_memory`

Writes a memory row to one of the three tiers.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `tier` | `"working" \| "episodic" \| "semantic"` | yes | Selects the target table |
| `actor_id` | string | yes | Owning actor; all reads are scoped to this value |
| `session_id` | string (UUID) | required for `working`/`episodic` | Groups rows within a session |
| `content` | string | yes | The memory text |
| `key` | string | required for `working` only | Point-lookup key within the session |
| `metadata.outcome` | string | optional, `episodic` only | e.g. `"resolved"`, `"escalated"` |

**Output**

```json
{
  "id": "b3f1...c0a2",
  "tier": "semantic",
  "created_at": "2026-07-30T14:02:11Z",
  "source_tool": "store_memory"
}
```

**Example: storing a durable preference**

```json
{
  "tier": "semantic",
  "actor_id": "user-4471",
  "content": "Prefers email over phone for follow-ups."
}
```

**Errors**

| Condition | Response |
|---|---|
| Missing `actor_id` or `content` | MCP validation error, no write attempted |
| `tier: working` without `key` | MCP validation error, no write attempted |
| Embedding model unreachable (`tier: semantic` only) | MCP tool error; write is not partially committed |

---

## `recall_memory`

Semantic + recency-filtered recall across one or more tiers.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `actor_id` | string | yes | |
| `query` | string | yes | Natural-language recall query |
| `tier_filter` | `"working" \| "episodic" \| "semantic" \| "all"` | no, default `semantic + episodic` | |
| `top_k` | integer | no, default 5, max 20 | |
| `recency_weight` | float 0.0–1.0 | no, default 0.2 | Blends similarity rank with recency |

**Output**

```json
{
  "results": [
    {
      "id": "b3f1...c0a2",
      "tier": "semantic",
      "content": "Prefers email over phone for follow-ups.",
      "similarity_score": 0.87,
      "actor_id": "user-4471",
      "created_at": "2026-07-30T14:02:11Z",
      "source_tool": "store_memory"
    }
  ]
}
```

**Example: recalling context at the start of a new session**

```json
{
  "actor_id": "user-4471",
  "query": "how does this user prefer to be contacted?",
  "top_k": 3
}
```

**Errors**

| Condition | Response |
|---|---|
| `actor_id` matches no rows | Empty `results` array, not an error |
| `top_k > 20` | MCP validation error |

---

## `list_episodes`

Recency-ordered scan of an actor's episodic memory.

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `actor_id` | string | yes | |
| `since` | ISO-8601 timestamp | no | |
| `limit` | integer | no, default 20, max 100 | |

**Output**

```json
{
  "episodes": [
    {
      "episode_id": "9a02...ff31",
      "session_id": "7c4e...11bd",
      "turn_index": 3,
      "role": "user",
      "content": "I reported this exact billing issue last Tuesday.",
      "outcome": null,
      "created_at": "2026-07-28T09:15:02Z"
    }
  ]
}
```

---

## `forget_memory`

Deletes one memory row by exact ID. The caller has to already know `memory_id` and `tier`, typically discovered via a prior `recall_memory` or `list_episodes` call. There's no query-based bulk delete, by design (see `SECURITY.md`).

**Input**

| Field | Type | Required | Notes |
|---|---|---|---|
| `actor_id` | string | yes | |
| `memory_id` | string (UUID) | yes | |
| `tier` | `"working" \| "episodic" \| "semantic"` | yes | |

**Output**

```json
{
  "deleted": true,
  "memory_id": "b3f1...c0a2"
}
```

**Errors**

| Condition | Response |
|---|---|
| `memory_id` doesn't exist, or belongs to a different `actor_id` | `{"deleted": false, "memory_id": "..."}`. Not an exception, since "already gone" is a normal outcome |

---

## Using Continuum from a non-Bedrock MCP client

Continuum's tool surface doesn't assume Bedrock (SRS NFR-PORT-01). To connect from the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) or Claude Desktop, point your MCP client config at the deployed server endpoint (see `DEPLOYMENT.md`). There's no Bedrock-specific code path in the tool implementations to work around.
