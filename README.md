# Printing Shop Management System

A working prototype of the Printing Shop Management System designed in
**DCIT 216 Assignment 2** (Student ID 22370827). It is a small website that
runs on your own computer. It is written in **Python** with **Flask**, and it
stores its data in an **SQLite** database file. No database server or internet
hosting is needed.

---

## Quick start on Windows (step by step)

You only do steps 1–4 **once**. After that, use step 6 each time you want to
start the program.

### Step 1: Install Python (one time only)

1. Go to **https://www.python.org/downloads/** and click the yellow
   **Download Python 3.x** button. Any version **3.9 or newer** works.
2. Open the downloaded file.
3. ⚠️ **Important:** on the first screen of the installer, tick the box
   **"Add python.exe to PATH"** at the bottom. Then click **Install Now**.
4. When it says "Setup was successful", click **Close**.

To check that it worked, open the Start menu, type `cmd`, press Enter, and in
the black window type:

```bat
py --version
```

You should see something like `Python 3.12.4`. If you get an error instead,
see [Problems and fixes](#problems-and-fixes) below.

### Step 2: Put the project folder somewhere easy

If you received the project as a **.zip** file, right-click it, choose
**Extract All…**, and extract it to an easy place, for example
`C:\Users\<your name>\Documents\printshop`.

Open the folder. You should see files such as `app.py`, `requirements.txt` and
`schema.sql`, and folders called `static`, `templates` and `tests`.

> If you see just one folder inside, open that folder. You need to be in the
> folder that contains `app.py` directly.

### Step 3: Open Command Prompt *inside* the project folder

1. In File Explorer, open the `printshop` folder (the one with `app.py`).
2. Click in the **address bar** at the top (where the folder path is shown).
3. Delete what is there, type `cmd`, and press **Enter**.

A black Command Prompt window opens, already in the right folder. The line
should end with `...\printshop>`.

> Use **Command Prompt (cmd)**, not PowerShell. All the commands below are
> written for Command Prompt.

### Step 4: Set up the program (one time only)

Type these commands one at a time in the Command Prompt window, pressing
**Enter** after each one and waiting for it to finish.

```bat
py -m venv .venv
```
This creates a private Python environment for the project in a folder called
`.venv`. It takes a few seconds and prints nothing.

```bat
.venv\Scripts\activate
```
This switches that environment on. The line now starts with **`(.venv)`**.

```bat
python -m pip install -r requirements.txt
```
This downloads Flask, the only library the program needs. **It needs an
internet connection** (only this once). Wait until it says
`Successfully installed ...`.

### Step 5: Start the program

```bat
python app.py
```

You should see something like:

```
 * Serving Flask app 'app'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment...
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

The red **WARNING** line is normal and safe to ignore. The database file
`printshop.db` is created automatically the first time.

Leave this window **open**. The program runs only while this window is open.

### Step 6: Open it in your browser

Open Chrome, Edge or Firefox and go to:

**http://127.0.0.1:5000**

Log in with one of these demo accounts:

| Role      | Username    | Password       |
|-----------|-------------|----------------|
| Attendant | `attendant` | `attendant123` |
| Manager   | `manager`   | `manager123`   |

Change these passwords on the **Staff** page (log in as manager) before
using the system for real.

### Stopping the program

Click on the Command Prompt window and press **Ctrl + C**, or just close the
window.

### Starting it again later (every day)

Steps 1–4 are already done, so you only need to:

1. Open the `printshop` folder, type `cmd` in the address bar, and press Enter.
2. Run these two commands:

   ```bat
   .venv\Scripts\activate
   python app.py
   ```

3. Open **http://127.0.0.1:5000** in the browser.

All orders, customers and payments are kept in `printshop.db` and are still
there when you start again.

---

## Using it from phones on the same Wi-Fi (optional)

Customers can check in and track their orders from their phones if the phones
and the computer are on the **same Wi-Fi network**.

1. Find the computer's IP address. In Command Prompt, type `ipconfig` and look
   for **IPv4 Address** under your Wi-Fi adapter, for example `192.168.1.25`.
2. Start the program like this instead of the usual `python app.py`:

   ```bat
   .venv\Scripts\activate
   set HOST=0.0.0.0
   python app.py
   ```

3. If Windows shows a **Windows Defender Firewall** pop-up, tick
   **Private networks** and click **Allow access**.
4. On the phone, open `http://192.168.1.25:5000`, using **your** IP address
   from step 1.

The waiting-area queue screen is at `http://<IP>:5000/display`. You can open
it on a TV or a spare screen.

---

## Problems and fixes

| What you see | What to do |
|---|---|
| `'py' is not recognized...` or `'python' is not recognized...` | Python is not installed, or "Add to PATH" was not ticked. Run the Python installer again, choose **Modify** (or uninstall and reinstall), and make sure **Add python.exe to PATH** is ticked. Then **close and reopen** Command Prompt. |
| Typing `python` opens the **Microsoft Store** | Use `py` instead of `python` for step 4's first command. Or go to *Settings → Apps → Advanced app settings → App execution aliases* and turn **off** the two "python" entries. |
| `...activate.ps1 cannot be loaded because running scripts is disabled` | You are in **PowerShell**, not Command Prompt. Close it and open Command Prompt as shown in step 3 (type `cmd` in the folder's address bar). |
| `No such file or directory: 'requirements.txt'` or `can't open file 'app.py'` | Command Prompt is in the wrong folder. Go back to step 3 and open it from the folder that contains `app.py`. |
| `ModuleNotFoundError: No module named 'flask'` | You forgot to activate the environment. Run `.venv\Scripts\activate` first. The line must start with `(.venv)`. |
| `pip install` fails with a connection or SSL error | Check that the computer is online, then run the command again. |
| Browser says **"This site can't be reached"** | The program is not running. Check that the Command Prompt window is still open and shows `Running on http://127.0.0.1:5000`. |
| `Address already in use` / port 5000 busy | The program is already running in another window, or another program uses port 5000. Close the other window, or start on another port with `set PORT=5050` and then `python app.py`, and open `http://127.0.0.1:5050`. |
| Forgot the manager password | See *Starting over* below. Note that this erases all data. |

---

## Starting over (erase all data)

1. Stop the program (Ctrl + C).
2. Delete the file `printshop.db` from the project folder.
3. Start the program again.

A fresh, empty database is created, with the demo accounts and the default
services and prices.

---

## Running on macOS / Linux

```bash
cd printshop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**. To allow phones on the same Wi-Fi to
connect, use `HOST=0.0.0.0 python app.py`.

---

## What each user can do

**Customer** (no login)
- **Check in**: tap a service, enter a name, and get a queue number and tracking code (sketch screen 1).
- **Track my order**: a live timeline (Received → Being processed → Ready → Completed) that updates by itself (sketch screen 3).
- **Ready notification**: a browser notification and banner when the order is ready for collection (sketch screen 4).
- **Queue board** (`/display`): a waiting-area screen that shows queue numbers only, never names.

**Shop attendant**
- **Today's queue**: a live list with customer, service, payment and status, plus one-click *Start → Mark ready → Complete* buttons (sketch screen 2).
- **New order**: typing a returning customer's phone number fills in their name, the total is worked out as you type, and you can record the payment at the same time.
- **Order page**: edit the order, record full or part payments (Cash / Mobile Money / Card), see the timeline, and see the customer's previous orders.
- **Search**: by name, phone, queue number, tracking code or notes, with status and date filters.
- **Reminders**: orders not updated for 30+ minutes are flagged ⏰, and "Ready but not paid" orders are listed at the top of the queue.
- An order **cannot be completed until it is fully paid**, so sales are not forgotten.

**Manager**
- Everything the attendant can do, plus:
- **Sales dashboard**: money collected, order count and value, open orders, unpaid balances, a 7-day chart, sales by service, payment methods, orders per staff member and the latest payments, for today, the last 7 days, this month or any date range.
- **Services and prices**: add services, change prices (existing orders keep their old price), and hide services.
- **Staff accounts**: add attendants or managers, reset passwords, and disable accounts.
- Cancel orders that have no payments recorded.

## How the prototype meets the assignment

| Assignment requirement (Part 2, Q3) | Where it is implemented |
|---|---|
| FR1 Register customer orders | *New order* page, plus customer self check-in |
| FR2 Record payments | *Order page → Payments*, or "Customer is paying now" on *New order* |
| FR3 Update order status | Queue buttons and order page (Waiting → In Progress → Ready → Completed) |
| FR4 Store customer and order information | SQLite tables `customers`, `orders`, `payments` (`schema.sql`) |
| FR5 Manager views sales information | *Dashboard* |
| FR6 Search previous orders | *Orders & search*, and "previous orders" on each order page |
| Effectiveness / avoid forgotten sales | Orders can't be completed while unpaid, plus the "Ready but not paid" alert |
| Efficiency (few steps) | One-click status buttons, phone lookup, pay-on-save |
| Learnability | Large labelled buttons, icons, plain-language messages |
| Situational awareness (Part 1) | Live queue with status pills, queue board, customer tracking page |
| Persuasive technology & trust (Part 2, Q2) | Stale-order reminders, confirmation message after every save, role-based access |
| Personalised access | Attendant and manager logins see different menus |
| Visceral / behavioural / reflective design | Clean layout, immediate feedback, dashboard for the manager's confidence |
| Technical constraints | Runs on any computer or phone browser, works on a local network, login and access control, responsive layout |
| Ideation sketch (Part 4, Q3) | Check-in, queue display, order tracking and notification screens |

---

## For developers continuing the project

### Project structure

```
printshop/
├── app.py              # all routes and business logic (start here)
├── schema.sql          # database tables
├── requirements.txt    # Python libraries (just Flask)
├── static/style.css    # styling (mobile-friendly)
├── templates/          # HTML pages (Jinja2); base.html is the shared layout
└── tests/test_app.py   # end-to-end test of every main flow
```

Files created automatically when the app runs (do not share or commit them):

- `printshop.db`: the database with all shop data.
- `.secret_key`: a random key used to secure logins.
- `.venv\`: the Python environment from step 4.

### Running the tests

With the environment activated:

```bat
python tests\test_app.py
```

The tests use a temporary database and do not touch `printshop.db`.

### Settings

These are set with `set NAME=value` in Command Prompt before running
`python app.py` (or `NAME=value python app.py` on macOS/Linux):

| Setting | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | Use `0.0.0.0` to allow other devices on the network |
| `PORT` | `5000` | Port the website runs on |
| `PRINTSHOP_DB` | `printshop.db` in the project folder | Path to the database file |
| `PRINTSHOP_SECRET` | contents of `.secret_key` | Secret key for login sessions |

The currency symbol (GH₵) is set in `CURRENCY` at the top of `app.py`.

### Notes and possible extensions

- The "ready" notification uses the browser. Sending an SMS when an order is ready would be a natural next step, through a local SMS gateway such as Hubtel or mNotify.
- `python app.py` runs Flask's development server in debug mode, which is fine for a demo or a single shop computer. For real use, run it with a production server such as `waitress` (`pip install waitress`, then `waitress-serve --port=5000 app:app`).
