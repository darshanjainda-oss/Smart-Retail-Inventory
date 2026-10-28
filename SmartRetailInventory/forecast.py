import math

from sklearn.linear_model import LinearRegression

from database import get_connection, load_products_from_database


# =========================================================
# SETTINGS
# =========================================================

# Default supplier lead time for this prototype.
# Later this can be stored separately for every supplier.
DEFAULT_LEAD_TIME_DAYS = 3

# Minimum number of different sales days needed
# before the ML model is used.
MIN_ML_HISTORY_DAYS = 3

# Safety stock buffer.
SAFETY_STOCK_PERCENT = 0.20


# =========================================================
# GET HISTORICAL SALES
# =========================================================

def get_sales_data():

    connection = get_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            p.product_id,
            p.name AS product,
            p.supplier,
            p.supplier_contact,
            p.stock AS current_stock,
            DATE(s.sale_date) AS sale_date,
            SUM(s.quantity) AS quantity
        FROM sales s

        JOIN products p
            ON s.product_id = p.product_id

        GROUP BY
            p.product_id,
            p.name,
            p.supplier,
            p.supplier_contact,
            p.stock,
            DATE(s.sale_date)

        ORDER BY
            p.name,
            sale_date
    """

    cursor.execute(query)

    data = cursor.fetchall()

    cursor.close()

    connection.close()

    return data


# =========================================================
# GET PRODUCT
# =========================================================

def get_product(product_name):

    products = load_products_from_database()

    for product in products:

        if (
            product["name"].strip().lower()
            == product_name.strip().lower()
        ):

            return product

    return None


# =========================================================
# FORECAST PRODUCT DEMAND
# =========================================================

def forecast_product(product_name, days=7):

    product = get_product(product_name)

    if product is None:

        return {
            "status": "error",
            "message": "Product not found."
        }


    sales_data = get_sales_data()


    product_sales = [

        row for row in sales_data

        if row["product_id"]
        == product["product_id"]

    ]


    if not product_sales:

        return {

            "status": "insufficient",

            "message":
                "No historical sales data available.",

            "history_days": 0

        }


    # ------------------------------------------------------
    # CREATE DAILY SALES DATA
    # ------------------------------------------------------

    product_sales.sort(
        key=lambda row: row["sale_date"]
    )


    history_days = len(product_sales)


    quantities = [

        float(row["quantity"])

        for row in product_sales

    ]


    total_units = sum(quantities)


    average_daily_demand = (
        total_units / history_days
    )


    # ------------------------------------------------------
    # ML FORECAST
    # ------------------------------------------------------

    if history_days >= MIN_ML_HISTORY_DAYS:

        X = [
            [index]
            for index in range(history_days)
        ]

        y = quantities


        model = LinearRegression()

        model.fit(X, y)


        future_X = [

            [history_days + index]

            for index in range(days)

        ]


        predictions = model.predict(
            future_X
        )


        predictions = [

            max(
                0,
                round(
                    float(prediction),
                    2
                )
            )

            for prediction in predictions

        ]


        method = "ML Linear Regression"

    else:

        # --------------------------------------------------
        # FALLBACK
        # --------------------------------------------------
        # We do NOT create fake historical data.
        # With limited history, use recent real sales
        # velocity instead of pretending ML is reliable.
        # --------------------------------------------------

        predictions = [

            round(
                max(
                    0,
                    average_daily_demand
                ),
                2
            )

            for _ in range(days)

        ]


        method = (
            "Recent Sales Velocity "
            "(insufficient ML history)"
        )


    total_forecast = round(
        sum(predictions),
        2
    )


    return {

        "status": "success",

        "history_days": history_days,

        "average_daily_demand":
            round(
                average_daily_demand,
                2
            ),

        "predictions":
            predictions,

        "total_forecast":
            total_forecast,

        "method":
            method

    }


# =========================================================
# SMART REORDER ENGINE
# =========================================================

def get_restock_recommendation(
    product_name,
    days=7,
    lead_time_days=DEFAULT_LEAD_TIME_DAYS
):

    product = get_product(product_name)


    if product is None:

        return {

            "status": "error",

            "message":
                "Product not found."

        }


    forecast = forecast_product(
        product_name,
        days
    )


    if forecast["status"] != "success":

        return forecast


    current_stock = int(
        product["stock"]
    )


    average_daily_demand = float(
        forecast["average_daily_demand"]
    )


    predicted_demand = float(
        forecast["total_forecast"]
    )


    # ------------------------------------------------------
    # SAFETY STOCK
    # ------------------------------------------------------

    safety_stock = max(

        1,

        math.ceil(
            predicted_demand
            * SAFETY_STOCK_PERCENT
        )

    )


    # ------------------------------------------------------
    # DEMAND DURING SUPPLIER LEAD TIME
    # ------------------------------------------------------

    lead_time_demand = (

        average_daily_demand
        * lead_time_days

    )


    lead_time_demand = round(
        lead_time_demand,
        2
    )


    # ------------------------------------------------------
    # REORDER POINT
    # ------------------------------------------------------

    reorder_point = math.ceil(

        lead_time_demand
        + safety_stock

    )


    # ------------------------------------------------------
    # TARGET STOCK
    # ------------------------------------------------------

    target_stock = math.ceil(

        predicted_demand
        + lead_time_demand
        + safety_stock

    )


    # ------------------------------------------------------
    # REORDER QUANTITY
    # ------------------------------------------------------

    reorder_quantity = max(

        0,

        target_stock - current_stock

    )


    # ------------------------------------------------------
    # STOCK COVERAGE
    # ------------------------------------------------------

    if average_daily_demand > 0:

        stock_coverage_days = round(

            current_stock
            / average_daily_demand,

            1

        )

    else:

        stock_coverage_days = None


    # ------------------------------------------------------
    # ESTIMATED STOCKOUT
    # ------------------------------------------------------

    if (
        average_daily_demand > 0
        and current_stock > 0
    ):

        stockout_in_days = round(

            current_stock
            / average_daily_demand,

            1

        )

    elif current_stock <= 0:

        stockout_in_days = 0

    else:

        stockout_in_days = None


    # ------------------------------------------------------
    # RISK / PRIORITY
    # ------------------------------------------------------

    if current_stock <= 0:

        status = "OUT OF STOCK"

        priority = "CRITICAL"

        reason = (
            "Product is currently out of stock."
        )


    elif (
        stock_coverage_days is not None
        and stock_coverage_days
        <= lead_time_days
    ):

        status = "RESTOCK REQUIRED"

        priority = "HIGH"

        reason = (

            "Current stock may not cover "
            "supplier lead time based on "
            "recent sales demand."

        )


    elif current_stock < reorder_point:

        status = "RESTOCK REQUIRED"

        priority = "HIGH"

        reason = (

            "Current stock is below the "
            "calculated reorder point."

        )


    elif current_stock < target_stock:

        status = "PLAN RESTOCK"

        priority = "MEDIUM"

        reason = (

            "Stock is below the recommended "
            "target inventory level."

        )


    else:

        status = "STOCK SUFFICIENT"

        priority = "LOW"

        reason = (

            "Current stock is sufficient "
            "for the calculated demand target."

        )


    # ------------------------------------------------------
    # RECOMMENDED STOCK
    # ------------------------------------------------------

    recommended_stock = target_stock


    # ------------------------------------------------------
    # RETURN SMART DECISION
    # ------------------------------------------------------

    return {

        "status": "success",

        "product": product["name"],

        "supplier":
            product.get(
                "supplier",
                ""
            ),

        "supplier_contact":
            product.get(
                "supplier_contact",
                ""
            ),

        "current_stock":
            current_stock,

        "history_days":
            forecast["history_days"],

        "average_daily_demand":
            average_daily_demand,

        "predicted_demand":
            predicted_demand,

        "lead_time_days":
            lead_time_days,

        "lead_time_demand":
            lead_time_demand,

        "safety_stock":
            safety_stock,

        "reorder_point":
            reorder_point,

        "recommended_stock":
            recommended_stock,

        "additional_stock":
            reorder_quantity,

        "reorder_quantity":
            reorder_quantity,

        "stock_coverage_days":
            stock_coverage_days,

        "stockout_in_days":
            stockout_in_days,

        "stock_status":
            status,

        "priority":
            priority,

        "reason":
            reason,

        "method":
            forecast["method"],

        "predictions":
            forecast["predictions"]

    }