import os
import requests
import hashlib
import hmac
import secrets
import smtplib
import time
from email.message import EmailMessage
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps
from decimal import Decimal, ROUND_HALF_UP
from expiry_decision import get_expiry_decision_report
from phone_validation import register_phone_validation

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from database import (
    get_connection,
    get_inventory_summary,
    get_sales_summary,
    load_products_from_database,
    load_sales_from_database,
    add_product_to_database,
    get_or_create_customer,
    update_product_stock,
    record_sale,
    get_top_selling_products,
    get_sales_chart_data,
    get_category_stock_data,
    get_expiry_alerts
)

from forecast import get_restock_recommendation
from scenario import simulate_scenario


# Resolve project paths from this app.py file, not from the terminal's
# current working directory. This ensures .env loads from C:\SmartRetailInventory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_FILE, override=True)


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates")
)

# Put FLASK_SECRET_KEY in .env for a stable key across restarts.
# The fallback is suitable for local testing, but it changes each restart.
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_urlsafe(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

register_phone_validation(app)


def round_money(value):
    """Round currency values to two decimal places using half-up rounding."""
    return float(
        Decimal(str(value)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def calculate_gst(taxable_amount, gst_rate, supply_type="intra"):
    """Calculate GST and its CGST/SGST or IGST components.

    supply_type='intra' splits GST into CGST and SGST.
    supply_type='inter' applies the full GST amount as IGST.
    The rate must be entered based on the product's applicable GST rate.
    """
    taxable = Decimal(str(taxable_amount)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    rate = Decimal(str(gst_rate))

    if taxable < 0:
        raise ValueError("Taxable amount cannot be negative.")
    if rate < 0 or rate > 40:
        raise ValueError("GST rate must be between 0 and 40 percent.")

    supply_type = str(supply_type).strip().lower()
    if supply_type not in ("intra", "inter"):
        raise ValueError("Supply type must be 'intra' or 'inter'.")

    gst_amount = (taxable * rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    cgst_amount = Decimal("0.00")
    sgst_amount = Decimal("0.00")
    igst_amount = Decimal("0.00")

    if supply_type == "intra":
        cgst_amount = (gst_amount / Decimal("2")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        # Ensure CGST + SGST equals total GST exactly to the paisa.
        sgst_amount = gst_amount - cgst_amount
    else:
        igst_amount = gst_amount

    return {
        "taxable_amount": float(taxable),
        "gst_rate": float(rate),
        "gst_amount": float(gst_amount),
        "cgst_amount": float(cgst_amount),
        "sgst_amount": float(sgst_amount),
        "igst_amount": float(igst_amount),
        "total_amount": float(taxable + gst_amount),
        "supply_type": supply_type,
    }


# =========================================================
# LOGIN
# =========================================================

USERNAME = "admin"
PASSWORD = "admin123"

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "").strip()
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()
ALLOWED_RECAPTCHA_HOSTS = {"localhost", "127.0.0.1"}

# Gmail OTP settings. Keep the actual credentials in .env, never in this file.
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "").strip()
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip()
OTP_LIFETIME_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_MAX_RESENDS = 3
OTP_RESEND_COOLDOWN_SECONDS = 30


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "logged_in" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def verify_recaptcha(response_token, remote_ip=None):
    """Verify a Google reCAPTCHA v2 response on the server."""
    if not RECAPTCHA_SITE_KEY or not RECAPTCHA_SECRET_KEY:
        app.logger.error("reCAPTCHA keys are not configured in .env")
        return False, "CAPTCHA is not configured. Check the project's .env file."

    if not response_token:
        return False, "Please complete the CAPTCHA."

    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": response_token,
                "remoteip": remote_ip or "",
            },
            timeout=8,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        app.logger.warning("reCAPTCHA verification request failed: %s", exc)
        return False, "CAPTCHA verification is temporarily unavailable. Try again."

    if result.get("success") is not True:
        return False, "CAPTCHA verification failed. Please try again."

    hostname = str(result.get("hostname", "")).lower()
    if hostname not in ALLOWED_RECAPTCHA_HOSTS:
        app.logger.warning("Unexpected reCAPTCHA hostname: %s", hostname)
        return False, "CAPTCHA domain mismatch. Open the app using http://localhost:5000."

    return True, ""


def otp_digest(otp_code):
    """Return a keyed digest for the six-digit one-time code."""
    return hmac.new(
        str(app.secret_key).encode("utf-8"),
        otp_code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def send_admin_otp(otp_code):
    """Email a short-lived admin login code using Gmail SMTP."""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or not ADMIN_EMAIL:
        raise RuntimeError(
            "Email OTP is not configured. Set SMTP_EMAIL, SMTP_APP_PASSWORD, "
            "and ADMIN_EMAIL in the .env file."
        )

    message = EmailMessage()
    message["Subject"] = "Smart Retail Inventory - Admin Login Verification"
    message["From"] = SMTP_EMAIL
    message["To"] = ADMIN_EMAIL
    message.set_content(
        "Your Smart Retail Inventory admin login verification code is: "
        f"{otp_code}\n\n"
        "This code expires in 5 minutes. If you did not request this code, "
        "you can ignore this email."
    )

    # Use a Google App Password, not the regular Gmail password.
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(message)


def clear_pending_otp():
    """Remove temporary verification values from the Flask session."""
    for key in (
        "pending_username",
        "pending_otp_hash",
        "pending_otp_expiry",
        "otp_attempts",
        "otp_last_sent_at",
        "otp_resends",
    ):
        session.pop(key, None)


@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    # A logged-in administrator visiting /login should go to the dashboard.
    if request.method == "GET" and session.get("logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        captcha_token = request.form.get("g-recaptcha-response", "").strip()

        captcha_ok, captcha_message = verify_recaptcha(
            captcha_token,
            request.remote_addr,
        )

        if not captcha_ok:
            message = captcha_message
        elif username != USERNAME or password != PASSWORD:
            message = "Invalid username or password."
        else:
            otp_code = f"{secrets.randbelow(1_000_000):06d}"
            try:
                send_admin_otp(otp_code)
            except Exception:
                app.logger.exception("Could not send admin login OTP")
                message = (
                    "Could not send the verification email. Check the Gmail settings "
                    "in .env and try again."
                )
            else:
                session.clear()
                session["pending_username"] = username
                session["pending_otp_hash"] = otp_digest(otp_code)
                session["pending_otp_expiry"] = time.time() + OTP_LIFETIME_SECONDS
                session["otp_attempts"] = 0
                session["otp_last_sent_at"] = time.time()
                session["otp_resends"] = 0
                return redirect(url_for("verify_otp"))

    return render_template(
        "login.html",
        message=message,
        recaptcha_site_key=RECAPTCHA_SITE_KEY,
    )


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if not session.get("pending_username") or not session.get("pending_otp_hash"):
        return redirect(url_for("login"))

    message = ""
    remaining_seconds = max(
        0, int(session.get("pending_otp_expiry", 0) - time.time())
    )

    if remaining_seconds <= 0:
        clear_pending_otp()
        return render_template(
            "verify_otp.html",
            message="Your code has expired. Return to login and try again.",
            can_verify=False,
            can_resend=False,
            remaining_seconds=0,
        )

    if request.method == "POST":
        otp_input = request.form.get("otp", "").strip()
        attempts = int(session.get("otp_attempts", 0))

        if attempts >= OTP_MAX_ATTEMPTS:
            clear_pending_otp()
            return redirect(url_for("login"))

        if not (otp_input.isdigit() and len(otp_input) == 6):
            session["otp_attempts"] = attempts + 1
            message = "Enter the 6-digit code from your email."
        else:
            supplied_hash = otp_digest(otp_input)
            expected_hash = str(session.get("pending_otp_hash", ""))

            if hmac.compare_digest(supplied_hash, expected_hash):
                username = session.get("pending_username", USERNAME)
                session.clear()
                session["logged_in"] = True
                session["username"] = username
                return redirect(url_for("dashboard"))

            session["otp_attempts"] = attempts + 1
            left = max(0, OTP_MAX_ATTEMPTS - int(session["otp_attempts"]))
            message = f"Incorrect code. Attempts remaining: {left}."

            if left <= 0:
                clear_pending_otp()
                message = "Too many incorrect attempts. Return to login and try again."

    remaining_seconds = max(
        0, int(session.get("pending_otp_expiry", 0) - time.time())
    )
    can_verify = bool(session.get("pending_otp_hash")) and remaining_seconds > 0

    return render_template(
        "verify_otp.html",
        message=message,
        can_verify=can_verify,
        can_resend=can_verify,
        remaining_seconds=remaining_seconds,
    )


@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    if not session.get("pending_username") or not session.get("pending_otp_hash"):
        return redirect(url_for("login"))

    now = time.time()
    last_sent = float(session.get("otp_last_sent_at", 0))
    resends = int(session.get("otp_resends", 0))

    if resends >= OTP_MAX_RESENDS:
        return render_template(
            "verify_otp.html",
            message="Maximum resend limit reached. Return to login and try again.",
            can_verify=True,
            can_resend=False,
            remaining_seconds=max(0, int(session.get("pending_otp_expiry", 0) - now)),
        )

    if now - last_sent < OTP_RESEND_COOLDOWN_SECONDS:
        wait_for = int(OTP_RESEND_COOLDOWN_SECONDS - (now - last_sent)) + 1
        return render_template(
            "verify_otp.html",
            message=f"Please wait {wait_for} seconds before requesting another code.",
            can_verify=True,
            can_resend=True,
            remaining_seconds=max(0, int(session.get("pending_otp_expiry", 0) - now)),
        )

    otp_code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        send_admin_otp(otp_code)
    except Exception:
        app.logger.exception("Could not resend admin login OTP")
        return render_template(
            "verify_otp.html",
            message="Could not resend email. Check Gmail settings and try again later.",
            can_verify=True,
            can_resend=True,
            remaining_seconds=max(0, int(session.get("pending_otp_expiry", 0) - now)),
        )

    session["pending_otp_hash"] = otp_digest(otp_code)
    session["pending_otp_expiry"] = now + OTP_LIFETIME_SECONDS
    session["otp_attempts"] = 0
    session["otp_last_sent_at"] = now
    session["otp_resends"] = resends + 1

    return render_template(
        "verify_otp.html",
        message="A new verification code has been sent to the admin email.",
        can_verify=True,
        can_resend=True,
        remaining_seconds=OTP_LIFETIME_SECONDS,
    )

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
@login_required
def dashboard():

    inventory_summary = get_inventory_summary()
    sales_summary = get_sales_summary()

    products = load_products_from_database()
    sales = load_sales_from_database()

    top_products = get_top_selling_products()
    sales_chart = get_sales_chart_data()
    category_stock = get_category_stock_data()

    expiry_alerts = get_expiry_alerts(days=30)

    forecast_data = []

    for product in products:

        result = get_restock_recommendation(
            product["name"],
            days=7
        )

        if result.get("status") == "success":

            forecast_data.append({
                "name": product["name"],
                "current_stock": result["current_stock"],
                "predicted_demand": result["predicted_demand"],
                "recommended_stock": result["recommended_stock"],
                "additional_stock": result["additional_stock"],
                "status": result["stock_status"]
            })

        else:

            forecast_data.append({
                "name": product["name"],
                "current_stock": product["stock"],
                "predicted_demand": None,
                "recommended_stock": None,
                "additional_stock": None,
                "status": "Insufficient history"
            })

    return render_template(
        "dashboard.html",
        inventory=inventory_summary,
        sales_summary=sales_summary,
        products=products,
        sales=sales,
        top_products=top_products,
        sales_chart=sales_chart,
        category_stock=category_stock,
        forecast_data=forecast_data,
        expiry_alerts=expiry_alerts
    )


# =========================================================
# PRODUCTS
# =========================================================

@app.route("/products")
@login_required
def products():

    products = load_products_from_database()

    return render_template(
        "products.html",
        products=products
    )


# =========================================================
# ADD PRODUCT
# =========================================================

@app.route("/add-product", methods=["GET", "POST"])
@login_required
def add_product_page():

    message = ""

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        supplier = request.form.get("supplier", "").strip()

        supplier_contact = request.form.get(
            "supplier_contact", ""
        ).strip()

        expiry_date = request.form.get(
            "expiry_date", ""
        ).strip()

        try:

            price = float(request.form["price"])
            stock = int(request.form["stock"])

            if not name or not category:
                message = "Product name and category are required."

            elif price < 0 or stock < 0:
                message = "Price and stock cannot be negative."

            else:

                parsed_expiry = None

                if expiry_date:

                    parsed_expiry = datetime.strptime(
                        expiry_date,
                        "%Y-%m-%d"
                    ).date()

                connection = get_connection()
                cursor = connection.cursor()

                cursor.execute(
                    """
                    SELECT product_id
                    FROM products
                    WHERE LOWER(name) = LOWER(%s)
                    """,
                    (name,)
                )

                existing = cursor.fetchone()

                cursor.close()
                connection.close()

                if existing:

                    message = "A product with this name already exists."

                else:

                    add_product_to_database(
                        name,
                        category,
                        supplier,
                        supplier_contact,
                        price,
                        stock,
                        parsed_expiry
                    )

                    message = "Product added successfully."

        except ValueError:

            message = "Enter a valid price, stock quantity and expiry date."

        except Exception as error:

            message = f"Could not add product: {error}"

    return render_template(
        "add_product.html",
        message=message
    )


# =========================================================
# EDIT PRODUCT
# =========================================================

@app.route(
    "/edit-product/<int:product_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_product_page(product_id):

    message = ""
    form_data = {}

    # -----------------------------------------------------
    # HANDLE FORM SUBMISSION
    # -----------------------------------------------------

    if request.method == "POST":

        form_data = request.form

        name = request.form.get(
            "name", ""
        ).strip()

        category = request.form.get(
            "category", ""
        ).strip()

        supplier = request.form.get(
            "supplier", ""
        ).strip()

        supplier_contact = request.form.get(
            "supplier_contact", ""
        ).strip()

        expiry_value = request.form.get(
            "expiry_date", ""
        ).strip()

        try:

            price = float(request.form["price"])
            stock = int(request.form["stock"])

            if not name or not category:

                message = (
                    "Product name and category are required."
                )

            elif price < 0 or stock < 0:

                message = (
                    "Price and stock cannot be negative."
                )

            else:

                parsed_expiry = None

                if expiry_value:

                    parsed_expiry = datetime.strptime(
                        expiry_value,
                        "%Y-%m-%d"
                    ).date()

                connection = get_connection()
                cursor = connection.cursor()

                # Check for another product with the same name.
                cursor.execute(
                    """
                    SELECT product_id
                    FROM products
                    WHERE LOWER(name) = LOWER(%s)
                      AND product_id <> %s
                    """,
                    (name, product_id)
                )

                duplicate = cursor.fetchone()

                if duplicate:

                    message = (
                        "Another product already uses this name."
                    )

                else:

                    cursor.execute(
                        """
                        UPDATE products
                        SET
                            name = %s,
                            category = %s,
                            supplier = %s,
                            supplier_contact = %s,
                            price = %s,
                            stock = %s,
                            expiry_date = %s
                        WHERE product_id = %s
                        """,
                        (
                            name,
                            category,
                            supplier,
                            supplier_contact,
                            price,
                            stock,
                            parsed_expiry,
                            product_id
                        )
                    )

                    connection.commit()

                    message = (
                        "Product updated successfully."
                    )

                    # Clear submitted values after a successful save.
                    form_data = {}

                cursor.close()
                connection.close()

        except ValueError:

            message = (
                "Enter a valid price, stock quantity and expiry date."
            )

        except Exception as error:

            message = f"Could not update product: {error}"

    # -----------------------------------------------------
    # LOAD THE CURRENT PRODUCT
    # -----------------------------------------------------

    connection = get_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            product_id,
            name,
            category,
            supplier,
            supplier_contact,
            price,
            stock,
            expiry_date,
            DATEDIFF(expiry_date, CURDATE()) AS days_to_expiry
        FROM products
        WHERE product_id = %s
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    connection.close()

    if product is None:

        return "Product not found.", 404

    if product["expiry_date"]:

        expiry_value = product["expiry_date"].strftime(
            "%Y-%m-%d"
        )

    else:

        expiry_value = ""

    return render_template(
        "edit_product.html",
        product=product,
        message=message,
        values=form_data,
        expiry_value=expiry_value
    )


# =========================================================
# SELL PRODUCT
# =========================================================

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell_page():
    products = load_products_from_database()
    message = ""
    invoice = None

    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id", ""))
            customer_name = request.form.get("customer_name", "").strip()
            customer_phone = request.form.get("customer_phone", "").strip()
            quantity = int(request.form.get("quantity", ""))
            discount_percent = float(request.form.get("discount_percent", "0"))
            gst_rate = float(request.form.get("gst_rate", "0"))
            supply_type = request.form.get("supply_type", "intra").strip().lower()

            # Validate the form before reading or changing inventory.
            if not customer_name:
                message = "Customer name is required."
            elif quantity <= 0:
                message = "Quantity must be greater than zero."
            elif not 0 <= discount_percent <= 100:
                message = "Discount must be between 0 and 100."
            elif not 0 <= gst_rate <= 40:
                message = "GST rate must be between 0 and 40 percent."
            elif supply_type not in ("intra", "inter"):
                message = "Please select a valid supply type."
            else:
                connection = None
                cursor = None
                try:
                    connection = get_connection()
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(
                        "SELECT * FROM products WHERE product_id = %s",
                        (product_id,)
                    )
                    product = cursor.fetchone()
                finally:
                    if cursor is not None:
                        cursor.close()
                    if connection is not None:
                        connection.close()

                if product is None:
                    message = "Product not found."
                elif (
                    product.get("expiry_date") is not None
                    and datetime.now().date() > product["expiry_date"]
                ):
                    message = "Sale blocked: this product has expired."
                elif quantity > product["stock"]:
                    message = (
                        "Not enough stock. "
                        f"Available stock: {product['stock']}."
                    )
                else:
                    # Calculate subtotal and discount before GST.
                    price = round_money(product["price"])
                    subtotal = round_money(quantity * price)
                    discount_amount = round_money(
                        subtotal * discount_percent / 100
                    )
                    taxable_amount = round_money(subtotal - discount_amount)

                    # GST rate is supplied by the user for this product.
                    # Confirm the correct rate/classification before real use.
                    gst_details = calculate_gst(
                        taxable_amount=taxable_amount,
                        gst_rate=gst_rate,
                        supply_type=supply_type
                    )
                    gst_amount = round_money(gst_details["gst_amount"])
                    cgst_amount = round_money(gst_details["cgst_amount"])
                    sgst_amount = round_money(gst_details["sgst_amount"])
                    igst_amount = round_money(gst_details["igst_amount"])
                    final_amount = round_money(gst_details["total_amount"])

                    remaining_stock = product["stock"] - quantity
                    customer_id = get_or_create_customer(
                        customer_name,
                        customer_phone
                    )

                    connection = None
                    cursor = None
                    try:
                        connection = get_connection()
                        cursor = connection.cursor()
                        cursor.execute("SELECT COUNT(*) FROM sales")
                        sale_count = cursor.fetchone()[0]
                    finally:
                        if cursor is not None:
                            cursor.close()
                        if connection is not None:
                            connection.close()

                    invoice_number = f"INV{sale_count + 1:04}"

                    # Existing database schema stores the final (tax-inclusive)
                    # amount in sales.total. Tax components are shown in invoice.
                    update_product_stock(product_id, remaining_stock)
                    record_sale(
                        invoice_number,
                        product_id,
                        customer_id,
                        quantity,
                        price,
                        subtotal,
                        discount_percent,
                        discount_amount,
                        final_amount
                    )

                    sale_date = datetime.now().strftime("%d-%m-%Y %H:%M")
                    expiry_display = product.get("expiry_date") or "N/A"

                    if supply_type == "intra":
                        supply_label = "Intra-state (CGST + SGST)"
                        tax_lines = (
                            f"CGST ({gst_rate / 2:.2f}%)            : ₹{cgst_amount:.2f}\n"
                            f"SGST ({gst_rate / 2:.2f}%)            : ₹{sgst_amount:.2f}\n"
                        )
                    else:
                        supply_label = "Inter-state (IGST)"
                        tax_lines = (
                            f"IGST ({gst_rate:.2f}%)            : ₹{igst_amount:.2f}\n"
                        )

                    invoice_text = f"""
========================================
        SMART RETAIL STORE
           SALES INVOICE
========================================

Invoice No : {invoice_number}
Date       : {sale_date}

Customer Name  : {customer_name}
Customer Phone : {customer_phone}

----------------------------------------
PRODUCT DETAILS
----------------------------------------

Product ID : {product['product_id']}
Product    : {product['name']}
Category   : {product['category']}
Expiry Date: {expiry_display}

Quantity   : {quantity}
Unit Price : ₹{price:.2f}

----------------------------------------
BILL BREAKDOWN
----------------------------------------

Subtotal                  : ₹{subtotal:.2f}
Discount ({discount_percent:.2f}%)  : ₹{discount_amount:.2f}
Taxable Amount             : ₹{taxable_amount:.2f}
GST Rate                   : {gst_rate:.2f}%
Supply Type                : {supply_label}
{tax_lines}Total GST                  : ₹{gst_amount:.2f}
----------------------------------------
FINAL AMOUNT               : ₹{final_amount:.2f}
----------------------------------------

Remaining Stock            : {remaining_stock}

========================================
       THANK YOU! VISIT AGAIN
========================================
"""

                    invoice_folder = "data/invoices"
                    os.makedirs(invoice_folder, exist_ok=True)
                    invoice_file = os.path.join(invoice_folder, f"{invoice_number}.txt")

                    with open(invoice_file, "w", encoding="utf-8") as file:
                        file.write(invoice_text)

                    message = "Sale completed successfully."
                    invoice = invoice_text
                    products = load_products_from_database()

        except ValueError:
            message = "Please enter valid values for quantity, discount and GST."
        except Exception as error:
            app.logger.exception("Sale failed")
            message = f"Sale failed: {error}"

    return render_template(
        "sell.html",
        products=products,
        message=message,
        invoice=invoice
    )


# =========================================================
# SALES HISTORY
# =========================================================

@app.route("/sales")
@login_required
def sales():

    sales_data = load_sales_from_database()

    return render_template(
        "sales.html",
        sales=sales_data
    )


# =========================================================
# CUSTOMERS
# =========================================================

@app.route("/customers")
@login_required
def customers():

    connection = get_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            c.customer_id,
            c.name,
            c.phone,
            COUNT(s.sale_id) AS total_orders,
            COALESCE(SUM(s.total), 0) AS total_spent
        FROM customers c
        LEFT JOIN sales s
            ON c.customer_id = s.customer_id
        GROUP BY
            c.customer_id,
            c.name,
            c.phone
        ORDER BY c.customer_id DESC
    """

    cursor.execute(query)

    customer_data = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "customers.html",
        customers=customer_data
    )


# =========================================================
# INVOICE HISTORY
# =========================================================

@app.route("/invoices")
@login_required
def invoices():

    invoice_folder = "data/invoices"

    os.makedirs(
        invoice_folder,
        exist_ok=True
    )

    invoice_files = sorted(
        [
            filename
            for filename in os.listdir(invoice_folder)
            if filename.endswith(".txt")
        ],
        reverse=True
    )

    return render_template(
        "invoices.html",
        invoices=invoice_files
    )


# =========================================================
# VIEW INVOICE
# =========================================================

@app.route("/invoice/<filename>")
@login_required
def view_invoice(filename):

    filename = os.path.basename(filename)

    invoice_path = os.path.join(
        "data/invoices",
        filename
    )

    if not os.path.isfile(invoice_path):

        return "Invoice not found.", 404

    with open(
        invoice_path,
        "r",
        encoding="utf-8"
    ) as file:

        invoice_text = file.read()

    return render_template(
        "invoice_view.html",
        invoice=invoice_text,
        filename=filename
    )


# =========================================================
# DEMAND FORECAST
# =========================================================

@app.route("/forecast", methods=["GET", "POST"])
@login_required
def forecast_page():

    products = load_products_from_database()

    result = None

    if request.method == "POST":

        product_name = request.form["product_name"]

        result = get_restock_recommendation(
            product_name,
            days=7
        )

    return render_template(
        "forecast.html",
        products=products,
        result=result
    )


# =========================================================
# DECISION SIMULATOR
# =========================================================

@app.route("/simulator", methods=["GET", "POST"])
@login_required
def simulator():

    products = load_products_from_database()

    result = None

    if request.method == "POST":

        try:

            product_name = request.form["product_name"]

            demand_increase = float(
                request.form["demand_increase"]
            )

            extra_supplier_delay = int(
                request.form["extra_supplier_delay"]
            )

            if not 0 <= demand_increase <= 500:

                result = {
                    "status": "error",
                    "message": "Demand increase must be between 0 and 500%."
                }

            elif not 0 <= extra_supplier_delay <= 30:

                result = {
                    "status": "error",
                    "message": "Extra supplier delay must be between 0 and 30 days."
                }

            else:

                result = simulate_scenario(
                    product_name,
                    demand_increase,
                    extra_supplier_delay
                )

        except ValueError:

            result = {
                "status": "error",
                "message": "Please enter valid scenario values."
            }

    return render_template(
        "simulator.html",
        products=products,
        result=result
    )


# =========================================================
# RUN FLASK
# =========================================================
# =========================================================
# EXPIRY-AWARE SMART REORDER DECISION ENGINE
# =========================================================
@app.route("/expiry-decisions")
@login_required
def expiry_decisions():

    try:
        report = get_expiry_decision_report()

        return render_template(
            "expiry_decisions.html",
            decisions=report["decisions"],
            summary=report["summary"],
            lookback_days=report["lookback_days"],
            near_expiry_days=report["near_expiry_days"],
            error=None
        )

    except Exception:
        app.logger.exception(
            "Expiry-aware decision report failed"
        )

        return render_template(
            "expiry_decisions.html",
            decisions=[],
            summary={},
            lookback_days=90,
            near_expiry_days=30,
            error=(
                "Could not load expiry-aware decisions. "
                "Check the MySQL connection and confirm "
                "that the required database columns exist."
            )
        ), 500

if __name__ == "__main__":
    app.run(debug=True)
