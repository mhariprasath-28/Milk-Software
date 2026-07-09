from re import search


from flask import Flask, render_template, request, redirect,send_file
from datetime import date
from database import get_connection
import pandas as pd

from flask import send_file
from datetime import date
from reportlab.platypus import *
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from flask import jsonify

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape

app = Flask(__name__)


# Create table
conn = get_connection()
cursor = conn.cursor()



cursor.execute("""
CREATE TABLE IF NOT EXISTS shops(
    id SERIAL PRIMARY KEY,
    shop_name VARCHAR(200) NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products(
    id SERIAL PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    rate DOUBLE PRECISION NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS entries(
    id SERIAL PRIMARY KEY,
    group_id VARCHAR(100),
    entry_date DATE,
    shop_id INTEGER REFERENCES shops(id),
    product_id INTEGER REFERENCES products(id),
    liter DOUBLE PRECISION,
    rate DOUBLE PRECISION,
    total_amount DOUBLE PRECISION
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payment_entries(
    id SERIAL PRIMARY KEY,
    payment_date DATE,
    shop_id INTEGER REFERENCES shops(id),
    opening_balance DOUBLE PRECISION,
    amount DOUBLE PRECISION DEFAULT 0,
    remarks TEXT
)
""")
cursor.execute("""
ALTER TABLE payment_entries
ADD COLUMN IF NOT EXISTS amount DOUBLE PRECISION DEFAULT 0;
""")

conn.commit()
conn.close()
conn = get_connection()
conn.commit()
cursor = conn.cursor()

@app.route("/shops", methods=["GET", "POST"])
def shops():

    conn = get_connection()
    cursor = conn.cursor()
    if request.method == "POST":
        

        shop_name = request.form["shop_name"]

        cursor.execute(
            "INSERT INTO shops(shop_name) VALUES(%s)",
            (shop_name,)
        )

        conn.commit()

        print("Saved:", shop_name)

        return redirect("/shops")

    cursor.execute("SELECT * FROM shops")
    shops_list = cursor.fetchall()

    conn.close()

    return render_template(
    "shops.html",
    shops=shops_list
)

@app.route("/products", methods=["GET", "POST"])
def products():

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        product_name = request.form["product_name"]
        rate = request.form["rate"]

        cursor.execute(
            "INSERT INTO products(product_name, rate) VALUES(%s, %s)",
            (product_name, rate)
        )

        conn.commit()

        return redirect("/products")

    cursor.execute("SELECT * FROM products")
    product_list = cursor.fetchall()

    conn.close()

    return render_template(
        "products.html",
        products=product_list
    )
@app.route("/entry", methods=["GET", "POST"])
def entry():

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        entry_date = request.form["entry_date"]
        shop_id = request.form["shop_id"]
        product_ids = request.form.getlist("product_id[]")
        liters = request.form.getlist("liter[]")
        rates = request.form.getlist("rate[]")
        totals = request.form.getlist("total[]")

        print("PRODUCTS =", product_ids)
        print("LITERS =", liters)
        print("RATES =", rates)
        print("TOTALS =", totals)

        import uuid
        group_id = str(uuid.uuid4())

        def to_float(v, default=0.0):
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        def to_int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        rows_to_insert = []
        for i in range(len(product_ids)):
            pid = to_int(product_ids[i])
            liter = to_float(liters[i] if i < len(liters) else None)
            rate = to_float(rates[i] if i < len(rates) else None)
            total = to_float(totals[i] if i < len(totals) else None)

            if pid is None or liter == 0:
                # skip incomplete/blank rows instead of crashing
                continue

            rows_to_insert.append((
                group_id,
                entry_date,
                shop_id,
                pid,
                liter,
                rate,
                total,
            ))

        if not rows_to_insert:
            conn.close()
            return "No valid product rows submitted. Please fill in Product, Liter and Rate.", 400

        try:
            cursor.executemany("""
                INSERT INTO entries
                (group_id, entry_date, shop_id, product_id, liter, rate, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, rows_to_insert)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("DB ERROR:", e)
            return f"Error saving entry: {e}", 500
        finally:
            conn.close()

        return redirect("/entry")

    # ... rest of GET branch unchanged ...
    # Shop List
    cursor.execute("SELECT * FROM shops")
    selected_shop = request.args.get("shop_id")
    cursor.execute("""
SELECT *
FROM shops
ORDER BY shop_name
""")

    shops = cursor.fetchall()
    old_balance = 0

    if selected_shop:
        cursor.execute("""
            SELECT 
                    COALESCE(SUM(opening_balance),0),
                    COALESCE(SUM(amount),0)
            FROM payment_entries
            WHERE shop_id=%s
        """, (selected_shop,))
        payment_total ,amount_total= cursor.fetchone()

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount),0)
            FROM entries
            WHERE shop_id=%s
        """, (selected_shop,))
        entries_total = cursor.fetchone()[0]

        old_balance = payment_total + entries_total - amount_total
    # Product List
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    # Dashboard Cards
    cursor.execute("""
    SELECT COALESCE(SUM(total_amount),0)
    FROM entries
    """)
    total_collection = cursor.fetchone()[0]
    
    cursor.execute("""
    SELECT COALESCE(SUM(amount),0) 
                   FROM payment_entries
    """)
    total_paid = cursor.fetchone()[0]

    cursor.execute("""
SELECT
(
    SELECT COALESCE(SUM(opening_balance),0)-COALESCE(SUM(amount),0)
    FROM payment_entries
)
+
COALESCE(SUM(total_amount),0)
FROM entries
""")
    total_balance = cursor.fetchone()[0]
    entry_from_date = request.args.get("entry_from_date")
    entry_to_date = request.args.get("entry_to_date")
    if not entry_from_date and not entry_to_date:
        today_str = date.today().strftime("%Y-%m-%d")
        entry_from_date = today_str
        entry_to_date = today_str

    entry_where = ""
    entry_params = []

    if entry_from_date and entry_to_date:
        entry_where = " AND e.entry_date BETWEEN %s AND %s "
        entry_params = [entry_from_date, entry_to_date]


    # Entry Report
    query = f"""
    SELECT
        e.group_id::text AS group_ids,
        e.entry_date,
        s.shop_name,
        e.shop_id,
        STRING_AGG(
            p.product_name || ' - ' ||
            e.liter::text || 'L - Rs.' ||
            e.total_amount::text,
            '<br>'
        ) AS products,
        SUM(e.total_amount) AS total,
        0 AS balance
    FROM entries e
    JOIN shops s ON e.shop_id = s.id
    JOIN products p ON e.product_id = p.id
    WHERE 1=1 {entry_where}
    GROUP BY
        e.group_id,
        e.entry_date,
        s.shop_name,
        e.shop_id
    ORDER BY e.entry_date ASC
    """

    cursor.execute(query, entry_params)
    
    entries = cursor.fetchall()
    # entries are fetched ORDER BY entry_date DESC — sort oldest first to run the balance forward
    entries_sorted = entries

    # seed each shop's running balance with its payment_entries opening balance
    cursor.execute("SELECT id FROM shops")
    shop_ids = [r[0] for r in cursor.fetchall()]

    running_balance = {}
    for sid in shop_ids:
        cursor.execute("""
            SELECT COALESCE(SUM(opening_balance),0),
                       COALESCE(SUM(amount),0)
            FROM payment_entries
            WHERE shop_id=%s
        """, (sid,))
        opening_balance, received_amount = cursor.fetchone()
        running_balance[sid] = opening_balance - received_amount

    new_entries = []

    for row in entries_sorted:

        shop_id = row[3]
        total = float(row[5] or 0)
        

        old_bal = running_balance.get(shop_id, 0)
        running_balance[shop_id] = old_bal + total
        temp = list(row)
        temp[7] = running_balance[shop_id]
        temp.append(old_bal)   # index 8 = old balance before this entry

        new_entries.append(temp)

    new_entries.reverse()

    entries = new_entries

    today = date.today().strftime("%Y-%m-%d")

    conn.close()

    return render_template(
    "entry.html",
    shops=shops,
    products=products,
    entries=entries,
    total_collection=total_collection,
    total_paid=total_paid,
    total_balance=total_balance,
    today=today,
    old_balance=old_balance,
    selected_shop=selected_shop,
    from_date=entry_from_date,
    to_date=entry_to_date

)
@app.route("/delete-entry/<group_ids>")
def delete_entry(group_ids):

    conn = get_connection()
    cursor = conn.cursor()

    id_list = group_ids.split(",")

    cursor.executemany(
        "DELETE FROM entries WHERE group_id = %s",
        [(gid,) for gid in id_list]
    )

    conn.commit()
    conn.close()

    return redirect("/entry")
@app.route("/")
def home():

    conn = get_connection()
    cursor = conn.cursor()

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    if not from_date and not to_date:
        today_str = date.today().strftime("%Y-%m-%d")
        from_date = today_str
        to_date = today_str

    where_clause = ""
    params = []

    if from_date and to_date:
        where_clause = """
        WHERE entry_date
        BETWEEN %s AND %s
        """
        params = [from_date, to_date]

    cursor.execute(f"""
        SELECT COALESCE(SUM(total_amount),0) 
        FROM entries
        {where_clause}
    """, params)
    total_collection = cursor.fetchone()[0]
   
    payment_where = ""
    payment_params = []

    if from_date and to_date:
        payment_where = """
    WHERE payment_date BETWEEN %s AND %s
    """
    payment_params = [from_date, to_date]

    cursor.execute(f"""
        SELECT COALESCE(SUM(amount),0)
        FROM payment_entries
            {payment_where}
    """, payment_params)
    total_paid = cursor.fetchone()[0]

    cursor.execute("""
    SELECT
    (
        COALESCE(
            (SELECT SUM(opening_balance)
            FROM payment_entries),
        0)
    )
    +
    COALESCE(
        (SELECT SUM(total_amount)
        FROM entries
        WHERE entry_date <= %s),
    0)
    -
    COALESCE(
        (SELECT SUM(amount)
        FROM payment_entries
        WHERE payment_date <= %s),
    0)
    """, (to_date, to_date))

    total_balance = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM shops")
    total_shops = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM entries
        {where_clause}
    """, params)
    total_entries = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total_collection=total_collection,
        total_paid=total_paid,
        total_balance=total_balance,
        total_shops=total_shops,
        total_products=total_products,
        total_entries=total_entries,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/edit-entry/<group_ids>", methods=["GET", "POST"])
def edit_entry(group_ids):

    conn = get_connection()
    cursor = conn.cursor()

    id_list = group_ids.split(",")

    if request.method == "POST":

        entry_date = request.form["entry_date"]
        shop_id = request.form["shop_id"]

        product_ids = request.form.getlist("product_id[]")
        liters = request.form.getlist("liter[]")
        rates = request.form.getlist("rate[]")
        totals = request.form.getlist("total[]")

        def to_float(v, default=0.0):
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        def to_int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None


        import uuid
        new_group_id = str(uuid.uuid4())

        rows_to_insert = []
        for i in range(len(product_ids)):
            pid = to_int(product_ids[i])
            liter = to_float(liters[i] if i < len(liters) else None)
            rate = to_float(rates[i] if i < len(rates) else None)
            total = to_float(totals[i] if i < len(totals) else None)

            if pid is None or liter == 0:
                continue

            rows_to_insert.append((
                new_group_id,
                entry_date,
                shop_id,
                pid,
                liter,
                rate,
                total,
            ))

        if not rows_to_insert:
            conn.rollback()
            conn.close()
            return "No valid product rows submitted. Please fill in Product, Liter and Rate.", 400

        try:
            cursor.executemany(
                "DELETE FROM entries WHERE group_id = %s",
                [(gid,) for gid in id_list]
            )

            cursor.executemany("""
                INSERT INTO entries
                (group_id, entry_date, shop_id, product_id, liter, rate, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, rows_to_insert)

            conn.commit()
        except Exception as e:
            conn.rollback()
            print("DB ERROR:", e)
            return f"Error updating entry: {e}", 500
        finally:
            conn.close()

        return redirect("/entry")

    placeholders = ",".join("%s" for _ in id_list)

    cursor.execute(f"""
        SELECT *
        FROM entries
        WHERE group_id IN ({placeholders})
    """, id_list)

    rows = cursor.fetchall()

    shop_id = rows[0][3] if rows else None
    old_balance = 0

    if shop_id:
        cursor.execute("""
            SELECT COALESCE(SUM(opening_balance),0),
                        COALESCE(SUM(amount),0)
            FROM payment_entries
            WHERE shop_id=%s
        """, (shop_id,))
        payment_total, amount_total = cursor.fetchone()

        exclude_placeholders = ",".join("%s" for _ in id_list)
        cursor.execute(f"""
            SELECT
                COALESCE(SUM(total_amount),0)
                        FROM entries
            WHERE shop_id=%s AND group_id NOT IN ({exclude_placeholders})
        """, [shop_id] + id_list)
        entries_total = cursor.fetchone()[0]
        old_balance = payment_total + entries_total - amount_total

    cursor.execute("SELECT * FROM shops")
    shops = cursor.fetchall()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_entry.html",
        rows=rows,
        shops=shops,
        products=products,
        group_id=group_ids,
        old_balance=old_balance
    )
@app.route("/edit-shop/<int:id>", methods=["GET","POST"])
def edit_shop(id):

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        shop_name = request.form["shop_name"]

        cursor.execute(
            "UPDATE shops SET shop_name=%s WHERE id=%s",
            (shop_name, id)
        )

        conn.commit()
        conn.close()

        return redirect("/shops")

    cursor.execute(
        "SELECT * FROM shops WHERE id=%s",
        (id,)
    )

    shop = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_shop.html",
        shop=shop
    )
@app.route("/delete-shop/<int:id>")
def delete_shop(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM shops WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/shops")
@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        product_name = request.form["product_name"]
        rate = request.form["rate"]

        cursor.execute("""
            UPDATE products
            SET product_name=%s,
                rate=%s
            WHERE id=%s
        """, (product_name, rate, id))

        conn.commit()
        conn.close()

        return redirect("/products")

    cursor.execute(
        "SELECT * FROM products WHERE id=%s",
        (id,)
    )

    product = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_product.html",
        product=product
    )
@app.route("/delete-product/<int:id>")
def delete_product(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM products WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/products")
@app.route("/shop-report")
def shop_report():

    conn = get_connection()
    cursor = conn.cursor()
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    if not from_date and not to_date:
        today_str = date.today().strftime("%Y-%m-%d")
        from_date = today_str
        to_date = today_str

    where_clause = ""
    params = []

    if from_date and to_date:
        where_clause = " AND e.entry_date BETWEEN %s AND %s "
        params = [from_date, to_date]

    cursor.execute(f"""
SELECT
    s.shop_name,
    COALESCE((
SELECT SUM(opening_balance)-SUM(amount)
FROM payment_entries p
WHERE p.shop_id=s.id
),0)
+
    COALESCE(SUM(e.total_amount),0)
FROM shops s
LEFT JOIN entries e
    ON s.id = e.shop_id
                   {where_clause}
GROUP BY s.id, s.shop_name
ORDER BY s.shop_name
""", params)
    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "shop_report.html",
        reports=reports,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/balance-report")
def balance_report():

    conn = get_connection()
    cursor = conn.cursor()
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    if not from_date and not to_date:
        today_str = date.today().strftime("%Y-%m-%d")
        from_date = today_str
        to_date = today_str

    where_clause = ""
    params = []

    if from_date and to_date:
        where_clause = " AND e.entry_date BETWEEN %s AND %s "
        params = [from_date, to_date]

    cursor.execute(f"""
    SELECT
        s.shop_name,
       COALESCE((
    SELECT SUM(p.opening_balance)-sum(p.amount)
    FROM payment_entries p
    WHERE p.shop_id=s.id
),0)
+
COALESCE(SUM(e.total_amount),0)
                   ) As balance

    FROM shops s
    LEFT JOIN entries e
        ON s.id = e.shop_id
                   {where_clause}
    GROUP BY s.shop_name
    HAVING SUM(e.total_amount) IS NOT NULL
    ORDER BY balance DESC
    """, params)

    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "balance_report.html",
        reports=reports,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/export-excel")
def export_excel():

    conn = get_connection()

    query = """
    SELECT
        e.entry_date,
        s.shop_name,
        p.product_name,
        e.liter,
        e.total_amount
    FROM entries e
    JOIN shops s ON e.shop_id = s.id
    JOIN products p ON e.product_id = p.id
    """

    cursor = conn.cursor()

    cursor.execute(query)

    rows = cursor.fetchall()

    columns = [desc[0] for desc in cursor.description]

    df = pd.DataFrame(rows, columns=columns)

    file_name = "Milk_Report.xlsx"

    df.to_excel(
        file_name,
        index=False
    )

    conn.close()

    return send_file(
        file_name,
        as_attachment=True
    )
@app.route("/product-report")
def product_report():

    conn = get_connection()
    cursor = conn.cursor()
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    if not from_date and not to_date:
        today_str = date.today().strftime("%Y-%m-%d")
        from_date = today_str
        to_date = today_str

    where_clause = ""
    params = []

    if from_date and to_date:
        where_clause = " AND e.entry_date BETWEEN %s AND %s "
        params = [from_date, to_date]

    cursor.execute(f"""
    SELECT
        p.product_name,
        COALESCE(SUM(e.liter),0),
        COALESCE(SUM(e.total_amount),0)
    FROM products p
    LEFT JOIN entries e
        ON p.id = e.product_id
                   {where_clause}
    GROUP BY p.product_name
    ORDER BY p.product_name
    """, params)

    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "product_report.html",
        reports=reports,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/daily-summary")
def daily_summary():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        entry_date,
        SUM(total_amount)
    FROM entries
    GROUP BY entry_date
    ORDER BY entry_date DESC
    """)

    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "daily_summary.html",
        reports=reports
    )
@app.route("/outstanding-report")
def outstanding_report():

    conn = get_connection()
    cursor = conn.cursor()

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    shop_id = request.args.get("shop_id")
    product_id = request.args.get("product_id")
    if not from_date and not to_date:
        today_str = date.today().strftime("%Y-%m-%d")
        from_date = today_str
        to_date = today_str

    query = """
    SELECT
        s.id,
        s.shop_name,
        COALESCE(SUM(e.total_amount),0)
    FROM shops s
    LEFT JOIN entries e
        ON s.id = e.shop_id
    LEFT JOIN products p
        ON e.product_id = p.id
    WHERE 1=1
    """

    params = []

    if from_date:
        query += " AND e.entry_date >= %s "
        params.append(from_date)

    if to_date:
        query += " AND e.entry_date <= %s "
        params.append(to_date)

    if shop_id:
        query += " AND s.id = %s "
        params.append(shop_id)

    if product_id:
        query += " AND p.id = %s "
        params.append(product_id)

    query += """
    GROUP BY s.id, s.shop_name
    ORDER BY s.shop_name
    """

    cursor.execute(query, params)
    raw_reports = cursor.fetchall()

    reports = []
    old_balance = 0

    for sid, sname, total in raw_reports:

        cursor.execute("""
            SELECT 
                       COALESCE(SUM(opening_balance),0),
                       COALESCE(SUM(amount),0)
                       
            FROM payment_entries
            WHERE shop_id=%s
        """, (sid,))
        payment_total ,amount_total= cursor.fetchone()

        balance = payment_total + total - amount_total

        reports.append((sname, total, balance))

        if shop_id and int(shop_id) == sid:
            old_balance = payment_total-amount_total + (total or 0)

    cursor.execute("SELECT * FROM shops")
    shops = cursor.fetchall()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    conn.close()

    return render_template(
        "outstanding_report.html",
        reports=reports,
        shops=shops,
        products=products,
        old_balance=old_balance,
        from_date=from_date,
        to_date=to_date,
        shop_id=shop_id,
        product_id=product_id
    )
@app.route("/export-pdf")
def export_pdf():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        e.entry_date,
        s.shop_name,
        p.product_name,
        e.liter,
        e.total_amount
    FROM entries e
    JOIN shops s ON e.shop_id = s.id
    JOIN products p ON e.product_id = p.id
    ORDER BY e.entry_date DESC
    """)

    rows = cursor.fetchall()

    cursor.execute("""
    SELECT
COALESCE(SUM(total_amount),0)

FROM entries
    """)

    totals = cursor.fetchone()[0]

    conn.close()

    pdf_file = "Milk_Report.pdf"

    doc = SimpleDocTemplate(pdf_file)

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        "<b>MILK & MELT</b>",
        styles["Title"]
    )

    elements.append(title)

    elements.append(
        Paragraph(
            "Milk Collection Report",
            styles["Heading2"]
        )
    )

    elements.append(Spacer(1, 10))

    data = [
        [
            "Date",
            "Shop",
            "Product",
            "Liter",
            "Total",
        ]
    ]

    for row in rows:
        data.append([
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            f"₹ {row[4]}"
        ])

    data.append([
        "",
        "",
        "TOTAL",
        "",
        f"₹ {totals}",
        
    ])

    table = Table(data)

    table.setStyle(TableStyle([

        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),

        ('GRID', (0,0), (-1,-1), 1, colors.black),

        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),

        ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),

        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),

        ('ALIGN', (0,0), (-1,-1), 'CENTER')

    ]))

    elements.append(table)

    doc.build(elements)

    return send_file(
        pdf_file,
        as_attachment=True
    )
@app.route("/clear-data")
def clear_data():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM entries")
    conn.commit()
    conn.close()

    return "Entries Cleared Successfully"   
@app.route("/payment-entry", methods=["GET", "POST"])
def payment_entry():

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        payment_date = request.form["payment_date"]
        shop_id = request.form["shop_id"]
        opening_balance = request.form["opening_balance"] or 0
        amount = request.form["amount"] or 0
        remarks = request.form["remarks"]

        cursor.execute("""
            INSERT INTO payment_entries
            (
                payment_date,
                shop_id,
                opening_balance,
                 amount,
                remarks
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            payment_date,
            shop_id,
            opening_balance,
            amount,
            remarks
        ))

        conn.commit()
        conn.close()

        return redirect("/payment-entry")

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    search = request.args.get("search")
    if not from_date and not to_date and not search:
        today_str = date.today().strftime("%Y-%m-%d")
        from_date = today_str
        to_date = today_str

    query = """
        SELECT
            p.id,
            p.payment_date,
            s.shop_name,
            p.opening_balance,
            p.amount,
            p.remarks
        FROM payment_entries p
        JOIN shops s ON p.shop_id = s.id
        WHERE 1=1
    """
    params = []

    if from_date:
        query += " AND p.payment_date >= %s "
        params.append(from_date)

    if to_date:
        query += " AND p.payment_date <= %s "
        params.append(to_date)

    if search:
        query += " AND s.shop_name LIKE %s "
        params.append(f"%{search}%")

    query += " ORDER BY p.payment_date DESC "

    cursor.execute(query, params)
    payments = cursor.fetchall()

    cursor.execute("SELECT id, shop_name FROM shops ORDER BY shop_name")
    shops = cursor.fetchall()

    # --- live current balance per shop ---
    shop_balances = []
    for sid, sname in shops:
        cursor.execute("""
            SELECT 
                       COALESCE(SUM(opening_balance),0),
                       COALESCE(SUM(amount),0)
            FROM payment_entries
            WHERE shop_id=%s
        """, (sid,))
        payment_total, amount_total = cursor.fetchone()

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount),0)
            FROM entries
            WHERE shop_id=%s
        """, (sid,))
        entries_total = cursor.fetchone()[0]    

        current_balance = (payment_total + entries_total - amount_total)
        shop_balances.append((sname, current_balance))
    # --- end live balance block ---

    today = date.today().strftime("%Y-%m-%d")

    conn.close()

    return render_template(
        "payment_entry.html",
        payments=payments,
        shops=shops,
        shop_balances=shop_balances,
        today=today,
        from_date=from_date,
        to_date=to_date,
        search=search
    )
@app.route("/edit-payment/<int:id>", methods=["GET", "POST"])
def edit_payment(id):

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        payment_date = request.form["payment_date"]
        shop_id = request.form["shop_id"]
        opening_balance = request.form["opening_balance"] or 0
        amount = request.form["amount"] or 0
        remarks = request.form["remarks"]

        cursor.execute("""
            UPDATE payment_entries
            SET payment_date=%s,
                shop_id=%s,
                opening_balance=%s,
                amount=%s,
                remarks=%s
            WHERE id=%s
        """, (
            payment_date,
            shop_id,
            opening_balance,
            amount,
            remarks,
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/payment-entry")

    cursor.execute(
        "SELECT id, payment_date, shop_id, opening_balance, amount, remarks"
        " FROM payment_entries"
        " WHERE id=%s",
        (id,)
    )

    payment = cursor.fetchone()

    cursor.execute("""
        SELECT id, shop_name
        FROM shops
        ORDER BY shop_name
    """)

    shops = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_payment.html",
        payment=payment,
        shops=shops
    )
@app.route("/delete-payment/<int:id>")
def delete_payment(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM payment_entries WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/payment-entry")
@app.route("/export-payment-excel")
def export_payment_excel():

    conn = get_connection()

    query = """
    SELECT
        p.payment_date,
        s.shop_name,
        p.opening_balance,
        p.amount,
        p.remarks
    FROM payment_entries p
    JOIN shops s
    ON p.shop_id = s.id
    ORDER BY payment_date DESC
    """

    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(rows, columns=columns)

    file_name = "Payment_Report.xlsx"

    df.to_excel(
        file_name,
        index=False
    )

    conn.close()

    return send_file(
        file_name,
        as_attachment=True
    )
@app.route("/export-payment-pdf")
def export_payment_pdf():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.payment_date,
            s.shop_name,
            p.opening_balance,
            p.amount,
            p.remarks
        FROM payment_entries p
        JOIN shops s ON p.shop_id = s.id
        ORDER BY p.payment_date DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    pdf_file = "Payment_Report.pdf"

    doc = SimpleDocTemplate(pdf_file, pagesize=landscape(A4))

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        "<b>PAYMENT REPORT</b>",
        styles["Title"]
    )

    elements.append(title)

    elements.append(Spacer(1, 10))

    data = [
        [
            "Payment Date",
            "Shop Name",
            "Opening Balance",
            "Amount",
            "Remarks"
        ]
    ]

    for row in rows:
        data.append([
            str(row[0]),
            str(row[1]),
            f"₹ {row[2]}",
            f"₹ {row[3]}",
            str(row[4])
        ])

    table = Table(data)

    table.setStyle(TableStyle([

        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),

        ('GRID', (0,0), (-1,-1), 1, colors.black),

        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),

        ('ALIGN', (0,0), (-1,-1), 'CENTER')

    ]))

    elements.append(table)

    doc.build(elements)

    return send_file(
        pdf_file,
        as_attachment=True
    )
@app.route("/get-old-balance/<int:shop_id>")
def get_old_balance(shop_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(opening_balance),0),
            COALESCE(SUM(amount),0)
        FROM payment_entries
        WHERE shop_id=%s
    """, (shop_id,))
    payment_total, amount_total = cursor.fetchone()

    cursor.execute("""
        SELECT COALESCE(SUM(total_amount),0)
        FROM entries
        WHERE shop_id=%s
    """, (shop_id,))
    entries_total= cursor.fetchone()[0]

    balance = payment_total + entries_total - amount_total

    conn.close()

    return jsonify({
        "balance": balance
    })
if __name__ == "__main__":
    app.run(debug=True)
