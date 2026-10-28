"""Expiry-aware inventory decision support for Smart Retail Inventory.

This module is read-only: it calculates estimates and recommendations from the
existing products and sales tables. It does not update stock, sales, or expiry
records. It expects database.py to expose get_connection().
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from database import get_connection

DEFAULT_LOOKBACK_DAYS = 90
DEFAULT_NEAR_EXPIRY_DAYS = 30


def _classify_product(
    row: dict[str, Any],
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    near_expiry_days: int = DEFAULT_NEAR_EXPIRY_DAYS,
) -> dict[str, Any]:
    """Calculate transparent expiry sell-through and replenishment guidance."""
    stock = max(0, int(row.get("stock") or 0))
    units_sold = max(0, int(row.get("units_sold") or 0))
    sale_days = max(0, int(row.get("sale_days") or 0))
    days_to_expiry = row.get("days_to_expiry")
    expiry_date = row.get("expiry_date")

    average_daily_demand = units_sold / max(1, lookback_days)
    if days_to_expiry is None:
        days_remaining = None
        expected_sales_before_expiry = None
        expected_unsold = None
        unsold_percent = None
    else:
        days_remaining = max(0, int(days_to_expiry))
        expected_sales_before_expiry = round(average_daily_demand * days_remaining, 1)
        expected_unsold = round(max(0.0, stock - expected_sales_before_expiry), 1)
        unsold_percent = round((expected_unsold / stock) * 100, 1) if stock > 0 else 0.0

    # Confidence is based on the amount of real sales evidence, not on a claim
    # that the estimates are scientifically validated or guaranteed.
    if units_sold >= 20 and sale_days >= 20:
        confidence = "High"
        confidence_note = "At least 20 units sold across 20 or more distinct sale dates in the lookback window."
    elif units_sold >= 8 and sale_days >= 8:
        confidence = "Medium"
        confidence_note = "Moderate sales history; treat the estimate as planning guidance."
    else:
        confidence = "Low"
        confidence_note = "Sparse sales history; verify demand manually before making a purchase decision."

    result = {
        "product_id": row.get("product_id"),
        "name": row.get("name") or "Unnamed product",
        "category": row.get("category") or "—",
        "supplier": row.get("supplier") or "—",
        "supplier_contact": row.get("supplier_contact") or "—",
        "stock": stock,
        "expiry_date": expiry_date,
        "days_to_expiry": days_to_expiry,
        "units_sold": units_sold,
        "sale_days": sale_days,
        "average_daily_demand": round(average_daily_demand, 3),
        "expected_sales_before_expiry": expected_sales_before_expiry,
        "expected_unsold": expected_unsold,
        "unsold_percent": unsold_percent,
        "confidence": confidence,
        "confidence_note": confidence_note,
        "lookback_days": lookback_days,
    }

    # Hard expiry alert first: never present expired stock as sellable.
    if days_to_expiry is not None and int(days_to_expiry) < 0 and stock > 0:
        result.update({
            "risk_level": "Critical",
            "risk_key": "critical",
            "decision_label": "EXPIRED — DO NOT SELL",
            "action": "Keep the expired stock out of sale and follow the store's applicable return/disposal procedure. Do not reorder based on this expired stock; review demand and incoming batch expiry separately.",
        })
    elif stock == 0:
        result.update({
            "risk_level": "No stock",
            "risk_key": "info",
            "decision_label": "CHECK STANDARD REORDER RULE",
            "action": "There is no on-hand stock. Review the standard reorder recommendation and confirm the expiry date of the incoming supplier batch before ordering.",
        })
    elif days_to_expiry is None:
        result.update({
            "risk_level": "Unknown",
            "risk_key": "unknown",
            "decision_label": "EXPIRY DATE MISSING",
            "action": "Add or verify the product expiry date before using expiry-aware replenishment guidance. The system cannot estimate sell-through before expiry without this date.",
        })
    elif int(days_to_expiry) <= near_expiry_days and confidence == "Low":
        result.update({
            "risk_level": "Review urgently",
            "risk_key": "warning",
            "decision_label": "REVIEW BEFORE REORDER",
            "action": "Expiry is near and the sales history is sparse. Prioritize checking and selling eligible existing stock, verify the physical quantity and demand, and avoid blindly increasing the order. Treat the estimated unsold quantity as low-confidence guidance.",
        })
    elif int(days_to_expiry) <= 7 and (expected_unsold or 0) > 0:
        result.update({
            "risk_level": "Critical",
            "risk_key": "critical",
            "decision_label": "PAUSE REORDER — CLEAR STOCK",
            "action": "The product expires within 7 days and some stock may remain unsold. Prioritize eligible existing stock; consider store-approved promotions where permitted. Review any new order separately and verify the incoming batch's expiry date.",
        })
    elif int(days_to_expiry) <= near_expiry_days and (unsold_percent or 0) >= 20:
        result.update({
            "risk_level": "High",
            "risk_key": "high",
            "decision_label": "PAUSE REORDER — CLEAR STOCK",
            "action": "The estimate suggests at least 20% of current stock could remain unsold at expiry. Prioritize selling eligible existing stock and reassess demand before replenishing. Confirm the expiry date of any incoming batch.",
        })
    elif int(days_to_expiry) <= near_expiry_days:
        result.update({
            "risk_level": "Watch",
            "risk_key": "warning",
            "decision_label": "MONITOR SELL-THROUGH",
            "action": "Expiry is within the next 30 days. Monitor sales and existing quantity. Only place a new order after checking the standard reorder recommendation and the incoming batch's expiry date.",
        })
    elif confidence == "Low":
        result.update({
            "risk_level": "Low confidence",
            "risk_key": "unknown",
            "decision_label": "MANUAL REVIEW",
            "action": "There is not enough sales evidence for a dependable sell-through estimate. Keep the expiry date monitored and use the regular reorder recommendation only after checking actual demand.",
        })
    elif (expected_unsold or 0) > 0 and (unsold_percent or 0) >= 20:
        result.update({
            "risk_level": "Monitor",
            "risk_key": "info",
            "decision_label": "MONITOR STOCK",
            "action": "The estimate suggests some stock may remain unsold by expiry, although expiry is not immediate. Monitor sales and avoid unnecessary extra stock; review the regular reorder recommendation before replenishing.",
        })
    else:
        result.update({
            "risk_level": "Lower estimated risk",
            "risk_key": "success",
            "decision_label": "REORDER REVIEW",
            "action": "Estimated sell-through is closer to current stock, but this is not a purchase order by itself. Review the normal reorder point and confirm that the supplier's incoming batch has a suitable expiry date.",
        })

    return result


def get_expiry_decision_report(
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    near_expiry_days: int = DEFAULT_NEAR_EXPIRY_DAYS,
) -> dict[str, Any]:
    """Fetch product/sales data and return expiry-aware decision rows + counts.

    Sales velocity uses total units sold during the prior ``lookback_days``
    divided by calendar days in that window. If there is little sales evidence,
    confidence is explicitly labelled Low. No database records are changed.
    """
    if not 1 <= int(lookback_days) <= 365:
        raise ValueError("lookback_days must be between 1 and 365")
    if not 1 <= int(near_expiry_days) <= 180:
        raise ValueError("near_expiry_days must be between 1 and 180")

    cutoff = date.today() - timedelta(days=int(lookback_days))
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                p.product_id,
                p.name,
                p.category,
                p.supplier,
                p.supplier_contact,
                p.price,
                p.stock,
                p.expiry_date,
                DATEDIFF(p.expiry_date, CURDATE()) AS days_to_expiry,
                COALESCE(SUM(
                    CASE WHEN s.sale_date >= %s THEN s.quantity ELSE 0 END
                ), 0) AS units_sold,
                COUNT(DISTINCT CASE
                    WHEN s.sale_date >= %s THEN DATE(s.sale_date)
                    ELSE NULL
                END) AS sale_days
            FROM products AS p
            LEFT JOIN sales AS s ON s.product_id = p.product_id
            GROUP BY
                p.product_id, p.name, p.category, p.supplier,
                p.supplier_contact, p.price, p.stock, p.expiry_date
            ORDER BY
                CASE
                    WHEN p.expiry_date IS NOT NULL AND p.expiry_date < CURDATE() THEN 0
                    WHEN p.expiry_date IS NOT NULL THEN 1
                    ELSE 2
                END,
                p.expiry_date ASC,
                p.name ASC
            """,
            (cutoff, cutoff),
        )
        rows = cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

    decisions = [
        _classify_product(
            row,
            lookback_days=int(lookback_days),
            near_expiry_days=int(near_expiry_days),
        )
        for row in rows
    ]

    summary = {
        "total_products": len(decisions),
        "expired_with_stock": sum(
            1 for item in decisions
            if item["days_to_expiry"] is not None
            and int(item["days_to_expiry"]) < 0
            and item["stock"] > 0
        ),
        "near_expiry": sum(
            1 for item in decisions
            if item["days_to_expiry"] is not None
            and 0 <= int(item["days_to_expiry"]) <= int(near_expiry_days)
            and item["stock"] > 0
        ),
        "missing_expiry_date": sum(1 for item in decisions if item["days_to_expiry"] is None),
        "low_confidence": sum(1 for item in decisions if item["confidence"] == "Low"),
        "reorder_pause_suggestions": sum(
            1 for item in decisions if item["decision_label"] == "PAUSE REORDER — CLEAR STOCK"
        ),
    }

    return {
        "decisions": decisions,
        "summary": summary,
        "lookback_days": int(lookback_days),
        "near_expiry_days": int(near_expiry_days),
    }
