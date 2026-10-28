from forecast import forecast_product


result = forecast_product("Rice", 7)

print("7-Day Forecast:")

if result.get("status") != "success":
    print(
        result.get(
            "message",
            "Not enough historical sales data "
            "to generate a forecast."
        )
    )
else:
    for day, quantity in enumerate(
        result["predictions"],
        start=1
    ):
        print(
            f"Day {day}: {quantity} units"
        )

    print(
        f"\nMethod used: {result['method']}"
    )

    print(
        f"Total 7-day forecast: "
        f"{result['total_forecast']} units"
    )