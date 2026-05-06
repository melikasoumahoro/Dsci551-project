# PostgreSQL CMS

A Content Management System for blog posts making PostgreSQL's internal behavior observable and measurable through live explain analyze output


## Table of Contents
- [Environment Setup](#environment-setup)
- [Install Dependencies](#install-dependencies)
- [Configure the Project](#configure-the-project)
- [Run the Application](#run-the-application)
- [Reproduce Results](#reproduce-results)
- [Secret Keys & Credentials](#secret-keys--credentials)
- [Dataset](#dataset)
- [Project Structure](#project-structure)


## Environment Setup

### Prerequisites
- PostgreSQL installed and running (tested on PostgreSQL 18.3)
- Python 3.11+
- pip

### Install PostgreSQL (if not already installed)

**macOS Homebrew:**
```bash
brew install postgresql@18
brew services start postgresql@18
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**  
Download the installer from https://www.postgresql.org/download/windows/

**Verify PostgreSQL is running**
```bash
psql --version
psql -c "SELECT version();"
```


### Install Dependencies

```bash
pip install flask psycopg2-binary faker
```


## Configure the project

### 1. Create the database
```bash
createdb dsci551_project
```

### 2. Create the schema
```bash
psql dsci551_project -c "
CREATE TABLE posts (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL,
    content      TEXT,
    published_at DATE NOT NULL,
    author       TEXT
);"
```

### 3. Verify the table was created
```bash
psql dsci551_project -c "\d posts"
```

You should see all 6 columns: `id`, `title`, `category`, `content`, `published_at`, `author`

### 4. Database connection
The application connects to PostgreSQL using the default local connection string:
```
dbname=dsci551_project
```
This assumes PostgreSQL is running locally on the default port and the current system user has access. No password is required for local connections with the default configuration

If your PostgreSQL setup requires a username or password, update the `get_conn()` function in `app.py`:
```python
def get_conn():
    return psycopg2.connect(
        dbname="dsci551_project",
        user="your_username",
        password="your_password",
        host="localhost",
        port=5432
    )
```



## Run the Application

### 1. Load the dataset
```bash
python project_db.py
```
This generates and inserts 100,000 synthetic blog posts; you will see no output while it runs, wait for the terminal prompt to return

### 2. Start Flask app
```bash
python app.py
```
You should see:
```
* Running on http://127.0.0.1:5000
* Debug mode: on
```
Copy the link provided in your browser



## Reproduce Results

The following steps reproduce each key experiment shown in the project:

### Category Filter
1. Open the app → go to Index Manager → click **Drop All Indexes**
2. Go to By Category → select any category → toggle EXPLAIN ANALYZE → click **Run Query**
3. Observe: List of posts and `Seq Scan on posts` + `Sort` node in the plan
4. Go to Index Manager → click Create All Indexes
5. Re-run the same category query
6. Observe: `Index Scan on idx_posts_cat_pub`, Sort node is gone

### Date Range
1. Ensure indexes are created (Index Manager → Create All Indexes)
2. Go to Date Range → set Start: `2023-01-01`, End: `2023-12-31`
3. Toggle EXPLAIN ANALYZE → click **Run Query**
4. Observe: All posts for this year, `Bitmap Heap Scan` & `Bitmap Index Scan on idx_posts_published_at`

### Stale Statistics Misestimation
1. First, reset any previous experiment data in your terminal:
```bash
psql dsci551_project -c "DELETE FROM posts WHERE category = 'new-category';"
psql dsci551_project -c "ANALYZE posts;"
```
2. Go to Stale Stats tab
3. Click Run on Step 1
4. Click Run EXPLAIN on Step 2, observe misestimate
5. Click Run ANALYZE on Step 3
6. Click Run EXPLAIN on Step 4, observe corrected estimate

### Keyword Search
1. Go to Keyword Search → enter the word 'data' for example
2. Toggle EXPLAIN ANALYZE
3. Run Query
4. Observe: posts matching the search, and `Seq Scan`



## Secret Keys & Credentials

This project does not use any secret keys, API keys, tokens, or external credentials

The only configuration required is a local PostgreSQL connection, which uses the system's default PostgreSQL authentication (no password for local connections). If your environment requires credentials, update the `get_conn()` function in `app.py` as described in the [Configure the Project](#configure-the-project) section above.



## Dataset

This project uses synthetic data generated automatically by `project_db.py` using the Faker library

### What the script generates
- 100,000 blog posts with realistic titles, content, authors, and dates
- 10 categories: database, machine-learning, web-dev, security, cloud, devops, mobile, data-science, networking, open-source
- Date range: last 5 years randomly distributed
- ~10,000 rows per category

### How it works
```
project_db.py
  └── connects to dsci551_project
  └── generates 100,000 rows using Faker
  └── bulk inserts using executemany()
  └── commits and closes
```

You do not need to upload or download any dataset file, running `python project_db.py` is sufficient to populate the database before starting the application

> **Note:** If you run `project_db.py` multiple times, it will insert an additional 100,000 rows each time. To reset the dataset:
> ```bash
> psql dsci551_project -c "TRUNCATE posts RESTART IDENTITY;"
> python project_db.py
> ```



## Project Structure

```
dsci551_dbproject/
├── app.py              # Flask backend: all API routes and database logic
├── project_db.py       # Synthetic dataset generator
├── templates/
│   └── index.html      # Single-page frontend
└── README.md           # This file
```
