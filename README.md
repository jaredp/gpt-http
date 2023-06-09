# `gpt-http`

## Requirements

Python v3.11.3, [Poetry](https://python-poetry.org/)

## Installation

```bash
poetry install
```

Then, get an API key from OpenAI and put it in a file called `openai-api-key.txt` in the root directory. You can get an API key from <https://platform.openai.com/account/api-keys>.

## Usage

```bash
poetry run python app.py
```

and go to a url at <http://localhost:7500>

## To test in a live repl

```bash
poetry run python app.py --shell
```

and go to a url at <http://localhost:7500>

## To run from a scripted test

```bash
poetry run python app.py --prerecording=sample2.convo.txt
```

and go to a url at <http://localhost:7500>

## Full options

```bash
$ poetry run python app.py --help
usage: app.py [-h] [--shell] [--confirm] [--prerecording FILENAME]

Have GPT hallucinate a web app

options:
  -h, --help            show this help message and exit
  --shell               Start an interactive repl for each request, like flask shell, where the
                        user can live respond to a request
  --confirm             Wait for the user to accept each GPT suggestion before proceeding
  --prerecording FILENAME
                        Use a prerecorded conversation from a file
```
