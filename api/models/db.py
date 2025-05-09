from prisma import Prisma

# TODO: change the hard-coded url to the .env url (in the schema.prisma too)
db = Prisma(datasource={'url': 'postgresql://postgres:postgres@localhost:5433/postgres?scheme=public'})
