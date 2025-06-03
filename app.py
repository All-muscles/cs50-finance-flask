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

    rows = db.execute(
        "SELECT price_cents, shares, symbol FROM purchases WHERE uuid = ?", id
    )

    current_prices = {} # keep track of each share and its price
    total_shares = {} # keep track of how many shares someone owns in total of each stock
    for row in rows:
        symbol = row["symbol"]
        share_count = row["shares"]

        # make sure the symbol has not been looked up yet
        if symbol not in current_prices:
            price = lookup(symbol)["price"] * 100
            current_prices[symbol] = price

        if symbol in total_shares:
            total_shares[symbol] = share_count + total_shares[symbol]
        else:
            total_shares[symbol] = share_count

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
        symbol = request.form.get("symbol")
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
        symbol = results["symbol"] # this is basically redundent i think

        row = db.execute(
            "SELECT balance_cents FROM users WHERE id = ?", session["user_id"]
        )

        user_budget = row[0]["balance_cents"]
        cost = (price * 100) * shares

        if (cost) > user_budget:
            return apology("Low on cash in your account, could not complete purchase")
        else:          
            # update the users cash in their account
            db.execute(
                "UPDATE users SET balance_cents = ? WHERE id = ?", (user_budget - cost), session["user_id"]
            )

            # add their purchase into the purchases table
            db.execute(
                "INSERT INTO purchases (uuid, price_cents, shares, symbol, time) VALUES (?, ?, ?, ?, ?)", session["user_id"], price * 100, shares, symbol, datetime.now()
            )

        return redirect("/")
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
            return apology("Must provide symbol", 403)
        
        quote = lookup(symbol)

        return render_template("quote.html", quote=quote)
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
            return apology("Must provide username", 403)
        
        if not password:
            return apology("Must provide password", 403)
        
        if not confirmation:
            return apology("Must provide password twice", 403)
        
        if confirmation != password:
            return apology("Your password and its confirmation must be the same", 403)
        
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
    return apology("TODO")

if __name__ == "__main__":
    app.debug = True
    app.run()