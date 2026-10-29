"""
Create a portal user directly in the database (Step 9). Use it for the FIRST admin, before anyone can log in;
after that, admins can create users through POST /api/users.

Run from backend/ (the server may be running or not):
    python -m scripts.create_user --role admin --email admin@company.local --name "Portal Admin"
    python -m scripts.create_user --role resource_manager --email rm@company.local --name "Resource Manager"
    python -m scripts.create_user --secret          # print a new random JWT_SECRET for .env
The password is asked for (twice) and never shown or stored in plain text.
"""
import argparse
import asyncio
import getpass
import secrets

from sqlalchemy import func, select

from app.auth.passwords import hash_password, password_problem
from app.db.enums import UserRole
from app.db.models import User
from app.db.session import SessionLocal, engine, init_db


async def main(email: str, name: str, role: str) -> None:
    await init_db()
    email = email.strip().lower()
    async with SessionLocal() as session:
        if await session.scalar(select(User).where(func.lower(User.email) == email)):
            raise SystemExit(f"A user with email {email} already exists.")
        while True:
            password = getpass.getpass("Password (at least 12 characters): ")
            if problem := password_problem(password):
                print(problem)
                continue
            if getpass.getpass("Repeat the password: ") != password:
                print("The passwords don't match.")
                continue
            break
        session.add(User(email=email, full_name=name, role=UserRole(role), hashed_password=hash_password(password)))
        await session.commit()
    await engine.dispose()
    print(f"Created {role} {email}. Log in at http://127.0.0.1:8010/docs (Authorize) or POST /api/auth/login.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email")
    parser.add_argument("--name", default="Portal Admin")
    parser.add_argument("--role", choices=[r.value for r in UserRole], default=UserRole.ADMIN.value)
    parser.add_argument("--secret", action="store_true", help="print a random JWT_SECRET and exit")
    args = parser.parse_args()
    if args.secret:
        print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
    elif not args.email:
        parser.error("--email is required")
    else:
        asyncio.run(main(args.email, args.name, args.role))
