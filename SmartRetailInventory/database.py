import mysql.connector


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():

    return mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="retail_app",
        password="RetailApp@2026",
        database="smart_retail_inventory"
    )


# =========================================================
# ADD PRODUCT
# =========================================================

def add_product_to_database(
    name,
    category,
    supplier,
    supplier_contact,
    price,
    stock,
    expiry_date=None
):

    connection = get_connection()
    cursor = connection.cursor()

    query = """
        INSERT INTO products
        (
            name,
            category,
            supplier,
            supplier_contact,
            price,
            stock,
            expiry_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        name,
        category,
        supplier,
        supplier_contact,
        price,
        stock,
        expiry_date
    )

    cursor.execute(query, values)

    connection.commit()

    cursor.close()
    connection.close()


# =========================================================
# LOAD PRODUCTS
# =========================================================

def load_products_from_database():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT
            product_id,
            name,
            category,
            supplier,
            supplier_contact,
            price,
            stock,
            expiry_date,
            DATEDIFF(
                expiry_date,
                CURDATE()
            ) AS days_to_expiry
        FROM products
        ORDER BY product_id
    """

    cursor.execute(query)

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return products


# =========================================================
# CUSTOMER
# =========================================================

def get_or_create_customer(
    name,
    phone
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT customer_id
        FROM customers
        WHERE phone = %s
        """,
        (phone,)
    )

    customer = cursor.fetchone()

    if customer:

        customer_id = customer[0]

    else:

        cursor.execute(
            """
            INSERT INTO customers
            (
                name,
                phone
            )
            VALUES
            (
                %s,
                %s
            )
            """,
            (
                name,
                phone
            )
        )

        customer_id = cursor.lastrowid

    connection.commit()

    cursor.close()
    connection.close()

    return customer_id


# =========================================================
# UPDATE PRODUCT STOCK
# =========================================================

def update_product_stock(
    product_id,
    new_stock
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE products
        SET stock = %s
        WHERE product_id = %s
        """,
        (
            new_stock,
            product_id
        )
    )

    connection.commit()

    cursor.close()
    connection.close()


# =========================================================
# RECORD SALE
# =========================================================

def record_sale(
    invoice_number,
    product_id,
    customer_id,
    quantity,
    price,
    subtotal,
    discount_percent,
    discount_amount,
    total
):

    connection = get_connection()

    cursor = connection.cursor()

    query = """
        INSERT INTO sales
        (
            invoice_number,
            product_id,
            customer_id,
            quantity,
            price,
            subtotal,
            discount_percent,
            discount_amount,
            total,
            sale_date
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            NOW()
        )
    """

    values = (
        invoice_number,
        product_id,
        customer_id,
        quantity,
        price,
        subtotal,
        discount_percent,
        discount_amount,
        total
    )

    cursor.execute(
        query,
        values
    )

    connection.commit()

    cursor.close()
    connection.close()


# =========================================================
# LOAD SALES
# =========================================================

# =========================================================
# LOAD SALES
# =========================================================

def load_sales_from_database():

    connection = get_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            s.sale_id,
            s.invoice_number,
            s.sale_date AS date,
            c.name AS customer_name,
            c.phone AS customer_phone,
            p.name AS product,
            s.quantity,
            s.price,
            s.discount_percent,
            s.discount_amount,
            s.total
        FROM sales s

        JOIN products p
            ON s.product_id = p.product_id

        LEFT JOIN customers c
            ON s.customer_id = c.customer_id

        ORDER BY
            s.sale_date DESC
    """

    cursor.execute(query)

    sales = cursor.fetchall()

    cursor.close()
    connection.close()

    return sales


# =========================================================
# INVENTORY SUMMARY
# =========================================================

def get_inventory_summary():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT

            COUNT(*) AS total_products,

            COALESCE(
                SUM(stock),
                0
            ) AS total_stock,

            COALESCE(
                SUM(price * stock),
                0
            ) AS total_inventory_value,

            COALESCE(
                SUM(
                    CASE
                        WHEN stock < 10
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS low_stock_count

        FROM products
    """

    cursor.execute(query)

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return result


# =========================================================
# SALES SUMMARY
# =========================================================

def get_sales_summary():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT

            COUNT(*) AS total_sales,

            COALESCE(
                SUM(quantity),
                0
            ) AS total_items,

            COALESCE(
                SUM(total),
                0
            ) AS total_revenue,

            COALESCE(
                AVG(total),
                0
            ) AS average_sale

        FROM sales
    """

    cursor.execute(query)

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return result


# =========================================================
# TOP SELLING PRODUCTS
# =========================================================

def get_top_selling_products():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT

            p.name AS product,

            SUM(
                s.quantity
            ) AS quantity_sold

        FROM sales s

        JOIN products p
            ON s.product_id =
               p.product_id

        GROUP BY
            p.product_id,
            p.name

        ORDER BY
            quantity_sold DESC
    """

    cursor.execute(query)

    result = cursor.fetchall()

    cursor.close()
    connection.close()

    return result


# =========================================================
# DAILY SALES REPORT
# =========================================================

def get_daily_sales_report():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT

            COUNT(*)
                AS total_transactions,

            COALESCE(
                SUM(quantity),
                0
            )
                AS total_items,

            COALESCE(
                SUM(total),
                0
            )
                AS total_revenue

        FROM sales

        WHERE DATE(sale_date)
              = CURDATE()
    """

    cursor.execute(query)

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return result


# =========================================================
# SALES CHART DATA
# =========================================================

def get_sales_chart_data():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT

            DATE(sale_date)
                AS sale_day,

            SUM(total)
                AS revenue

        FROM sales

        GROUP BY
            DATE(sale_date)

        ORDER BY
            sale_day
    """

    cursor.execute(query)

    result = cursor.fetchall()

    cursor.close()
    connection.close()

    return result


# =========================================================
# CATEGORY STOCK DATA
# =========================================================

def get_category_stock_data():

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT

            category,

            SUM(stock)
                AS total_stock

        FROM products

        GROUP BY
            category

        ORDER BY
            total_stock DESC
    """

    cursor.execute(query)

    result = cursor.fetchall()

    cursor.close()
    connection.close()

    return result


# =========================================================
# EXPIRY ALERTS
# =========================================================

def get_expiry_alerts(days=30):

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT

            product_id,

            name,

            category,

            stock,

            expiry_date,

            DATEDIFF(
                expiry_date,
                CURDATE()
            ) AS days_to_expiry

        FROM products

        WHERE

            expiry_date IS NOT NULL

            AND expiry_date <= DATE_ADD(
                CURDATE(),
                INTERVAL %s DAY
            )

        ORDER BY
            expiry_date ASC
    """

    cursor.execute(
        query,
        (days,)
    )

    alerts = cursor.fetchall()

    cursor.close()
    connection.close()

    return alerts