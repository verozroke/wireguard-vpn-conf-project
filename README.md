# Project Setup Guide

## 📦 Virtual Environment

**Activate venv**:

```bash
source .venv/Scripts/activate
```

**Deactivate venv**:

```bash
deactivate
```

## 🚀 Running the Development Server

**Start FastAPI development server** (only inside `.venv`):

```bash
fastapi dev main.py
```

**Swagger API documentation** is available at:  
http://127.0.0.1:8000/docs

## 🎨 Formatting Code

**For Linux/macOS**:

```bash
./format.sh
```

**For Windows**:

```bash
format.bat
```

## 🛢️ Database Management

**Run DB server with Docker**:

```bash
docker compose up -d
```

## 🔧 Prisma Management

**Pull database schema into Prisma**:

```bash
prisma db pull
```

**Push Prisma schema changes to database**:

```bash
prisma db push
```

**Generate Prisma Client**:

```bash
prisma generate
```

**Open Prisma Studio (visual DB manager)**:

```bash
prisma studio
```

---

# ✅ Notes

- Always activate your virtual environment before running the dev server or managing dependencies.
- Always format your code before pushing changes.
- Use Prisma commands carefully to avoid overwriting database structure.

---

Хочешь — ещё могу дополнить в конец файл раздел "Project Structure", где будет описание папок (`api/`, `models/`, `routes/`, `dependencies/`).  
Скажешь — добавлю сразу. 🚀
