from prisma import Prisma

db = Prisma(
    datasource={
        "url": "postgresql://postgres:postgres@localhost:5433/postgres?scheme=public"
    }
)
