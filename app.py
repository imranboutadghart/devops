from flask import Flask, request, redirect, url_for, abort, Response
import secrets
import html
import time

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Replace with your actual PostgreSQL credentials
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://myuser:mysecretpassword@dabase:5432/mydatabase'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Paste(db.Model):
    __tablename__ = 'pastes'

    id = db.Column(db.String(12), primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "content": self.content}


def init_db(retries=30, delay=2):
    """Create tables, retrying until the database is reachable.

    docker-compose `depends_on` only waits for the container to start, not for
    Postgres to accept connections, so the first attempts may fail.
    """
    with app.app_context():
        for attempt in range(1, retries + 1):
            try:
                db.create_all()
                print("database ready: tables created")
                return
            except Exception as e:
                db.session.rollback()
                print(f"db not ready (attempt {attempt}/{retries}): {e}")
                time.sleep(delay)
        print("could not initialize database after retries")


init_db()


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>pastebin</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    background: #1e1e2e; color: #cdd6f4; display: flex; flex-direction: column;
    min-height: 100vh;
  }}
  header {{
    padding: 1rem 1.5rem; border-bottom: 1px solid #313244;
    display: flex; align-items: center; gap: .75rem;
  }}
  header h1 {{ font-size: 1.25rem; margin: 0; color: #89b4fa; }}
  header a {{ color: #94e2d5; text-decoration: none; margin-left: auto; }}
  main {{ flex: 1; padding: 1.5rem; max-width: 900px; width: 100%; margin: 0 auto; }}
  input[type=text] {{
    width: 100%; padding: .75rem 1rem; margin-bottom: .75rem;
    background: #181825; color: #cdd6f4; border: 1px solid #313244;
    border-radius: 8px; font-family: inherit; font-size: 1rem;
  }}
  h2.title {{ margin: 0 0 1rem; color: #f9e2af; font-size: 1.4rem; }}
  textarea {{
    width: 100%; min-height: 50vh; resize: vertical; padding: 1rem;
    background: #181825; color: #cdd6f4; border: 1px solid #313244;
    border-radius: 8px; font-family: inherit; font-size: .95rem; line-height: 1.4;
  }}
  pre {{
    width: 100%; padding: 1rem; background: #181825; border: 1px solid #313244;
    border-radius: 8px; overflow: auto; white-space: pre-wrap; word-break: break-word;
  }}
  .row {{ display: flex; gap: .75rem; align-items: center; margin-top: 1rem; flex-wrap: wrap; }}
  button {{
    background: #89b4fa; color: #1e1e2e; border: 0; padding: .6rem 1.25rem;
    border-radius: 8px; font: inherit; font-weight: 600; cursor: pointer;
  }}
  button:hover {{ background: #b4befe; }}
  .link {{
    margin-top: 1rem; padding: 1rem; background: #181825; border: 1px solid #a6e3a1;
    border-radius: 8px; word-break: break-all;
  }}
  .link a {{ color: #a6e3a1; }}
</style>
</head>
<body>
<header>
  <h1>pastebin</h1>
  <a href="{home}">+ new paste</a>
</header>
<main>
{body}
</main>
</body>
</html>"""


def render(body, **kw):
    return PAGE.format(home=url_for('index'), body=body, **kw)


@app.route("/", methods=["GET"])
def index():
    link = ""
    new_id = request.args.get("created")
    if new_id:
        url = url_for("view_paste", paste_id=new_id, _external=True)
        link = (
            '<div class="link">paste saved &rarr; '
            f'<a href="{html.escape(url)}">{html.escape(url)}</a></div>'
        )
    body = f"""
<form method="post" action="{url_for('create_paste')}">
  <input type="text" name="title" placeholder="title (optional)" maxlength="200">
  <textarea name="content" placeholder="type or paste something here..." autofocus required></textarea>
  <div class="row">
    <button type="submit">create link</button>
  </div>
</form>
{link}
"""
    return render(body)


@app.route("/paste", methods=["POST"])
def create_paste():
    content = request.form.get("content", "")
    title = request.form.get("title", "").strip()[:200]
    if not content.strip():
        return redirect(url_for("index"))

    # generate a short unique id
    for _ in range(10):
        paste_id = secrets.token_urlsafe(6)[:8]
        if db.session.get(Paste, paste_id) is None:
            break
    else:
        abort(500, "could not allocate a paste id")

    try:
        db.session.add(Paste(id=paste_id, title=title or None, content=content))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(500, f"could not save paste: {e}")

    return redirect(url_for("index", created=paste_id))


@app.route("/<paste_id>", methods=["GET"])
def view_paste(paste_id):
    paste = db.session.get(Paste, paste_id)
    if paste is None:
        abort(404)

    if request.args.get("raw") is not None:
        return Response(paste.content, mimetype="text/plain")

    raw_url = url_for("view_paste", paste_id=paste_id, raw="1")
    heading = f'<h2 class="title">{html.escape(paste.title)}</h2>' if paste.title else ""
    body = f"""
{heading}
<div class="row" style="margin-top:0">
  <a href="{raw_url}"><button type="button">raw</button></a>
</div>
<pre>{html.escape(paste.content)}</pre>
"""
    return render(body)


if __name__ == "__main__":
    app.run(debug=True, port=8080, host="0.0.0.0")
