# Farm Management API (Django + DRF)

A mini project built with **Django REST Framework** for managing farms, fields, crops, animals, activities, and user profiles.

## Features

- Authentication (Session + Token ready)
- Each user has:
  - Their own **farms**, **fields**, **crops**, **animals**
  - A **profile** with avatar (image upload)
- Activity logs (watering, feeding, vet check, harvesting, etc.)
- Pagination & search (via DRF)
- Swagger & ReDoc API documentation
- PostgreSQL database
- Docker & docker-compose support

---

## Tech Stack

- Python 3.x
- Django 6.x
- Django REST Framework
- PostgreSQL
- drf-yasg (Swagger docs)
- Docker + docker-compose (optional)

---

## Local Setup (without Docker)

### 1. Clone & create virtualenv

```bash
git clone <your-repo-url>
cd <your-project-folder>

python -m venv .venv
source .venv/bin/activate   # on Linux/Mac
# OR
.venv\Scripts\activate      # on Windows
