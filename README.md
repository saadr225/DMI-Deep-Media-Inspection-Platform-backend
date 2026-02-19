<p align="center">
  <h1 align="center">DMI — Digital Media Integrity Platform</h1>
  <p align="center">
    <b>AI-Powered Deepfake Detection, AI-Generated Content Analysis & Digital Media Forensics</b>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Django-5.1-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django">
    <img src="https://img.shields.io/badge/DRF-3.15-A30000?style=for-the-badge&logo=django&logoColor=white" alt="DRF">
    <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
    <img src="https://img.shields.io/badge/TensorFlow-2.19-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white" alt="TensorFlow">
    <img src="https://img.shields.io/badge/PyTorch-2.5-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch">
    <img src="https://img.shields.io/badge/HuggingFace-Transformers-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" alt="HuggingFace">
    <img src="https://img.shields.io/badge/JWT-Auth-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white" alt="JWT">
  </p>
</p>

## Table of Contents

- [About](#about)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Database Setup](#database-setup)
  - [Running the Server](#running-the-server)
- [API Overview](#api-overview)
- [ML Models & Notebooks](#ml-models--notebooks)
- [Admin & Moderation Panels](#admin--moderation-panels)
- [Related Repositories (Frontend)](#related-repositories)
- [Contributing](#contributing)
- [License](#license)

## About

**DMI (Digital Media Integrity)** is a comprehensive full-stack platform designed to combat misinformation by detecting deepfakes, AI-generated images, and AI-generated text. Built as a **Final Year Project (FYP)**, it provides a suite of AI-powered forensic analysis tools wrapped in a modern REST API, along with community-driven features like a public deepfake archive, discussion forum, and knowledge base.

The backend is built with **Django 5.1** and **Django REST Framework**, leveraging state-of-the-art deep learning models including **ResNeXt** for deepfake detection, **Vision Transformer (ViT)** for AI-generated image detection, and **BERT-based transformers** for AI-generated text detection. It also integrates a **facial recognition watch system** powered by DeepFace to alert users when their face appears in a deepfake submission.

## Features

### Core AI/ML Detection

| Feature                            | Model / Approach         | Description                                                                          |
| ---------------------------------- | ------------------------ | ------------------------------------------------------------------------------------ |
| **Deepfake Video/Image Detection** | ResNeXt (CNN)            | Frame-by-frame analysis of videos/images with confidence scoring & Grad-CAM heatmaps |
| **AI-Generated Image Detection**   | Vision Transformer (ViT) | Classifies images as real or AI-generated with confidence scores                     |
| **AI-Generated Text Detection**    | BERT / Transformers      | Detects AI-generated text and predicts the source (Human, GPT, Claude, etc.)         |
| **Metadata Analysis**              | Custom Pipeline          | Extracts and analyzes media file metadata for forensic evidence                      |

### Facial Watch System

- **Face Registration** — Users register their face via embedding vectors (powered by DeepFace)
- **Automatic Scanning** — New PDA submissions are automatically scanned for registered faces
- **Match Notifications** — Users are alerted when their face is detected in a deepfake submission
- **Match History** — Full history of facial matches with confidence scores and face locations

### Public Deepfake Archive (PDA)

- Community-sourced deepfake submissions with moderation workflow
- Category-based organization (Politicians, Celebrities, Influencers, Public Figures)
- Full detection results linked to each submission
- Moderation approval/rejection pipeline

### Community Forum

- Threaded discussions with topic & tag organization
- Nested replies with parent-child relationships
- Like/dislike system and emoji reactions
- Pinning, locking, and solution-marking capabilities
- Moderation queue with approval workflow
- Forum analytics and notification system

### Knowledge Base

- Article management system organized by topics
- File attachments (images, videos, PDFs, documents)
- View count statistics and sharing capabilities
- Admin CRUD operations with rich content editing

### Donation System

- Stripe-integrated checkout for one-time, monthly, and annual donations
- Gift donations with recipient details
- Refund management
- Donation statistics and analytics dashboard

### Public API

- API key management with creation, rotation, and revocation
- Per-key permission scoping (deepfake detection, AI text, AI media)
- Rate limiting with configurable daily quotas
- Usage logging and analytics
- Dedicated middleware for API key authentication

### Authentication & Authorization

- JWT-based authentication (access + refresh tokens) via SimpleJWT
- User registration, login, logout
- Password reset flow via email (Brevo/Sendinblue)
- Role-based access control (Admin, Staff, Moderator, Verified User, User)
- Custom role middleware

### Admin & Moderation Panels

- **Custom Admin Panel** — Full dashboard with user management, PDA management, forum moderation, analytics, donation management, knowledge base CRUD, and moderator management
- **Moderation Panel** — Dedicated panel for moderators with content review queues, reported content, analytics, and search

## Tech Stack

| Layer               | Technology                                                  |
| ------------------- | ----------------------------------------------------------- |
| **Framework**       | Django 5.1, Django REST Framework 3.15                      |
| **Language**        | Python 3.12                                                 |
| **Database**        | PostgreSQL (via psycopg2)                                   |
| **Authentication**  | JWT (SimpleJWT), API Key auth                               |
| **Deep Learning**   | TensorFlow 2.19, PyTorch 2.5, HuggingFace Transformers 4.49 |
| **Computer Vision** | OpenCV, Ultralytics (YOLOv8), DeepFace, MTCNN, RetinaFace   |
| **Explainability**  | Grad-CAM (pytorch-grad-cam)                                 |
| **Payments**        | Stripe                                                      |
| **Email**           | Brevo (Sendinblue) via django-anymail                       |
| **WSGI Server**     | Gunicorn                                                    |
| **CORS**            | django-cors-headers                                         |

## Project Structure

```
DMI_FYP_dj_primary-backend/
├── .env.example                    # Environment variable template
├── Pipfile                         # Pipenv dependency file
├── Pipfile.lock                    # Locked dependency versions
├── requirements.txt                # pip requirements
├── README.md
│
├── DMI_backend/                    # Django project root
│   ├── manage.py                   # Django management script
│   │
│   ├── DMI_backend/                # Project settings & configuration
│   │   ├── settings.py             # Django settings (DB, JWT, email, etc.)
│   │   ├── urls.py                 # Root URL configuration
│   │   ├── wsgi.py                 # WSGI entry point
│   │   └── asgi.py                 # ASGI entry point
│   │
│   ├── api/                        # REST API application
│   │   ├── models.py               # API data models (MediaUpload, Detection Results, Forum, KB, API Keys, etc.)
│   │   ├── serializers.py          # DRF serializers
│   │   ├── urls.py                 # API URL routing
│   │   ├── views/                  # API view modules
│   │   │   ├── auth_views.py       # Authentication endpoints (signup, login, password reset)
│   │   │   ├── user_views.py       # User profile & submission management
│   │   │   ├── semantic_views.py   # ML processing endpoints (deepfake, AI media, AI text, metadata)
│   │   │   ├── pda_views.py        # Public Deepfake Archive endpoints
│   │   │   ├── facial_watch_views.py       # Facial watch registration & matching
│   │   │   ├── community_forum_views.py    # Forum threads, replies, reactions
│   │   │   ├── knowledge_base_views.py     # Knowledge base articles & topics
│   │   │   ├── public_api_views.py         # Public API & API key management
│   │   │   ├── donations_views.py          # Donation/Stripe endpoints
│   │   │   └── helper_views.py             # Utility endpoints (response codes)
│   │   ├── middleware/             # Custom middleware
│   │   │   └── public_api_key_middleware.py # API key auth middleware
│   │   └── migrations/            # Database migrations
│   │
│   ├── app/                        # Core application (admin, moderation, utilities)
│   │   ├── models.py               # Core models (UserData, PasswordReset, ModeratorAction, Donation)
│   │   ├── urls.py                 # Admin & moderation panel URL routing
│   │   ├── signals.py              # Django signals
│   │   ├── admin.py                # Django admin configuration
│   │   ├── controllers/            # Business logic controllers
│   │   │   ├── DeepfakeDetectionController.py          # Deepfake detection pipeline (ResNeXt)
│   │   │   ├── AIGeneratedMediaDetectionController.py  # AI media detection pipeline (ViT)
│   │   │   ├── AIGeneratedTextDetectionController.py   # AI text detection pipeline (BERT)
│   │   │   ├── FacialWatchAndRecognitionController.py  # Face registration & matching (DeepFace)
│   │   │   ├── MediaProcessorController.py             # Video/image frame extraction & processing
│   │   │   ├── MetadataAnalysisController.py           # File metadata extraction
│   │   │   ├── CommunityForumController.py             # Forum business logic
│   │   │   ├── KnowledgeBaseController.py              # Knowledge base operations
│   │   │   ├── PublicAPIController.py                  # Public API business logic
│   │   │   ├── HelpersController.py                    # Utility helpers
│   │   │   └── ResponseCodesController.py              # Standardized response code definitions
│   │   ├── views/                  # Server-rendered views
│   │   │   ├── custom_admin_views.py       # Admin panel views
│   │   │   ├── custom_moderation_views.py  # Moderation panel views
│   │   │   ├── donation_admin_views.py     # Donation admin views
│   │   │   └── base_views.py               # Base views (home)
│   │   ├── templates/              # HTML templates for admin/moderation panels
│   │   ├── templatetags/           # Custom template tags
│   │   ├── utils/                  # Utilities & custom middleware
│   │   ├── management/             # Custom Django management commands
│   │   └── migrations/             # Database migrations
│   │
│   ├── docs/                       # API documentation
│   │   ├── public_api_documentation.md     # Public API docs
│   │   └── donation_api_documentation.md   # Donation API docs
│   │
│   └── templates/                  # Global templates
│       ├── portal.html             # Portal page
│       ├── portal_login.html       # Portal login page
│       └── access_denied.html      # Access denied page
│
├── Hugging_face_helper/            # HuggingFace model download/management utility
│   ├── __init__.py
│   └── helper/                     # Helper script for model downloads
│
└── Model Notebooks/                # Jupyter notebooks for ML model training
    ├── DF_detectection_ResNext_FYP_P1.ipynb           # Deepfake detection (ResNeXt) training
    ├── AIGM_detectection_ResNext_FYP_P2.ipynb         # AI-generated media detection training
    ├── AIGT_detection_bert.ipynb                      # AI-generated text detection (BERT) training
    └── ai-vs-human-generated-images-prediction-vit.ipynb  # ViT image classification training
```

## Getting Started

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 14+**
- **Pipenv** (recommended) or **pip**
- **Stripe Account** (for donation features — [Get test keys](https://dashboard.stripe.com/test/apikeys))
- **HuggingFace Account** (for model downloads — [Get token](https://huggingface.co/settings/tokens))
- **Brevo (Sendinblue) Account** (for email features)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/Spectrewolf8/DMI_FYP_dj_primary-backend.git
   cd DMI_FYP_dj_primary-backend
   ```

2. **Install dependencies**

   Using Pipenv (recommended):

   ```bash
   pipenv install
   pipenv shell
   ```

   Using pip:

   ```bash
   pip install -r requirements.txt
   ```

### Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

| Variable                      | Description                                                 |
| ----------------------------- | ----------------------------------------------------------- |
| `DB_NAME`                     | PostgreSQL database name                                    |
| `DB_USER`                     | PostgreSQL username                                         |
| `DB_PASSWORD`                 | PostgreSQL password                                         |
| `DB_HOST`                     | Database host (default: `localhost`)                        |
| `DB_PORT`                     | Database port (default: `5432`)                             |
| `EMAIL_HOST_BREVO_API_KEY`    | Brevo (Sendinblue) API key for transactional emails         |
| `DEFAULT_FROM_EMAIL`          | Default sender email address                                |
| `STRIPE_PUBLISHABLE_KEY`      | Stripe publishable key (test mode)                          |
| `STRIPE_SECRET_KEY`           | Stripe secret key (test mode)                               |
| `STRIPE_DONATION_SUCCESS_URL` | Redirect URL after successful donation                      |
| `STRIPE_DONATION_CANCEL_URL`  | Redirect URL after cancelled donation                       |
| `HF_TOKEN`                    | HuggingFace API token for model downloads                   |
| `HF_OFFLINE_MODE`             | Set to `True` for offline mode (uses cached models)         |
| `FRONTEND_HOST_URL`           | Frontend application URL (default: `http://localhost:3000`) |

### Database Setup

```bash
cd DMI_backend
python manage.py migrate
python manage.py createsuperuser
```

### Running the Server

```bash
cd DMI_backend
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/`

## API Overview

### Authentication

| Method | Endpoint                            | Description                        |
| ------ | ----------------------------------- | ---------------------------------- |
| `POST` | `/api/user/signup/`                 | Register a new user                |
| `POST` | `/api/user/login/`                  | Login and receive JWT tokens       |
| `POST` | `/api/user/logout/`                 | Logout and blacklist refresh token |
| `POST` | `/api/auth/refresh_token/`          | Refresh JWT access token           |
| `POST` | `/api/user/forgot_password/`        | Request password reset email       |
| `POST` | `/api/user/reset_password/<token>/` | Reset password with token          |

### Media Processing (ML)

| Method | Endpoint                 | Description                           |
| ------ | ------------------------ | ------------------------------------- |
| `POST` | `/api/process/df/`       | Analyze media for deepfakes (ResNeXt) |
| `POST` | `/api/process/ai/`       | Detect AI-generated media (ViT)       |
| `POST` | `/api/process/text/`     | Detect AI-generated text (BERT)       |
| `POST` | `/api/process/metadata/` | Extract and analyze file metadata     |

### Public Deepfake Archive

| Method | Endpoint                 | Description                              |
| ------ | ------------------------ | ---------------------------------------- |
| `GET`  | `/api/pda/search/`       | Browse/search the archive                |
| `GET`  | `/api/pda/details/<id>/` | Get submission details                   |
| `POST` | `/api/pda/submit/`       | Submit a detection result to the archive |

### Facial Watch System

| Method   | Endpoint                      | Description                  |
| -------- | ----------------------------- | ---------------------------- |
| `POST`   | `/api/facial-watch/register/` | Register face for monitoring |
| `GET`    | `/api/facial-watch/status/`   | Check registration status    |
| `DELETE` | `/api/facial-watch/remove/`   | Remove face registration     |
| `GET`    | `/api/facial-watch/history/`  | Get match history            |

### Community Forum

| Method | Endpoint                         | Description                 |
| ------ | -------------------------------- | --------------------------- |
| `GET`  | `/api/forum/threads/`            | List forum threads          |
| `POST` | `/api/forum/threads/create/`     | Create a new thread         |
| `POST` | `/api/forum/threads/<id>/reply/` | Reply to a thread           |
| `POST` | `/api/forum/like/`               | Toggle like on thread/reply |
| `POST` | `/api/forum/reaction/`           | Add emoji reaction          |

### Donations

| Method | Endpoint                              | Description                    |
| ------ | ------------------------------------- | ------------------------------ |
| `POST` | `/api/donations/checkout/`            | Create Stripe checkout session |
| `GET`  | `/api/donations/verify/<session_id>/` | Verify donation completion     |
| `GET`  | `/api/donations/stats/`               | Get donation statistics        |

### Public API (API Key Auth)

| Method | Endpoint                              | Description                    |
| ------ | ------------------------------------- | ------------------------------ |
| `POST` | `/api/api-keys/`                      | Create a new API key           |
| `POST` | `/api/public-api/deepfake-detection/` | Deepfake detection via API key |
| `POST` | `/api/public-api/ai-text-detection/`  | AI text detection via API key  |
| `POST` | `/api/public-api/ai-media-detection/` | AI media detection via API key |

> Full API documentation is available in [`docs/public_api_documentation.md`](DMI_backend/docs/public_api_documentation.md) and [`docs/donation_api_documentation.md`](DMI_backend/docs/donation_api_documentation.md).

---

## ML Models & Notebooks

The `Model Notebooks/` directory contains Jupyter notebooks used for training and evaluating the detection models:

| Notebook                                            | Purpose                               | Architecture             |
| --------------------------------------------------- | ------------------------------------- | ------------------------ |
| `DF_detectection_ResNext_FYP_P1.ipynb`              | Deepfake detection model training     | ResNeXt (CNN)            |
| `AIGM_detectection_ResNext_FYP_P2.ipynb`            | AI-generated media detection training | ResNeXt (CNN)            |
| `AIGT_detection_bert.ipynb`                         | AI-generated text detection training  | BERT (Transformer)       |
| `ai-vs-human-generated-images-prediction-vit.ipynb` | Real vs AI image classification       | Vision Transformer (ViT) |

Trained models are downloaded at runtime via **HuggingFace Hub** and cached locally in `DMI_backend/ML_Models/`.

## Admin & Moderation Panels

The platform includes two server-rendered management panels:

- **Admin Panel** (`/custom-admin/`) — Full platform management including users, PDA submissions, forum, knowledge base, donations, analytics, and moderator management.
- **Moderation Panel** (`/moderation/`) — Content review queues, PDA and forum moderation, reported content, analytics dashboard, and search.

Both panels feature secure login, role-based access, and audit logging of all moderator actions.

## Related Repositories

| Repository                                                                                                   | Description                                                  |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| [DMI Next.js Frontend](https://github.com/Spectrewolf8/DMI-Digital-Media-Integrity-Platform-NextJS-Frontend) | The frontend client for the DMI platform, built with Next.js |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

This project is developed as a **Final Year Project (FYP)** and is released under the [MIT License](LICENSE).
