import re
from flask import request


# Phone number must contain exactly 10 digits.
PHONE_PATTERN = re.compile(r"^[0-9]{10}$")

# Allows names such as:
# Darshan Jain
# A. K. Jain
# Mary-Jane
# O'Neil
#
# Disallows numbers, underscores, @ and other symbols.
NAME_PATTERN = re.compile(
    r"^[^\W\d_]+(?:[ .'-][^\W\d_]+)*\.?$",
    re.UNICODE
)

PHONE_FIELD_MARKERS = ("phone", "mobile", "contact")


def is_valid_customer_name(name):
    """Check whether a customer name contains valid name characters."""

    if not isinstance(name, str):
        return False

    name = " ".join(name.strip().split())

    # Minimum 2 characters, maximum 80 characters.
    if len(name) < 2 or len(name) > 80:
        return False

    # A name must contain at least two alphabetic characters.
    if sum(character.isalpha() for character in name) < 2:
        return False

    # Only letters, spaces, periods, apostrophes and hyphens.
    if not all(
        character.isalpha() or character in " .'-"
        for character in name
    ):
        return False

    return NAME_PATTERN.fullmatch(name) is not None


def validation_error(message):
    """Display a simple validation error with a Back button."""

    page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Input Validation</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f3f4f6;
                padding: 40px 15px;
                text-align: center;
            }}
            .box {{
                max-width: 500px;
                margin: 40px auto;
                padding: 30px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }}
            h2 {{ color: #b91c1c; }}
            p {{ color: #374151; line-height: 1.6; }}
            button {{
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                background: #2563eb;
                color: white;
                cursor: pointer;
                font-size: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>Invalid Input</h2>
            <p>{message}</p>
            <button onclick="history.back()">Go Back</button>
        </div>
    </body>
    </html>
    """

    return page, 400


def register_phone_validation(app):

    @app.before_request
    def validate_phone_and_customer_name():

        if request.method != "POST":
            return None

        # ---------------------------------------------
        # 1. VALIDATE CUSTOMER NAME
        # ---------------------------------------------

        endpoint = (request.endpoint or "").lower()

        customer_name_fields = []

        for field_name in request.form.keys():

            normalized_name = field_name.lower()

            if normalized_name in (
                "customer_name",
                "customername",
                "customer_full_name"
            ):
                customer_name_fields.append(field_name)

            # On a customer-management route, "name" means
            # the customer's name rather than a product name.
            elif "customer" in endpoint and normalized_name == "name":
                customer_name_fields.append(field_name)

        for field_name in customer_name_fields:

            customer_name = request.form.get(field_name, "")

            if not is_valid_customer_name(customer_name):
                return validation_error(
                    "Enter a valid customer name. "
                    "Use letters and spaces only, with optional "
                    "periods, apostrophes or hyphens. "
                    "Example: Darshan Jain. "
                    "Numbers, @ and underscores are not allowed."
                )

        # ---------------------------------------------
        # 2. VALIDATE PHONE NUMBERS
        # ---------------------------------------------

        for field_name, raw_value in request.form.items():

            normalized_name = field_name.lower()

            if not any(
                marker in normalized_name
                for marker in PHONE_FIELD_MARKERS
            ):
                continue

            phone = (raw_value or "").strip()

            # Keep optional phone fields optional.
            if phone == "":
                continue

            if PHONE_PATTERN.fullmatch(phone) is None:
                return validation_error(
                    "Enter a valid phone number containing "
                    "exactly 10 digits (0-9)."
                )

        return None