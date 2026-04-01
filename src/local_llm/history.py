from collections.abc import Callable

from .config import CONTEXT_RESERVE, TITLE_AFTER_EXCHANGES, TOKEN_ESTIMATE_RATIO


class ConversationHistory:
    def __init__(
        self,
        context_limit: int,
        summarize_fn: Callable[[list[dict]], str] | None = None,
        on_truncate: Callable[[list[dict]], None] | None = None,
        title_fn: Callable[[list[dict]], str] | None = None,
    ) -> None:
        self._messages: list[dict] = []
        self._context_limit = context_limit
        self._summarize_fn = summarize_fn
        self._on_truncate = on_truncate
        self._title_fn = title_fn
        self._summary_count = 0
        self.title: str | None = None
        self._user_renamed = False

    @property
    def messages(self) -> list[dict]:
        return list(self._messages)

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        if role == "assistant" and not self.title and not self._user_renamed:
            self._maybe_generate_title()

    def set_title(self, title: str) -> None:
        self.title = title
        self._user_renamed = True

    def _maybe_generate_title(self) -> None:
        if not self._title_fn:
            return
        exchange_count = sum(1 for m in self._messages if m["role"] == "user")
        if exchange_count < TITLE_AFTER_EXCHANGES:
            return
        try:
            self.title = self._title_fn(self._messages)
        except Exception:
            pass

    def get_messages(self) -> list[dict]:
        budget = self._context_limit - CONTEXT_RESERVE
        if self._estimate_tokens(self._messages) <= budget:
            return list(self._messages)
        return self._truncate(budget)

    def _estimate_tokens(self, messages: list[dict]) -> int:
        return int(sum(len(m["content"]) / TOKEN_ESTIMATE_RATIO for m in messages))

    def _truncate(self, budget: int) -> list[dict]:
        if self._on_truncate:
            self._on_truncate(list(self._messages))

        has_system = self._messages and self._messages[0]["role"] == "system"
        system = [self._messages[0]] if has_system else []
        conversation = self._messages[1:] if has_system else list(self._messages)

        evicted: list[dict] = []
        while conversation and self._estimate_tokens(system + conversation) > budget:
            evicted.append(conversation.pop(0))

        if evicted and self._summarize_fn:
            try:
                summary = self._summarize_fn(evicted)
                self._summary_count += 1
                summary_msg = {
                    "role": "system",
                    "content": f"[Summary of earlier conversation]\n{summary}",
                }
            except Exception:
                summary_msg = {
                    "role": "system",
                    "content": "[Earlier conversation history was truncated to fit the context window.]",
                }
        else:
            summary_msg = {
                "role": "system",
                "content": "[Earlier conversation history was truncated to fit the context window.]",
            }

        return system + [summary_msg] + conversation

    def stats(self) -> dict:
        tokens_used = self._estimate_tokens(self._messages)
        budget = self._context_limit - CONTEXT_RESERVE
        qa_count = sum(1 for m in self._messages if m["role"] == "user")
        return {
            "tokens_used": tokens_used,
            "token_budget": budget,
            "tokens_remaining": max(0, budget - tokens_used),
            "pct_used": min(100.0, round(tokens_used / budget * 100, 1)) if budget > 0 else 0,
            "qa_count": qa_count,
            "summary_count": self._summary_count,
            "title": self.title,
        }
