# RouteWise

RouteWise helps a truck driver choose between route options using the forecast
weather the truck will actually drive into. For a trip it fetches up to three
routes, samples checkpoints along each one, estimates when the truck reaches each
checkpoint, looks up the forecast for that hour, classifies the risk with the
wind, rain, snow and load rules, and recommends the safest route. A corridor
heatmap shows how conditions change over the next 48 hours.

Stack: Django and Django REST Framework on the backend, React, TypeScript and Vite
on the frontend, react-leaflet with OpenStreetMap tiles for the map. Routing comes
from OpenRouteService or OSRM, geocoding from Nominatim or OpenRouteService, and
weather from Open-Meteo.

## Project layout

```
backend/
  config/         settings, URLs, WSGI
  api/index.py    serverless entry point for Vercel
  apps/common     geo helpers, HTTP client with retries, error handling, caching
  apps/geocoding  Nominatim and OpenRouteService geocoders
  apps/routing    ORS and OSRM providers, checkpoint sampling, ETA profiles
  apps/weather    batched Open-Meteo client
  apps/risk       risk classification rules
  apps/planner    aggregation, ranking and the plan endpoint
  apps/heatmap    corridor grid and the 48-hour forecast endpoint
  apps/demo       simulated storm scenario with recorded routes
  tests/          pytest suite
frontend/
  src/api         typed API client
  src/hooks       TanStack Query hooks
  src/lib         risk thresholds, formatting, polyline decoding
  src/map         Leaflet map, canvas heat layer, markers
  src/components  form, results, legend, heatmap controls
  src/styles      design tokens and styles
```

## Running locally

Requirements: Python 3.11 or newer and Node 20 or newer.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env             # set DJANGO_DEBUG=true for local work
python manage.py runserver 127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173, proxies /api to port 8000
```

### Checks

```bash
cd backend  && pytest && ruff check . && ruff format --check .
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | required unless debug | Django secret key |
| `DJANGO_DEBUG` | `false` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Comma-separated hosts; Vercel and Railway hostnames are added automatically |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Frontend origins |
| `ORS_API_KEY` | empty | Enables OpenRouteService `driving-hgv` routing and its geocoder |
| `NOMINATIM_USER_AGENT` | project identifier | Must identify the deployment. Nominatim returns 403 for placeholder contacts |
| `GEOCODE_COUNTRY_CODES` | empty | Restrict geocoding, for example `us,ca` |
| `REDIS_URL` | empty | Use Redis instead of the per-process LocMem cache |
| `OSRM_BASE_URL`, `OPEN_METEO_BASE_URL`, `ORS_BASE_URL`, `NOMINATIM_BASE_URL` | public endpoints | Provider overrides |
| `HTTP_TIMEOUT_SECONDS`, `HTTP_RETRIES` | `15`, `2` | Upstream timeouts and retries |
| `THROTTLE_GEOCODE`, `THROTTLE_PLAN`, `THROTTLE_HEATMAP` | `60/min`, `20/min`, `20/min` | Rate limits per client |
| `VITE_API_URL` (frontend, build time) | empty | API base URL in production; empty means same origin or the dev proxy |

`backend/.env.example` and `frontend/.env.example` list everything. No secrets are
committed.

## API

Every error uses one shape:

```json
{"error": {"code": "validation_error", "message": "departure_time: Departure time is in the past.", "details": {}}}
```

Codes: `validation_error` (400), `plan_expired` (404), `location_not_found` and
`no_route` (422), `throttled` (429), `provider_error` (502), `server_error` (500).

### GET /api/geocode?q=dallas&limit=5

`q` needs at least three characters. Returns
`{"results": [{"label": "Dallas, Texas, United States", "lat": 32.77, "lng": -96.79}]}`.

### POST /api/plan

```json
{
  "origin": {"label": "Denver, CO", "lat": 39.74, "lng": -104.99},
  "destination": "Chicago, IL",
  "departure_time": "2026-11-01T14:00:00Z",
  "load_weight_lb": 42000,
  "interval_miles": 25,
  "scenario": null
}
```

- `origin` and `destination` accept `{label, lat, lng}` or free text, which is geocoded.
- `departure_time` must be between 15 minutes ago and 48 hours from now.
- `interval_miles` is 10, 25 or 50.
- `scenario` is optional. `null` (the default) uses live data. `"winter_storm"`
  runs the demo scenario described below.

The response contains `plan_id`, `routes` (each with `id`, `geometry` as an encoded
polyline, `distance_mi`, `duration_min`, `checkpoints`, `metrics`, `rank`,
`recommended`), `recommended_route_id`, `ranking`, `explanation`,
`all_routes_no_travel`, `notices` and `warnings`. Each checkpoint has `lat`, `lng`,
`mile`, `segment_miles`, `eta`, `timezone`, `wind_mph`, `gust_mph`, `rain_in_hr`,
`snow_in_hr`, `risk` (1 to 5, or null when weather is missing), `risk_label`,
`driver` and `load_adjusted`. Demo responses also include `"demo": true`,
`"scenario"` and a `"scenario_note"`.

### POST /api/heatmap

```json
{"polylines": ["<encoded>", "<encoded>"], "load_weight_lb": 42000, "start_time": "2026-11-01T14:00:00Z", "scenario": null}
```

`plan_id` with `route_ids` also works while that plan is cached. The response has
`hours` (49 UTC hours from the current hour), `points` (each with `wind`, `rain`,
`snow` and `risk` arrays of 49 values), `spacing_mi`, `buffer_mi`,
`departure_index` and `warnings`. The `scenario` field works as it does on `/api/plan`.

### GET /api/health

Returns `{"status": "ok", "routing_provider": "osrm"}` or `"openrouteservice"`.

## Risk engine

The rules live in `backend/apps/risk/rules.py`.

| Condition | Low (1) | Moderate (2) | High (3) | Severe (4) | No Travel (5) |
|---|---|---|---|---|---|
| Wind (mph) | under 25 | 25 to under 35 | 35 to under 45 | 45 to under 55 | 55 or more |
| Rain (in/hr) | under 0.10 | 0.10 to under 0.25 | 0.25 to under 0.50 | 0.50 to 1.00 | over 1.00 |
| Snow (in/hr) | under 0.5 | 0.5 to under 1.0 | 1.0 to under 2.0 | 2.0 to 3.0 | over 3.0 |

Load rules only apply to wind and can only raise its level:

- 55 mph or more is No Travel for any load.
- 45 to 54 mph with more than 30,000 lb is No Travel.
- 35 to 44 mph with more than 40,000 lb is Severe.

A checkpoint's risk is the highest of the three factors, and the factor that set it
is reported as the driver. Missing weather makes the checkpoint Unknown rather than
failing the plan.

Each checkpoint stands for the road halfway to its neighbours, so the segments add
up to the route length. Miles per level are sums of those segments, and the average
risk is weighted by mileage over the checkpoints with known weather.

## Ranking

Routes are compared in this order:

1. Any No Travel miles puts a route behind every route without them. Among those
   routes, fewer No Travel miles wins.
2. Fewer Severe miles.
3. Fewer High miles.
4. Lower average risk.
5. Shorter duration.

Mileage comparisons use a 0.5 mile tolerance so a difference of one sampling step
does not decide the result. The explanation names the criterion that separated the
recommendation from each alternative and how much slower it is than the fastest
route. If every route has No Travel miles, the explanation starts with a warning
and the routes are still ranked.

## Demo scenario

Live weather is usually calm, so I added a simulated winter storm to show Severe
and No Travel conditions, the load rules and the moving heatmap on demand. The
"Load demo scenario" button fills a Denver to Chicago trip with a 45,000 lb load,
a departure at the next whole hour at least two hours out, and 25 mile checkpoints,
then plans it.

The weather comes from a few storm cells defined in `backend/apps/demo/`. Each cell
has a center, a full-strength core, a linear falloff and an eastward drift, and time
is counted from the departure, so the scenario looks the same on any date. The three
routes were recorded once from OSRM and are replayed from a fixture, so the demo
does not depend on the public routing server.

At 45,000 lb the fastest route runs through the storm core and has Severe and No
Travel miles. The northern route clips the edge and picks up High and Severe miles.
The southern route stays mostly Low and Moderate and is recommended. Dropping the
load to 30,000 lb turns the core's No Travel miles into Severe and the northern
route's Severe miles into High.

The UI labels everything in demo mode as simulated. "Use live data" switches back.
Requests without `scenario` never touch the demo code.

## Design decisions and tradeoffs

- ETAs use the routing engine's own step or segment durations, not a flat speed.
- The heatmap grid (at most 250 points within 25 miles of any route) is fetched once
  per plan with all 49 hours. The slider only redraws a canvas and never refetches.
- I wrote a custom canvas layer instead of using leaflet.heat, because leaflet.heat
  blends by point density and risk needs discrete colours.
- Provider calls sit behind small classes with a shared interface, which keeps
  the planner independent of the providers and makes the tests and the demo
  provider straightforward.
- Risk range boundaries are lower-bound inclusive and upper-bound exclusive, except
  the No Travel cutoffs. Load rules never lower a level.
- Open-Meteo stamps a whole forecast series with one UTC offset, even across a
  daylight saving change, so I decode times with that fixed offset rather than the
  location's time zone.
- The backend is stateless: the frontend sends route polylines to the heatmap
  endpoint, so any server instance can answer it. That is what makes serverless
  hosting work.

## Known limitations

- Without `ORS_API_KEY`, routing uses the public OSRM server with the car profile.
  Durations are optimistic for trucks and there are no truck restrictions.
- OSRM and the public ORS API often return fewer than three alternatives for long
  trips. I fill the gap by routing through detour waypoints on either side of the
  trip midpoint, dropping duplicates and anything longer than 1.5 times the shortest
  route. A notice says when this happened.
- Nominatim allows about one request per second and needs an identifying User-Agent.
  The backend throttles and caches, and the frontend debounces input.
- On serverless hosting the in-memory cache only lives as long as a warm instance,
  and the first request after an idle period is slower. Correctness does not depend
  on the cache; setting `REDIS_URL` improves hit rates.
- A narrow storm cell between two checkpoints 50 miles apart can be missed. The
  10 mile interval and the heatmap reduce this.
- Hours-of-service breaks are not modelled. ETAs assume continuous driving.

## Deployment

### Backend on Vercel

1. Push the repository to GitHub.
2. In Vercel, import the repository and set the root directory to `backend`. Vercel
   reads `backend/vercel.json`, which routes every request to the Django app in
   `api/index.py`.
3. Add environment variables:
   - `DJANGO_SECRET_KEY`: a long random string
   - `DJANGO_DEBUG`: `false`
   - `DJANGO_ALLOWED_HOSTS`: `.vercel.app`
   - `NOMINATIM_USER_AGENT`: an identifier with your repository URL
   - `CORS_ALLOWED_ORIGINS`: the Netlify URL (add it after step 2 of the frontend)
   - `ORS_API_KEY`: optional
4. Deploy and check `https://<project>.vercel.app/api/health`.

### Backend on Railway (alternative)

Create a service from the repository with the root directory set to `backend`.
Railway builds `backend/Dockerfile`, which serves the app with gunicorn on the port
Railway provides. Use the same environment variables, with `DJANGO_ALLOWED_HOSTS`
set to `.up.railway.app`, then generate a public domain for the service.

### Frontend on Netlify

1. In Netlify, import the repository and set the base directory to `frontend`.
   `frontend/netlify.toml` sets the build command, publish directory and SPA redirect.
2. Add `VITE_API_URL` with the backend URL, without a trailing slash.
3. Deploy, then add the Netlify URL to the backend's `CORS_ALLOWED_ORIGINS` and
   redeploy the backend.
