# FastAPI Weather Agent

A small asynchronous FastAPI service that looks up a city's current temperature using the free Open-Meteo geocoding and weather APIs. A one-node LangGraph workflow coordinates the lookup and creates a short weather advisory. No API key is required; the service needs internet access to reach Open-Meteo.

## Requirements

- Python 3.10 or newer
- Internet access while the application is running

## Environment Setup

Open a terminal in the project directory (the directory containing `main.py` and `requirements.txt`). Create and activate a virtual environment so the project packages are isolated from other Python projects.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt "uvicorn[standard]"
```

If PowerShell prevents activation because of the current execution policy, either activate the environment from Command Prompt with `.venv\Scripts\activate.bat` or run the interpreter and packages directly as `.venv\Scripts\python.exe`.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt "uvicorn[standard]"
```

## Run the API

From the project directory, with the virtual environment active:

```bash
python -m uvicorn main:app --reload
```

The server listens at `http://127.0.0.1:8000`. The `--reload` option restarts it when source files change; omit that option for a non-development run. Stop the server with `Ctrl+C`.

Open <http://127.0.0.1:8000> in a browser to use the Weather Desk UI. Enter a city and select **Check weather**; the page sends the city to the `POST /weather` endpoint and displays the result or an error. The API and UI are served by the same FastAPI process.

## UI and API Architecture

`main.py` serves `static/index.html` at `GET /`. The page submits the entered city as JSON to `POST /weather`; FastAPI runs the LangGraph workflow and returns either a weather result or an error. Since the UI and API share the same server and origin, no separate frontend server or CORS configuration is needed.

```mermaid
flowchart LR
	User([User])
	UI[Browser UI<br/>static/index.html]

	subgraph App[FastAPI application: main.py]
		Root[GET /<br/>serve UI with FileResponse]
		Endpoint[POST /weather<br/>validate WeatherQuery]
		Graph[Compiled LangGraph]
		Worker[weather_worker]
		Result[WeatherResult JSON]
		NotFound[HTTP 400<br/>city not found]
	end

	Geocoding[Open-Meteo<br/>Geocoding API]
	Forecast[Open-Meteo<br/>Forecast API]

	User -->|Open app| UI
	UI -->|GET /| Root
	Root -->|HTML page| UI
	UI -->|POST /weather with city| Endpoint
	Endpoint -->|AgentState| Graph
	Graph --> Worker
	Worker -->|Search city| Geocoding
	Geocoding -->|Match: coordinates| Worker
	Geocoding -->|No results| Worker
	Worker -->|If match: request temperature| Forecast
	Forecast -->|Current temperature| Worker
	Worker -->|Success or error state| Graph
	Graph -->|Final state| Endpoint
	Endpoint -->|Success| Result
	Result -->|HTTP 200| UI
	Endpoint -->|No city match| NotFound
	NotFound -->|HTTP 400| UI
	UI -->|Render weather or error| User
```

Interactive API documentation is available at:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

## Request the Weather

Send a JSON object with a `city` field to `POST /weather`.

### PowerShell

```powershell
$body = @{ city = "London" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/weather" -Method Post -ContentType "application/json" -Body $body
```

### macOS / Linux / curl

```bash
curl -X POST "http://127.0.0.1:8000/weather" \
	-H "Content-Type: application/json" \
	-d '{"city":"London"}'
```

A successful response has this shape (temperature and location depend on the current API data):

```json
{
	"city": "London, United Kingdom",
	"temperature_c": 18.4,
	"summary": "Current weather in London, United Kingdom: 18.4°C. Pleasant weather."
}
```

If geocoding returns no match, the endpoint responds with HTTP `400` and a detail such as:

```json
{
	"detail": "City 'NotARealCity' not found."
}
```

The request body is validated by FastAPI/Pydantic. For example, a missing `city` field or a value with the wrong type is rejected as an invalid request (`422`). Open-Meteo network or upstream errors may prevent a successful response.

## Request Workflow

This sequence shows one lookup from browser submission through the external API calls and back to the page:

```mermaid
sequenceDiagram
	actor User
	participant UI as Browser UI
	participant API as FastAPI endpoint
	participant Graph as LangGraph
	participant Worker as weather_worker
	participant Geo as Open-Meteo Geocoding
	participant Weather as Open-Meteo Forecast

	User->>UI: Enter city and submit
	UI->>API: POST /weather with city JSON
	API->>API: Validate WeatherQuery
	API->>Graph: ainvoke(AgentState)
	Graph->>Worker: Run weather node
	Worker->>Geo: Search city (count=1)

	alt No matching city
		Geo-->>Worker: No results
		Worker-->>Graph: Error state
		Graph-->>API: Final state with error
		API-->>UI: HTTP 400 with detail
		UI-->>User: Display error
	else City found
		Geo-->>Worker: First match with coordinates
		Worker->>Weather: Request current temperature by coordinates
		Weather-->>Worker: temperature_2m
		Worker->>Worker: Build advisory and report
		Worker-->>Graph: City, temperature, report
		Graph-->>API: Final state
		API->>API: Build WeatherResult
		API-->>UI: HTTP 200 JSON
		UI-->>User: Display city, temperature, summary
	end
```

Temperatures above 30°C produce the “Warm day, keep hydrated.” advisory; other temperatures produce “Pleasant weather.” A request with an invalid body is rejected by FastAPI with HTTP `422` before the LangGraph workflow starts. Open-Meteo network or upstream errors may also prevent a successful response.

## Project Files

```text
.
├── main.py          # FastAPI app, request/response models, and LangGraph workflow
├── static/
│   └── index.html   # Browser UI served at /
├── requirements.txt # Python package dependencies
└── README.md        # Setup and usage instructions
```
