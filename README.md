# Research Paper Platform - Backend

Backend services for the Research Paper Platform built with FastAPI.

## Project Structure

```
backend/
├── api-gateway/          # Main FastAPI gateway
├── services/             # Microservices
│   ├── user-service/    # Authentication & user management
│   ├── content-service/ # arXiv integration
│   ├── ai-service/       # AI chat functionality
│   └── search-service/   # Search & recommendations
├── shared/              # Shared utilities and models
└── docker-compose.yml   # Local development setup
```

## Setup

1. **Install dependencies:**
   ```bash
   cd api-gateway
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp api-gateway/.env.example api-gateway/.env
   # Edit .env with your Supabase credentials
   ```

3. **Setup Supabase:**
   - Create a Supabase project
   - Run the SQL schema from `shared/schema.sql` in the Supabase SQL editor
   - Copy your project URL and anon key to `.env`

4. **Run the API gateway:**

   **Option 1: Using the run script (recommended)**
   ```bash
   cd backend
   chmod +x run.sh
   ./run.sh
   ```

   **Option 2: Set PYTHONPATH and run**
   ```bash
   cd backend
   export PYTHONPATH="${PWD}:${PYTHONPATH}"
   cd api-gateway
   python main.py
   ```

   **Option 3: Run with uvicorn directly**
   ```bash
   cd backend
   export PYTHONPATH="${PWD}:${PYTHONPATH}"
   cd api-gateway
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Using Docker Compose:**
   ```bash
   cd backend
   docker-compose up
   ```

## API Documentation

Once running, visit:
- API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Services

### User Service
- `GET /api/users/me` - Get user profile
- `PUT /api/users/me` - Update user profile

### Content Service
- `GET /api/papers` - List/search papers
- `GET /api/papers/{arxiv_id}` - Get paper details
- `GET /api/papers/trending` - Get trending papers

### AI Service
- `POST /api/ai/chat` - Chat with paper
- `GET /api/ai/conversations/{paper_id}` - Get conversation history

## Development

Each service is a separate FastAPI router that can be developed independently. The API gateway combines all services into a single application.

## Troubleshooting

### ModuleNotFoundError: No module named 'shared'

If you get this error, make sure you're either:
1. Using the `run.sh` script from the `backend/` directory
2. Setting `PYTHONPATH` to include the `backend/` directory
3. Running from the `backend/` directory with the path set

The `shared` module is in the parent directory, so Python needs to know where to find it.
