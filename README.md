# VB-G RAM G Convergence Management System

## Setup

1. Create a Supabase project and execute `database/schema.sql` in the SQL editor.
2. Run `database/seed.sql` to populate initial data.
3. Copy `.env.example` to `.streamlit/secrets.toml` and fill in your Supabase URL and keys.
4. Install dependencies: `pip install -r requirements.txt`
5. Run the app: `streamlit run app.py`

## Production Deployment

- Deploy to Streamlit Community Cloud by connecting your GitHub repo.
- Set the secrets in the Streamlit dashboard (identical to `secrets.toml`).
- Ensure Row Level Security (RLS) is active in Supabase.
- Create user accounts via the built-in Supabase Auth (or invite) and assign roles in the `users` table.

## Building Additional Modules

Each module follows the same pattern:
- Add a new Python file in `modules/`
- Define a `show()` function
- Import and call it from `app.py` navigation
- Use Supabase queries with proper RLS filtering
- Use `require_role()` to guard access
