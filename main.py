import httpx
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from langgraph.graph import StateGraph, START, END
from pathlib import Path

app = FastAPI()


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

# 1. Pydantic Models
class WeatherQuery(BaseModel):
    city: str

class WeatherResult(BaseModel):
    city: str
    temperature_c: float
    summary: str

class AgentState(BaseModel):
    city: str
    temp: Optional[float] = None
    report: Optional[str] = None
    error: Optional[str] = None


# 2. Graph Node: Calls Free Open-Meteo APIs
async def fetch_weather_node(state: AgentState):
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step A: Get coordinates
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={state.city}&count=1"
        geo_res = (await client.get(geo_url)).json()
        
        if not geo_res.get("results"):
            return {"error": f"City '{state.city}' not found."}
        
        place = geo_res["results"][0]
        lat, lon = place["latitude"], place["longitude"]
        full_name = f"{place['name']}, {place.get('country', '')}"
        
        # Step B: Get live temperature
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m"
        w_res = (await client.get(weather_url)).json()
        temperature = w_res["current"]["temperature_2m"]
        
        # Step C: Simple advisory
        advisory = "Warm day, keep hydrated." if temperature > 30 else "Pleasant weather."
        
        return {
            "city": full_name,
            "temp": temperature,
            "report": f"Current weather in {full_name}: {temperature}°C. {advisory}"
        }


# 3. Build LangGraph
graph_builder = StateGraph(AgentState)
graph_builder.add_node("weather_worker", fetch_weather_node)
graph_builder.add_edge(START, "weather_worker")
graph_builder.add_edge("weather_worker", END)
weather_agent = graph_builder.compile()


# 4. FastAPI Endpoint
@app.post("/weather", response_model=WeatherResult)
async def get_weather(payload: WeatherQuery):
    initial_state = AgentState(city=payload.city)
    final_state = await weather_agent.ainvoke(initial_state)

    if final_state.get("error"):
        raise HTTPException(status_code=400, detail=final_state["error"])

    return WeatherResult(
        city=final_state["city"],
        temperature_c=final_state["temp"],
        summary=final_state["report"]
    )