import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # stocks they own, number of each stock's shares, current price of each stock, total value of each holding, current cash balance, total networth

    id = session["user_id"]

    rows_purchases = db.execute(
        "SELECT shares, symbol FROM purchases WHERE uuid = ?", id
    )

    rows_sells = db.execute(
        "SELECT shares, symbol FROM sells WHERE uuid = ?", id
    )

    current_prices = {} # keep track of each share and its price
    total_shares = {} # keep track of how many shares someone owns in total of each stock
    for purchase in rows_purchases:
        symbol = purchase["symbol"]
        share_count = purchase["shares"]

        # make sure the symbol has not been looked up yet
        if symbol not in current_prices:
            price = lookup(symbol)["price"] * 100
            current_prices[symbol] = price

        if symbol in total_shares:
            total_shares[symbol] = share_count + total_shares[symbol]
        else:
            total_shares[symbol] = share_count

    for sell in rows_sells:
        symbol = sell["symbol"]
        share_count = sell["shares"]

        if symbol in total_shares:
            total_shares[symbol] = total_shares[symbol] - share_count
        else:
            pass

    # make a list of dict with each dict containing symbol, shares, price and a total
    rows = []
    total = 0
    for symbol, shares in total_shares.items():
        row = {}
        row["symbol"] = symbol
        row["shares"] = shares
        row["price"] = current_prices[symbol] / 100
        row["total"] = round((shares * current_prices[symbol]) / 100, 2)
        total += shares * current_prices[symbol]
        rows.append(row)

    cash_cents = db.execute("SELECT balance_cents FROM users WHERE id = ?", id)[0]["balance_cents"]
    total += cash_cents

    return render_template("index.html", rows=rows, cash=cash_cents / 100, total=total / 100)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        if not symbol:
            return apology("Must provide symbol")
        
        results = lookup(symbol)
        if not results:
            return apology("Symbol must exist")
        
        shares = request.form.get("shares")
        if not shares:
            return apology("Must provide shares")
        
        if not shares.isdigit() or int(shares) == 0:
            return apology("The share value must be a positive whole number")
        
        shares = int(shares)

        name = results["name"]
        price = results["price"]

        row = db.execute("SELECT balance_cents FROM users WHERE id = ?", session["user_id"])

        user_budget = row[0]["balance_cents"]
        cost = (price * 100) * shares

        if (cost) > user_budget:
            return apology("Low on cash in your account, could not complete purchase")
        else:          
            # update the users cash in their account
            db.execute("UPDATE users SET balance_cents = ? WHERE id = ?", (user_budget - cost), session["user_id"])

            # add their purchase into the purchases table
            db.execute("INSERT INTO purchases (uuid, price_cents, shares, symbol, time) VALUES (?, ?, ?, ?, ?)", session["user_id"], price * 100, shares, symbol, datetime.now())

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    uuid = session["user_id"]
    purchases_rows = db.execute("SELECT price_cents, shares, symbol, time FROM purchases WHERE uuid = ?", uuid)
    sells_rows = db.execute("SELECT price_cents, shares, symbol, time FROM purchases WHERE uuid = ?", uuid)

    rows = []
    for row in purchases_rows:
        r = {}
        r["price"] = row["price_cents"] / 100
        r["shares"] = row["shares"]
        r["symbol"] = row["symbol"]
        r["time"] = row["time"]
        r["status"] = "purchased"
        rows.append(r)
    for row in sells_rows:
        r = {}
        r["price"] = row["price_cents"] / 100
        r["shares"] = row["shares"]
        r["symbol"] = row["symbol"]
        r["time"] = row["time"]
        r["status"] = "sold"
        rows.append(r)

    return render_template("history.html", rows=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Must provide symbol")
        
        r = lookup(symbol)

        if r is None:
            return apology("Your symbol does not exist in the DB")

        r["price"] = usd(r["price"])

        return render_template("quote.html", quote=r)
    else:
        return render_template("quote.html")
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username:
            return apology("Must provide username")
        
        if not password:
            return apology("Must provide password")
        
        if not confirmation:
            return apology("Must provide password twice")
        
        if confirmation != password:
            return apology("Your password and its confirmation must be the same")
        
        # make sure the username is not in the database
        rows = db.execute("SELECT username FROM users")
        usernames = []
        for row in rows:
            usernames.append(row["username"])

        if username in usernames:
            return apology("The username is already in the database")

        try:
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password)
            )

            return redirect("/")
        except ValueError:
            return apology("Username already in the database", 400)

    else:
        return render_template("register.html")
    

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        uuid = session["user_id"]
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        current_price = int(lookup(symbol)["price"] * 100)

        # check if shares is a positive whole int
        if not shares.isdigit() or int(shares) == 0:
            return apology("Shares value must be a positive whole integer")

        shares = int(shares)

        # check if the user has such shares and symbols as they claim to have
        # check each of the purchases and sells table and then verify if they have that much share of the symbol they have entered
        purchased_shares = db.execute("SELECT SUM(shares) FROM purchases WHERE uuid = ? AND symbol = ?", uuid, symbol)[0]["SUM(shares)"]
        sold_shares = db.execute("SELECT SUM(shares) from sells WHERE uuid = ? AND symbol = ?", uuid, symbol)[0]["SUM(shares)"]
        if sold_shares is None:
            sold_shares = 0
        if shares >= (purchased_shares - sold_shares):
            return apology(f"You do not have enough shares to sell of the symbol {symbol}")
        else:
            db.execute("INSERT INTO sells (uuid, price_cents, shares, symbol, time) VALUES (?, ?, ?, ?, ?)", uuid, current_price, shares, symbol, datetime.now())

            # update users cash balance
            user_balance = int(db.execute("SELECT balance_cents FROM users WHERE id = ?", uuid)[0]["balance_cents"])
            
            db.execute("UPDATE users SET balance_cents = ? WHERE id = ?", user_balance + (current_price * shares), uuid)

            return redirect("/")

    else:
        id = session["user_id"]

        rows = db.execute("SELECT symbol FROM purchases WHERE uuid = ?", id)

        symbols = []
        for row in rows:
            symbol = row["symbol"]
            if symbol in symbols:
                pass
            else:
                symbols.append(symbol)
        # import pdb; pdb.set_trace()
        return render_template("sell.html", symbols=symbols)
    
@app.route("/topup", methods=["get", "post"])
@login_required
def topup():
    """Top up users cash score"""
    if request.method == "post":
        amount = request.form.get("amount")
        uuid = session["user_id"]

        try:
            amount = float(amount)
        except:
            return apology("Please try to enter a number like 1.22")
        
        # check if the floating points are two
        decimals = len(str(amount).split(".")[1])
        if decimals > 2:
            return apology("Please try to enter a number like 1.22")

        user_balance = db.execute("SELECT balance_cents FROM users WHERE uuid = ?", uuid)[0]["balance_cents"]

        db.execute("UPDATE users SET balance_cents = ? WHERE uuid = ?", user_balance + amount * 100, uuid)

        return redirect("/")
    else:
        return render_template("topup.html")