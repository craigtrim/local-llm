from rich.console import Console
from rich.markdown import Markdown

from . import archive, client, obsidian
from .config import (
    OBSIDIAN_ENABLED,
    OBSIDIAN_VAULT_DIR,
    SUMMARIZE_PROMPT,
    SUMMARY_MODEL,
    SYSTEM_PROMPT,
)
from .history import ConversationHistory

console = Console()


def _archive(history: ConversationHistory, model: str | None = None) -> None:
    try:
        path = archive.save(history.messages)
        if path:
            console.print(f"[dim]Archived conversation to {path}[/]")
            if OBSIDIAN_ENABLED and OBSIDIAN_VAULT_DIR:
                obsidian.convert(path, OBSIDIAN_VAULT_DIR, model)
    except Exception as e:
        console.print(f"[dim]Archive failed: {e}[/]")


def select_model() -> str | None:
    models = client.list_models()
    if not models:
        console.print(
            "[bold red]No models found.[/] Is Ollama running? "
            "Try [bold]ollama pull llama3.2:1b[/] first."
        )
        return None

    if len(models) == 1:
        console.print(f"Using model: [bold green]{models[0]}[/]")
        return models[0]

    console.print("\n[bold]Available models:[/]")
    for i, name in enumerate(models, 1):
        console.print(f"  {i}. {name}")

    while True:
        try:
            choice = console.input("\n[bold cyan]Select a model (number): [/]")
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                console.print(f"Using model: [bold green]{models[idx]}[/]")
                return models[idx]
            console.print("[red]Invalid selection.[/]")
        except ValueError:
            console.print("[red]Enter a number.[/]")


def new_session(model: str) -> ConversationHistory:
    context_length = client.get_context_length(model)
    summary_model = SUMMARY_MODEL or model

    def summarize_fn(messages: list[dict]) -> str:
        return client.summarize(messages, summary_model, SUMMARIZE_PROMPT)

    def on_truncate(messages: list[dict]) -> None:
        try:
            path = archive.save(messages)
            if path:
                console.print(f"[dim]Archived conversation to {path}[/]")
                if OBSIDIAN_ENABLED and OBSIDIAN_VAULT_DIR:
                    obsidian.convert(path, OBSIDIAN_VAULT_DIR, model)
        except Exception as e:
            console.print(f"[dim]Archive failed: {e}[/]")

    history = ConversationHistory(
        context_limit=context_length,
        summarize_fn=summarize_fn,
        on_truncate=on_truncate,
    )
    if SYSTEM_PROMPT:
        history.add("system", SYSTEM_PROMPT)
    console.print(f"Context window: [bold]{context_length}[/] tokens\n")
    return history


def main() -> None:
    console.print("[bold]local-llm[/] — chat with local Ollama models\n")

    model = select_model()
    if not model:
        return

    history = new_session(model)

    try:
        while True:
            try:
                user_input = console.input("[bold cyan]You:[/] ")
            except EOFError:
                break

            stripped = user_input.strip().lower()
            if stripped in ("exit", "quit", "/quit", "/exit"):
                break
            if stripped == "/clear":
                _archive(history, model)
                history = new_session(model)
                console.print("[dim]Conversation cleared.[/]\n")
                continue
            if stripped == "/status":
                s = history.stats()
                console.print(
                    f"[bold]Context:[/] {s['pct_used']}% used "
                    f"({s['tokens_used']:,} / {s['token_budget']:,} tokens)"
                )
                console.print(f"[bold]Q&A exchanges:[/] {s['qa_count']}")
                console.print(f"[bold]Summaries:[/] {s['summary_count']}\n")
                continue
            if stripped == "/model":
                _archive(history, model)
                new_model = select_model()
                if new_model:
                    model = new_model
                    history = new_session(model)
                continue
            if not user_input.strip():
                continue

            history.add("user", user_input)

            try:
                with console.status("Thinking..."):
                    messages = history.get_messages()
                    response_text = client.chat(model, messages)
            except Exception as e:
                console.print(f"[bold red]Error:[/] {e}\n")
                continue

            history.add("assistant", response_text)
            console.print()
            console.print(Markdown(response_text))
            console.print()
    except KeyboardInterrupt:
        pass

    _archive(history, model)
    console.print("\n[dim]Goodbye.[/]")
