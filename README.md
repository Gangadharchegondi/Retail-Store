# Retail Store SmartRetail

AI-powered smart retail checkout system built with FastAPI, Jinja templates, and a browser-based scanner flow.

## Features

- Product catalog and searchable storefront
- Cart management with live totals
- Barcode scanning via camera feed
- Cashfree-based checkout flow
- Customer profile, orders, and invoice views
- SQLite-backed persistence

## Tech Stack

- Python 3.10+
- FastAPI
- Jinja2
- SQLite / SQLAlchemy
- OpenCV
- Cashfree integration

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Create a `.env` file in the project root if you need custom settings.
4. Start the app:

```bash
python main.py
```

The app runs on `http://127.0.0.1:8000` by default.

## Environment Variables

The app supports these common settings:

- `DATABASE_URL`
- `STORE_NAME`
- `STORE_EMAIL`
- `STORE_PHONE`
- `API_HOST`
- `API_PORT`
- `DEBUG`
- `SESSION_SECRET_KEY`
- `SESSION_MAX_AGE_SECONDS`
- `ALLOWED_ORIGINS`
- `CASHFREE_APP_ID`
- `CASHFREE_SECRET_KEY`
- `CASHFREE_ENV`
- `CASHFREE_API_VERSION`
- `STRIPE_SECRET_KEY`

## Database Seeding

To seed sample products:

```bash
python seed_products.py
```

## Project Structure

- `backend/` - API, services, models, and route handlers
- `frontend/templates/` - HTML templates
- `static/` - CSS, JavaScript, and images
- `tests/` - automated tests

## Notes

- `smart_store.db` is ignored by Git and is safe to recreate locally.
- Camera and payment features may require additional device or provider configuration.