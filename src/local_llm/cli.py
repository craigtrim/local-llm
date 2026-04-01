from rich.console import Console
from rich.markdown import Markdown

from . import archive, client, obsidian
from .config import (
    OBSIDIAN_ENABLED,
    OBSIDIAN_VAULT_DIR,
    SUMMARIZE_PROMPT,
    SUMMARY_MODEL,
    SYSTEM_PROMPT,
    TITLE_PROMPT,
)
from .history import ConversationHistory

console = Console()


def _archive(history: ConversationHistory, model: str | None = None) -> None:
    try:
        path = archive.save(history.messages, title=history.title)
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

    def title_fn(messages: list[dict]) -> str:
        return client.generate_title(messages, summary_model, TITLE_PROMPT)

    history = ConversationHistory(
        context_limit=context_length,
        summarize_fn=summarize_fn,
        on_truncate=on_truncate,
        title_fn=title_fn,
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
    prev_title: str | None = None

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
                prev_title = None
                console.print("[dim]Conversation cleared.[/]\n")
                continue
            if stripped == "/status":
                s = history.stats()
                console.print(
                    f"[bold]Context:[/] {s['pct_used']}% used "
                    f"({s['tokens_used']:,} / {s['token_budget']:,} tokens)"
                )
                console.print(f"[bold]Q&A exchanges:[/] {s['qa_count']}")
                console.print(f"[bold]Summaries:[/] {s['summary_count']}")
                if s["title"]:
                    console.print(f"[bold]Title:[/] {s['title']}")
                console.print()
                continue
            if stripped == "/model":
                _archive(history, model)
                new_model = select_model()
                if new_model:
                    model = new_model
                    history = new_session(model)
                    prev_title = None
                continue
            if user_input.strip().startswith("/title"):
                new_title = user_input.strip()[len("/title"):].strip()
                if new_title:
                    history.set_title(new_title)
                    prev_title = new_title
                    console.print(f"[dim]Chat title set: {new_title}[/]\n")
                else:
                    if history.title:
                        console.print(f"[bold]Title:[/] {history.title}\n")
                    else:
                        console.print("[dim]No title yet. Usage: /title <name>[/]\n")
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

            if history.title and history.title != prev_title:
                console.print(f"[dim]Chat title: {history.title}[/]")
                prev_title = history.title

            console.print()
            console.print(Markdown(response_text))
            console.print()
    except KeyboardInterrupt:
        pass

    _archive(history, model)
    console.print("\n[dim]Goodbye.[/]")
