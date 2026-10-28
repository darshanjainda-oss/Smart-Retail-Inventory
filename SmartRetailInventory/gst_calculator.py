from decimal import Decimal, ROUND_HALF_UP


def round_money(value):
    """Round a monetary value to two decimal places."""
    return float(
        Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    )


def calculate_gst(taxable_amount, gst_rate, supply_type="intra"):
    """
    Calculate GST for a retail sale.

    taxable_amount:
        Amount after discount but before GST.

    gst_rate:
        Total applicable GST percentage for the product.

    supply_type:
        intra = CGST + SGST
        inter = IGST
    """

    taxable_amount = Decimal(str(taxable_amount))
    gst_rate = Decimal(str(gst_rate))

    if taxable_amount < 0:
        raise ValueError("Taxable amount cannot be negative.")

    if gst_rate < 0 or gst_rate > 40:
        raise ValueError("GST rate must be between 0 and 40.")

    supply_type = supply_type.strip().lower()

    if supply_type not in ("intra", "inter"):
        raise ValueError("Invalid supply type.")

    tax_amount = (
        taxable_amount * gst_rate / Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    cgst_amount = Decimal("0.00")
    sgst_amount = Decimal("0.00")
    igst_amount = Decimal("0.00")

    if supply_type == "intra":
        # Split total GST equally between CGST and SGST.
        cgst_amount = (
            tax_amount / Decimal("2")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # Assign the remaining paisa to SGST if required.
        sgst_amount = tax_amount - cgst_amount

    else:
        # Inter-state supply: apply IGST instead.
        igst_amount = tax_amount

    total_amount = taxable_amount + tax_amount

    return {
        "taxable_amount": float(taxable_amount),
        "gst_rate": float(gst_rate),
        "gst_amount": float(tax_amount),
        "cgst_amount": float(cgst_amount),
        "sgst_amount": float(sgst_amount),
        "igst_amount": float(igst_amount),
        "total_amount": float(total_amount),
        "supply_type": supply_type,
    }