# 🌾 Farm API

RESTful API for managing farms, fields, crops, animals, activities, and user profiles.  
Built with **Django 6.0** and **Django REST Framework**, secured with **JWT (djangorestframework-simplejwt)** and documented via **Swagger (drf_yasg)**.

---

## 🚀 Features

- User registration and JWT-based authentication (access/refresh tokens)
- CRUD operations for:
  - Farms
  - Fields (linked to farms)
  - Crops (linked to fields)
  - Animals (linked to farms)
  - Activity logs (linked to farms, optionally to fields/crops/animals)
  - User profile (one profile per user)
- Per-user data isolation:
  - Each user can access **only their own** farms, fields, crops, animals, activities, and profile
- Automatic API documentation with Swagger and ReDoc

---

## 🧱 Tech Stack

- **Backend:** Django 6.0, Django REST Framework
- **Auth:** djangorestframework-simplejwt
- **Docs:** drf_yasg (Swagger / OpenAPI)
- **Database:** SQLite (by default) or PostgreSQL (via `psycopg2`)
- **Static files (production):** WhiteNoise
- **Server (production):** gunicorn
- **Images (avatars):** Pillow

### Main Python dependencies

From `requirements.txt`:

```txt
Django==6.0
djangorestframework==3.16.1
djangorestframework-simplejwt==5.5.1
drf_yasg==1.21.11
gunicorn==23.0.0
whitenoise==6.11.0
pillow==12.0.0
psycopg2==2.9.11
