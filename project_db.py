import psycopg2
from faker import Faker
import random
from datetime import datetime, timezone

fake = Faker()
categories = ['database', 'machine-learning', 'web-dev', 'security',
              'cloud', 'devops', 'mobile', 'data-science', 'networking', 'open-source']

conn = psycopg2.connect("dbname=dsci551_project")
cur = conn.cursor()

rows = [(
    fake.sentence(nb_words=6),
    random.choice(categories),
    fake.paragraph(nb_sentences=5),
    fake.date_time_between(start_date='-5y', end_date='now', tzinfo=timezone.utc),
    fake.name()
) for _ in range(100_000)]

cur.executemany(
    "INSERT INTO posts (title, category, content, published_at, author) VALUES (%s,%s,%s,%s,%s)",
    rows
)
conn.commit()