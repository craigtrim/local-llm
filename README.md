# local-llm

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Ollama](https://img.shields.io/badge/ollama-powered-green.svg)](https://ollama.com)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)]()

A lightweight CLI for chatting with local Ollama models. Built with [Rich](https://github.com/Textualize/rich) for terminal rendering and the [Ollama Python SDK](https://github.com/ollama/ollama-python) for model interaction.

## Features

- **Model selection** from all locally available Ollama models
- **Context-aware history** with automatic summarization when the context window fills up
- **Conversation archiving** to `~/.local-llm/archives/` as JSON
- **Token usage tracking** via `/status`

## Install

```bash
pip install .
```

## Usage

```bash
local-llm
```

### Commands

| Command | Description |
|---------|-------------|
| `/clear` | Archive and reset the conversation |
| `/status` | Show token usage and exchange count |
| `/model` | Switch to a different model |
| `/quit` | Exit the session |

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with at least one model pulled
