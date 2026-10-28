import math

from forecast import forecast_product
from database import load_products_from_database


# =========================================================
# RETAIL DECISION SIMULATOR
# =========================================================

def simulate_scenario(
    product_name,
    demand_increase,
    extra_supplier_delay
):

    products = load_products_from_database()

    product = None

    for item in products:

        if (
            item["name"].strip().lower()
            == product_name.strip().lower()
        ):

            product = item
            break


    if product is None:

        return {

            "status": "error",

            "message":
                "Product not found."

        }


    # =====================================================
    # GET BASE FORECAST
    # =====================================================

    forecast = forecast_product(
        product_name,
        days=7
    )


    if forecast["status"] != "success":

        return {

            "status": "insufficient",

            "message":
                forecast["message"],

            "history_days":
                forecast.get(
                    "history_days",
                    0
                )

        }


    # =====================================================
    # BASIC DATA
    # =====================================================

    current_stock = int(
        product["stock"]
    )


    average_daily_demand = float(
        forecast["average_daily_demand"]
    )


    original_7_day_demand = float(
        forecast["total_forecast"]
    )


    # =====================================================
    # DEMAND SHOCK
    # =====================================================

    demand_multiplier = (
        1 + demand_increase / 100
    )


    scenario_daily_demand = (

        average_daily_demand
        * demand_multiplier

    )


    scenario_daily_demand = round(
        scenario_daily_demand,
        2
    )


    scenario_7_day_demand = (

        original_7_day_demand
        * demand_multiplier

    )


    scenario_7_day_demand = round(
        scenario_7_day_demand,
        2
    )


    # =====================================================
    # SUPPLIER DELAY
    # =====================================================

    base_lead_time = 3

    scenario_lead_time = (

        base_lead_time
        + extra_supplier_delay

    )


    # =====================================================
    # SAFETY STOCK
    # =====================================================

    safety_stock = max(

        1,

        math.ceil(
            scenario_7_day_demand
            * 0.20
        )

    )


    # =====================================================
    # LEAD-TIME DEMAND
    # =====================================================

    lead_time_demand = (

        scenario_daily_demand
        * scenario_lead_time

    )


    lead_time_demand = round(
        lead_time_demand,
        2
    )


    # =====================================================
    # NEW REORDER POINT
    # =====================================================

    reorder_point = math.ceil(

        lead_time_demand
        + safety_stock

    )


    # =====================================================
    # TARGET STOCK
    # =====================================================

    target_stock = math.ceil(

        scenario_7_day_demand
        + lead_time_demand
        + safety_stock

    )


    # =====================================================
    # REORDER QUANTITY
    # =====================================================

    reorder_quantity = max(

        0,

        target_stock - current_stock

    )


    # =====================================================
    # STOCK COVERAGE
    # =====================================================

    if scenario_daily_demand > 0:

        stock_coverage = round(

            current_stock
            / scenario_daily_demand,

            1

        )

    else:

        stock_coverage = None


    # =====================================================
    # STOCKOUT RISK
    # =====================================================

    if current_stock <= 0:

        stockout_days = 0

        risk = "CRITICAL"


    elif scenario_daily_demand > 0:

        stockout_days = round(

            current_stock
            / scenario_daily_demand,

            1

        )


        if stockout_days <= scenario_lead_time:

            risk = "HIGH"

        elif stockout_days <= 7:

            risk = "MEDIUM"

        else:

            risk = "LOW"

    else:

        stockout_days = None

        risk = "LOW"


    # =====================================================
    # ADDITIONAL DEMAND CAUSED BY SCENARIO
    # =====================================================

    additional_demand = round(

        scenario_7_day_demand
        - original_7_day_demand,

        2

    )


    # =====================================================
    # RECOMMENDATION
    # =====================================================

    if reorder_quantity > 0:

        recommendation = (

            f"Prepare to reorder "
            f"{reorder_quantity} units."

        )

    else:

        recommendation = (

            "Current inventory can cover "
            "the simulated scenario."

        )


    # =====================================================
    # EXPLANATION
    # =====================================================

    reasons = []


    if demand_increase > 0:

        reasons.append(

            f"Demand increased by "
            f"{demand_increase:.0f}%."

        )


    if extra_supplier_delay > 0:

        reasons.append(

            f"Supplier lead time increased "
            f"by {extra_supplier_delay} days."

        )


    if risk in [
        "HIGH",
        "CRITICAL"
    ]:

        reasons.append(

            "The simulated stock coverage "
            "is shorter than the supplier "
            "lead time."

        )


    if not reasons:

        reasons.append(

            "No additional demand or "
            "supplier delay was applied."

        )


    explanation = " ".join(
        reasons
    )


    # =====================================================
    # RETURN SCENARIO
    # =====================================================

    return {

        "status":
            "success",

        "product":
            product["name"],

        "current_stock":
            current_stock,

        "original_7_day_demand":
            original_7_day_demand,

        "scenario_7_day_demand":
            scenario_7_day_demand,

        "additional_demand":
            additional_demand,

        "original_daily_demand":
            average_daily_demand,

        "scenario_daily_demand":
            scenario_daily_demand,

        "demand_increase":
            demand_increase,

        "base_lead_time":
            base_lead_time,

        "scenario_lead_time":
            scenario_lead_time,

        "extra_supplier_delay":
            extra_supplier_delay,

        "safety_stock":
            safety_stock,

        "reorder_point":
            reorder_point,

        "target_stock":
            target_stock,

        "reorder_quantity":
            reorder_quantity,

        "stock_coverage":
            stock_coverage,

        "stockout_days":
            stockout_days,

        "risk":
            risk,

        "recommendation":
            recommendation,

        "explanation":
            explanation,

        "method":
            forecast["method"]

    }