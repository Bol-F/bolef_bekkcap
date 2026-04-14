# Qabila Smart Farm

Qabila Smart Farm is a smart agriculture web platform that helps farmers monitor fields and make better decisions using satellite data, soil measurements, weather forecasts, yield prediction, and AI-style recommendations.

The system is designed for a hackathon MVP, but the backend structure is modular and can be extended later.

## Project Idea

Farmers often need fast information about field health, irrigation needs, and possible crop stress. Qabila Smart Farm combines:

- Sentinel-2 satellite data for vegetation health using NDVI
- Sentinel-1 radar concept for future soil moisture analysis
- Soil monitoring data such as moisture, pH, NPK, and temperature
- Weather forecast data for irrigation decisions
- Machine learning for crop yield prediction
- AI-style explanation for simple farmer-friendly recommendations

The goal is to turn complex agronomic and satellite data into clear actions.

## Main Features

### Farm Management

- User registration and login
- JWT authentication
- CRUD for farms
- CRUD for fields
- CRUD for crops
- CRUD for animals
- CRUD for activity logs
- User profile management
- Per-user data isolation

Each user can access only their own farms, fields, crops, animals, activities, and records.

### Field Mapping

Fields can store geographic information:

- latitude
- longitude
- polygon coordinates
- bounding box values
- approximate polygon area

This allows fields to be selected on a map and analyzed with satellite data.

### Soil Monitoring

The `soil_monitoring` app stores field soil measurements:

- soil type
- moisture percentage
- pH level
- nitrogen
- phosphorus
- potassium
- temperature
- sample date
- notes

Soil measurements are connected to `farm.Field` and can optionally be connected to `YieldRecord`.

### NDVI Satellite Monitoring

The `ndvi` app connects satellite analytics to existing farm fields.

Supported data source modes:

- `synthetic` — demo data, works without credentials
- `huggingface` — optional dataset-backed mode
- `sentinel_api` — live Sentinel Hub / Copernicus mode

NDVI features:

- fetch NDVI records for a field
- store NDVI mean/min/max/std
- get NDVI time series
- analyze vegetation trend
- detect sudden drops or abnormal values
- generate field-level NDVI analysis
- optional PNG NDVI map endpoint

### Yield Prediction

The project includes a CatBoost-based yield prediction service using:

- crop type
- farm area
- irrigation type
- fertilizer used
- pesticide used
- soil type
- season
- water usage

The prediction result is saved into `YieldRecord`.

### Weather-Based Irrigation Status

The backend can call Open-Meteo forecast data and calculate watering status based on:

- precipitation forecast
- evapotranspiration
- temperature

Possible statuses:

- `water_now`
- `watch`
- `rain_expected`
- `no_need`
- `unknown`

## Tech Stack

- Python
- Django
- Django REST Framework
- Simple JWT
- dj-rest-auth
- django-allauth
- drf-spectacular
- django-cors-headers
- SQLite / PostgreSQL-ready settings
- CatBoost
- pandas
- scikit-learn
- Sentinel Hub / Copernicus Data Space
- Open-Meteo API

## Project Structure

```text
bolef_bekkcap/
├── config/
├── farm/
├── soil_monitoring/
├── ndvi/
├── datasets/
├── ml_artifacts/
├── ml_experiments/
├── media/
├── staticfiles/
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/cursor-uzbekistan/qabila.git
cd qabila
```

### 2. Create virtual environment

```bash
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

or Git Bash:

```bash
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

Copy `.env.example` to `.env`.

```bash
copy .env.example .env
```

Example local `.env`:

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

DB_ENGINE=sqlite

CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOW_CREDENTIALS=True

NDVI_DATA_SOURCE=synthetic
SENTINEL_CLIENT_ID=
SENTINEL_CLIENT_SECRET=
```

Do not commit `.env` to GitHub.

## Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Local server:

```text
http://127.0.0.1:8000/
```

## Seed Demo Data

```bash
python manage.py seed_demo_data
```

Use synthetic mode for demo:

```env
NDVI_DATA_SOURCE=synthetic
```

## API Documentation

Swagger UI:

```text
http://127.0.0.1:8000/swagger/
```

ReDoc:

```text
http://127.0.0.1:8000/redoc/
```

OpenAPI schema:

```text
http://127.0.0.1:8000/api/schema/
```

## Main API Routes

### Farm API

```text
POST   /api/v1/auth/register/
POST   /api/v1/auth/login/
POST   /api/v1/auth/refresh/
POST   /api/v1/auth/logout/
GET    /api/v1/profiles/me/

GET    /api/v1/farms/
POST   /api/v1/farms/

GET    /api/v1/fields/
POST   /api/v1/fields/

GET    /api/v1/crops/
POST   /api/v1/crops/

GET    /api/v1/animals/
POST   /api/v1/animals/

GET    /api/v1/activities/
POST   /api/v1/activities/

GET    /api/v1/yield-records/
POST   /api/v1/yield-records/
POST   /api/v1/yield-records/{id}/predict/

GET    /api/v1/fields/{id}/watering-status/
```

### Soil Monitoring API

```text
GET    /api/v1/soil/measurements/
POST   /api/v1/soil/measurements/
GET    /api/v1/soil/measurements/{id}/
PUT    /api/v1/soil/measurements/{id}/
PATCH  /api/v1/soil/measurements/{id}/
DELETE /api/v1/soil/measurements/{id}/
```

### NDVI API

```text
GET  /api/v1/ndvi/health/

POST /api/v1/ndvi/fields/{field_id}/fetch/
GET  /api/v1/ndvi/fields/{field_id}/timeseries/
GET  /api/v1/ndvi/fields/{field_id}/analysis/
GET  /api/v1/ndvi/fields/{field_id}/map/?date=YYYY-MM-DD

POST /api/v1/ndvi/query/
```

## Example: Create Field

```json
{
  "farm": 1,
  "name": "Demo Field",
  "area": "2.50",
  "soil_type": "loamy",
  "polygon": [
    [69.2400, 41.2990],
    [69.2500, 41.2990],
    [69.2500, 41.3050],
    [69.2400, 41.3050],
    [69.2400, 41.2990]
  ]
}
```

## Example: Fetch NDVI

```http
POST /api/v1/ndvi/fields/1/fetch/
```

```json
{
  "date_from": "2024-03-01",
  "date_to": "2024-10-01",
  "force_refresh": false
}
```

## Example: NDVI Analysis

```http
GET /api/v1/ndvi/fields/1/analysis/?date_from=2024-03-01&date_to=2024-10-01
```

## Sentinel Hub Setup

To use real Sentinel data:

1. Create a Copernicus Data Space account.
2. Open Sentinel Hub Dashboard.
3. Create OAuth client credentials.
4. Put them in `.env`:

```env
NDVI_DATA_SOURCE=sentinel_api
SENTINEL_CLIENT_ID=your_client_id
SENTINEL_CLIENT_SECRET=your_client_secret
```

For hackathon demo, synthetic mode is enough:

```env
NDVI_DATA_SOURCE=synthetic
```

## ML Yield Prediction

The project expects trained CatBoost artifacts inside:

```text
ml_artifacts/
├── yield_catboost_model.cbm
└── yield_catboost_model_meta.json
```

Prediction endpoint:

```http
POST /api/v1/yield-records/{id}/predict/
```

## Security Notes

- Never commit `.env`
- Rotate any credentials that were exposed
- Use a strong `DJANGO_SECRET_KEY` in production
- Do not use `DJANGO_ALLOWED_HOSTS=*` in production
- Keep `CORS_ALLOW_ALL_ORIGINS=False` in production
- Use HTTPS in production

## Demo Flow

1. Register or log in.
2. Create a farm.
3. Create a field with polygon coordinates.
4. Add soil measurement.
5. Fetch NDVI data.
6. Open NDVI time series.
7. Open NDVI analysis.
8. Show watering status.
9. Show yield prediction.
10. Explain recommendation to the farmer.

## Project Value

Qabila Smart Farm helps farmers by combining different data sources into one simple decision-support platform.

Instead of manually understanding satellite imagery, soil data, and weather forecasts, the farmer gets clear insights:

- what is happening in the field
- whether vegetation is healthy
- whether irrigation may be needed
- whether field inspection is recommended
- what actions can be taken next
