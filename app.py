from flask import Flask, request, jsonify, render_template
import psycopg2
import psycopg2.extras
import json

app = Flask(__name__)

def get_conn():
    return psycopg2.connect("dbname=dsci551_project")


def run_query(sql, params=None, explain=False):
    """Run a query and optionally capture its plan with EXPLAIN ANALYZE"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    plan = None

    if explain:
        explain_sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
        cur.execute(explain_sql, params)
        plan_raw = cur.fetchone()
        plan = list(plan_raw.values())[0][0] if plan_raw else None
        cur.close()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], plan


# ── Serve frontend ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── List all posts ────────────────────────────────────────────────────────

@app.route('/api/posts')
def list_posts():
    explain = request.args.get('explain') == '1'
    limit = int(request.args.get('limit', 50))
    sql = """
        SELECT id, title, category, author, published_at
        FROM posts
        ORDER BY published_at DESC
        LIMIT %s
    """
    rows, plan = run_query(sql, (limit,), explain=explain)
    for r in rows:
        r['published_at'] = str(r['published_at'])
    return jsonify({"rows": rows, "plan": plan, "count": len(rows)})


# ── Filter by category ────────────────────────────────────────────────────

@app.route('/api/posts/category/<category>')
def filter_by_category(category):
    explain = request.args.get('explain') == '1'
    sql = """
        SELECT id, title, category, author, published_at
        FROM posts
        WHERE category = %s
        ORDER BY published_at DESC
        LIMIT 100
    """
    rows, plan = run_query(sql, (category,), explain=explain)
    for r in rows:
        r['published_at'] = str(r['published_at'])
    return jsonify({"rows": rows, "plan": plan, "count": len(rows)})


# ── Filter by date range ──────────────────────────────────────────────────

@app.route('/api/posts/date-range')
def filter_by_date():
    explain = request.args.get('explain') == '1'
    start = request.args.get('start', '2023-01-01')
    end = request.args.get('end', '2023-12-31')
    sql = """
        SELECT id, title, category, author, published_at
        FROM posts
        WHERE published_at BETWEEN %s AND %s
        ORDER BY published_at DESC
    """
    rows, plan = run_query(sql, (start, end), explain=explain)
    for r in rows:
        r['published_at'] = str(r['published_at'])
    return jsonify({"rows": rows, "plan": plan, "count": len(rows)})


# ── Keyword search ──────────────────────────────────────────────

@app.route('/api/posts/search')
def search_posts():
    explain = request.args.get('explain') == '1'
    keyword = request.args.get('q', '')
    sql = """
        SELECT id, title, category, author, published_at
        FROM posts
        WHERE title ILIKE %s OR content ILIKE %s
        ORDER BY published_at DESC
        LIMIT 100
    """
    pattern = f'%{keyword}%'
    rows, plan = run_query(sql, (pattern, pattern), explain=explain)
    for r in rows:
        r['published_at'] = str(r['published_at'])
    return jsonify({"rows": rows, "plan": plan, "count": len(rows)})


# ── Create post ───────────────────────────────────────────────────────────

@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO posts (title, category, content, published_at, author)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (
        data['title'],
        data['category'],
        data.get('content', ''),
        data.get('published_at', 'now()'),
        data.get('author', 'Anonymous')
    ))
    new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({"success": True, "id": new_id})


# ── Index management ─────────────────────────────────────────────────────────

@app.route('/api/indexes', methods=['POST'])
def manage_indexes():
    action = request.json.get('action')
    conn = get_conn()
    cur = conn.cursor()
    results = []

    if action == 'create':
        indexes = [
            ("idx_posts_category",
             "CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)"),
            ("idx_posts_published_at",
             "CREATE INDEX IF NOT EXISTS idx_posts_published_at ON posts(published_at)"),
            ("idx_posts_cat_pub",
             "CREATE INDEX IF NOT EXISTS idx_posts_cat_pub ON posts(category, published_at DESC)"),
        ]
        for name, ddl in indexes:
            cur.execute(ddl)
            results.append(f"Created: {name}")

    elif action == 'drop':
        for name in ['idx_posts_category', 'idx_posts_published_at', 'idx_posts_cat_pub', 'idx_posts_category_date']:
            cur.execute(f"DROP INDEX IF EXISTS {name}")
            results.append(f"Dropped: {name}")

    elif action == 'analyze':
        cur.execute("ANALYZE posts")
        results.append("ANALYZE completed — statistics refreshed")

    conn.commit()
    conn.close()
    return jsonify({"results": results})


# ── Stale stats experiment ───────────────────────────────────────────────────

@app.route('/api/experiment/stale-stats', methods=['POST'])
def stale_stats_experiment():
    """
    Bulk-insert 50k rows for 'new-category', then query it
    with explain to show planner misestimation before ANALYZE.
    """
    phase = request.json.get('phase')  # 'insert' | 'query_before' | 'analyze' | 'query_after'
    conn = get_conn()
    cur = conn.cursor()

    if phase == 'insert':
        cur.execute("""
            INSERT INTO posts (title, category, content, published_at, author)
            SELECT
                'Stale stats post ' || g,
                'new-category',
                'Content for stale stats experiment post ' || g,
                NOW() - (random() * INTERVAL '365 days'),
                'Test Author'
            FROM generate_series(1, 50000) g
        """)
        conn.commit()
        conn.close()
        return jsonify({"message": "Inserted 50,000 rows for 'new-category' (no ANALYZE run yet)"})

    elif phase in ('query_before', 'query_after'):
        cur.close()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = """
            SELECT title, published_at FROM posts
            WHERE category = 'new-category'
            ORDER BY published_at DESC
            
        """
        explain_sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
        cur.execute(explain_sql)
        plan_raw = cur.fetchone()
        plan = list(plan_raw.values())[0][0] if plan_raw else None
        conn.close()
        return jsonify({"plan": plan, "phase": phase})

    elif phase == 'analyze':
        cur.execute("ANALYZE posts")
        conn.commit()
        conn.close()
        return jsonify({"message": "ANALYZE completed — planner statistics refreshed"})

    conn.close()
    return jsonify({"error": "Unknown phase"})


# ── Index info ───────────────────────────────────────────────────────────────

@app.route('/api/indexes/status')
def index_status():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'posts'
        ORDER BY indexname
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route('/api/posts/categories')
def get_categories():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM posts ORDER BY category")
    cats = [r[0] for r in cur.fetchall()]
    conn.close()
    return jsonify(cats)


if __name__ == '__main__':
    app.run(debug=True)