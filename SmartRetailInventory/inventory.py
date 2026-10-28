from database import add_product_to_database, get_connection


def add_product(inventory):

    name = input("Enter Product Name: ").strip()
    category = input("Enter Category: ").strip()
    supplier = input("Enter Supplier Name: ").strip()
    supplier_contact = input("Enter Supplier Contact Number: ").strip()

    try:
        price = float(input("Enter Price: "))

        if price < 0:
            print("\n❌ Price cannot be negative.")
            return

        stock = int(input("Enter Stock Quantity: "))

        if stock < 0:
            print("\n❌ Stock cannot be negative.")
            return

    except ValueError:
        print("\n❌ Please enter valid numbers for price and stock.")
        return

    # Check duplicate product in MySQL
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT product_id FROM products WHERE LOWER(name) = LOWER(%s)",
        (name,)
    )

    existing_product = cursor.fetchone()

    cursor.close()
    connection.close()

    if existing_product:
        print("\n❌ Product already exists.")
        return

    # Add product to MySQL
    add_product_to_database(
        name,
        category,
        supplier,
        supplier_contact,
        price,
        stock
    )

    print("\n✅ Product Added Successfully to MySQL!")


def view_products(inventory):

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products ORDER BY product_id")

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    if not products:
        print("\nNo Products Available.")
        return

    print("\n========= PRODUCT LIST =========")

    for product in products:

        inventory_value = (
            product["price"] * product["stock"]
        )

        print("--------------------------------")
        print("ID                :", product["product_id"])
        print("Name              :", product["name"])
        print("Category          :", product["category"])
        print("Supplier          :", product["supplier"])
        print("Supplier Contact  :", product["supplier_contact"])
        print("Price             : ₹", product["price"])
        print("Stock             :", product["stock"])
        print("Inventory Value   : ₹", inventory_value)


def search_product(inventory):

    search = input("Enter Product Name: ").strip()

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE LOWER(name) = LOWER(%s)
        """,
        (search,)
    )

    product = cursor.fetchone()

    cursor.close()
    connection.close()

    if product:

        inventory_value = (
            product["price"] * product["stock"]
        )

        print("\n========= PRODUCT FOUND =========")
        print("--------------------------------")
        print("ID                :", product["product_id"])
        print("Name              :", product["name"])
        print("Category          :", product["category"])
        print("Supplier          :", product["supplier"])
        print("Supplier Contact  :", product["supplier_contact"])
        print("Price             : ₹", product["price"])
        print("Stock             :", product["stock"])
        print("Inventory Value   : ₹", inventory_value)

    else:
        print("\n❌ Product Not Found.")


def update_stock(inventory):

    search = input("Enter Product Name: ").strip()

    try:
        new_stock = int(input("Enter New Stock: "))

        if new_stock < 0:
            print("\n❌ Stock cannot be negative.")
            return

    except ValueError:
        print("\n❌ Please enter a valid stock number.")
        return

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE products
        SET stock = %s
        WHERE LOWER(name) = LOWER(%s)
        """,
        (new_stock, search)
    )

    connection.commit()

    affected_rows = cursor.rowcount

    cursor.close()
    connection.close()

    if affected_rows > 0:
        print("\n✅ Stock Updated Successfully.")
    else:
        print("\n❌ Product Not Found.")


def delete_product(inventory):

    search = input("Enter Product Name: ").strip()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM products
        WHERE LOWER(name) = LOWER(%s)
        """,
        (search,)
    )

    connection.commit()

    affected_rows = cursor.rowcount

    cursor.close()
    connection.close()

    if affected_rows > 0:
        print("\n🗑 Product Deleted Successfully.")
    else:
        print("\n❌ Product Not Found.")


def low_stock(inventory):

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM products WHERE stock < 10 ORDER BY stock"
    )

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    print("\n======= LOW STOCK PRODUCTS =======")

    if not products:
        print("No Low Stock Products.")
        return

    for product in products:
        print(
            product["name"],
            "- Remaining:",
            product["stock"]
        )