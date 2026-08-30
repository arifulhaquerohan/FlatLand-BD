# Deploying to cPanel

Written for shared cPanel hosting with the "Setup Python App" tool. Allow about thirty
minutes the first time. There is no build step: nothing needs compiling before upload.

---

## Before you start

Have these ready:

- Your cPanel login.
- The project ZIP.
- The domain you are publishing to, for example `xryz.online`.
- Two random keys. Generate them in cPanel Terminal, or locally:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
  Run it twice. One value is `SECRET_KEY`, the other is `DATA_ENCRYPTION_KEY`.
  Keep the second one safe: it decrypts stored phone numbers and emails.

---

## Step 1. Upload the files

1. cPanel then **File Manager**.
2. Go to your home directory and create a folder named `flatlandbd`.
3. Enter it, click **Upload**, choose the ZIP.
4. Back in File Manager, right click the ZIP then **Extract**.
5. Confirm `wsgi.py` and `requirements.txt` sit directly inside `flatlandbd`, not inside a
   nested folder. If they are nested, move everything up one level.
6. Delete the ZIP.

---

## Step 2. Create the Python application

1. cPanel then **Setup Python App** (sometimes "Application Manager").
2. Click **Create Application** and fill in:

   | Field | Value |
   | --- | --- |
   | Python version | 3.11 (recommended, stable; 3.10 or 3.12 also fine) |
   | Application root | `flatlandbd` |
   | Application URL | your domain, path left empty |
   | Application startup file | `wsgi.py` |
   | Application Entry point | `application` |

3. Click **Create**. Leave this page open, you will come back to it.

---

## Step 3. Install the dependencies

On the same page, find **Configuration files**, type `requirements.txt`, click **Add**,
then click **Run Pip Install**. Wait for it to finish.

If it fails on `psycopg2-binary`, you are not using Postgres. Open `requirements.txt`,
put a `#` in front of that one line, save, and run pip install again.

`requirements.txt` ships with every version pinned to a tested, stable stack for
Python 3.11, so a fresh install always matches what was tested. Keep the pins in
place unless you have a specific reason to change a package.

---

## Step 4. Create the .env file

In File Manager, inside `flatlandbd`, copy `.env.example` to `.env`, then edit `.env`.
At minimum change these:

```ini
SECRET_KEY=paste-your-first-random-key
DATA_ENCRYPTION_KEY=paste-your-second-random-key

ADMIN_PATH=console-x7
ADMIN_USERNAME=admin
ADMIN_EMAIL=you@example.com
ADMIN_PASSWORD=choose-a-strong-password
ADMIN_PHONE=01XXXXXXXXX

DATABASE_URL=sqlite:///flatland.db

TRUST_PROXY=1
FORCE_HTTPS=1
SESSION_COOKIE_SECURE=1
```

`ADMIN_PATH` is the secret door to your console. With the value above, the console is at
`https://your-domain/console-x7`. Pick your own, keep it boring and unguessable, and do
not link to it from the public site.

Every other setting is explained inside `.env.example`.

---

## Step 5. Turn on the image CDN

Strongly recommended, and free. Follow `CLOUDINARY.md`, which walks through creating the
account and pasting three values into `.env`. Skip it and the site still works, images just
live on your hosting disk and pages are heavier.

After pasting the keys, restart the app and open **Media and CDN** in the console, then
click **Run connection test**. Green means done.

---

## Step 6. Start it

Back on the Setup Python App page, click **Restart**. Open your domain.

Then open `https://your-domain/<your ADMIN_PATH>` and sign in with `ADMIN_USERNAME` and
`ADMIN_PASSWORD`. Change the password from the dashboard afterwards.

---

## Using MySQL instead of SQLite

SQLite is fine for a small site and needs no setup. If you prefer MySQL:

1. cPanel then **MySQL Databases**. Create a database and a user, and add the user to the
   database with all privileges.
2. Add `pymysql` to `requirements.txt` and run **Run Pip Install** again.
3. Set the connection string in `.env`, using your real names:
   ```ini
   DATABASE_URL=mysql+pymysql://cpaneluser_dbuser:password@localhost/cpaneluser_dbname
   ```
4. Restart the app. Tables are created automatically on first boot.

---

## When something is wrong

| What you see | What it means | Fix |
| --- | --- | --- |
| 500 error on every page | Usually a missing package or a bad `.env` line | Open `stderr.log` in the app root, read the last lines |
| "Internal Server Error" right after editing `.env` | A value contains stray quotes or spaces | Values need no quotes: `SECRET_KEY=abc123` |
| Pages load but look unstyled | Static files are not being served | Confirm `frontend/static/css` uploaded, then hard refresh with `Ctrl Shift R` |
| Console URL returns 404 | `ADMIN_PATH` differs from the URL you typed | Check the exact value in `.env`, then restart |
| "File too large" when posting photos | Upload exceeded `MAX_UPLOAD_MB` | Raise it in `.env`, or upload fewer photos at once |
| Images vanish after a redeploy | They were on local disk, not the CDN | Set up Cloudinary, see `CLOUDINARY.md` |
| Login says "too many attempts" | Rate limiting, working as intended | Wait a minute, or set `REDIS_URL` for a shared limiter |
| Cannot read old phone numbers or emails | `DATA_ENCRYPTION_KEY` changed | Restore the original key. There is no other way back |

After **any** change to `.env` or to a `.py` file, click **Restart** in Setup Python App.
Template and CSS edits only need a browser refresh.

---

## Updating later

1. Back up first: download `.env` and, if you use SQLite, the `.db` file from the instance
   folder.
2. Upload and extract the new ZIP over the existing folder.
3. Run **Run Pip Install** if `requirements.txt` changed.
4. Click **Restart**.

Your `.env` and database are not part of the ZIP, so they survive an update.

---

## Quick health check after going live

Open the console then **Health and config**. It checks the database, secret keys, image
storage, mail, cache and rate limiting live on the server, and tells you what to fix in
plain language. Green across the board means you are done.
