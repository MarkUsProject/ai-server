# markus-ai-server

## Developers

To install project dependencies, including development dependencies:

```console
$ source venv/bin/activate;

$ pip install -e '.[dev]'
```

To install pre-commit hooks:

```console
$ pre-commit install
```

To run the test suite:

```console
$ pytest
```

To run locally:

Pre-requisites:

Must have redis and lamma server up and running.


```console
$ docker compose -f opentelemetry_collector/docker-compose.yml up -d

$ REDIS_URL='redis://localhost:6379' LLAMA_SERVER_URL='http://localhost:11434' python3 -m ai_server.__main__
```

Send Request:

Example

```curl
curl --location 'localhost:5000/chat' \
--form 'content="asdf asdf asdasdf ad"'
```
