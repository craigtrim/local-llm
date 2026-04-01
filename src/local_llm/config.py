DEFAULT_CONTEXT_TOKENS = 4096
TOKEN_ESTIMATE_RATIO = 4.0
CONTEXT_RESERVE = 512
SYSTEM_PROMPT = "You are a helpful assistant."

ARCHIVE_DIR = "~/.local-llm/archives"
SUMMARY_MODEL = None  # None means use the chat model
SUMMARIZE_PROMPT = (
    "Summarize the following conversation in under 200 words. "
    "Preserve key facts, decisions, and any instructions the user gave. "
    "Respond with only the summary, no preamble."
)
