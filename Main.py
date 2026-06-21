from flask import Flask, render_template, request, redirect
from datetime import date
import sqlite3
import pandas as pd

from flask import send_file
from flask import send_file
from flask import Flask, render_template, request, redirect, send_file
from datetime import date
import sqlite3
import pandas as pd
from flask import send_file
from reportlab.platypus import *
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

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
app = Flask(__name__)

# Create table
conn = sqlite3.connect("milk.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS shops(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_name TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    rate REAL NOT NULL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS entries(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT,
    shop_id INTEGER,
    product_id INTEGER,
    liter REAL,
    rate REAL,
    total_amount REAL,
    paid_amount REAL,
    balance_amount REAL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS payment_entries(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_date TEXT,
    person_name TEXT,
    received_amount REAL,
    paid_amount REAL,
    balance_amount REAL,
    remarks TEXT
)
""")
conn = sqlite3.connect("milk.db")
cursor = conn.cursor()

try:
    cursor.execute("""
    ALTER TABLE entries
    ADD COLUMN group_id TEXT
    """)
    conn.commit()
except:
    pass

conn.close()



@app.route("/shops", methods=["GET", "POST"])
def shops():

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    if request.method == "POST":
        

        shop_name = request.form["shop_name"]

        cursor.execute(
            "INSERT INTO shops(shop_name) VALUES(?)",
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

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    if request.method == "POST":

        product_name = request.form["product_name"]
        rate = request.form["rate"]

        cursor.execute(
            "INSERT INTO products(product_name, rate) VALUES(?, ?)",
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

    conn = sqlite3.connect("milk.db")
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
        today = date.today().strftime("%Y-%m-%d")
        import uuid
        group_id = str(uuid.uuid4())
        paid = request.form["paid"]
        balance = request.form["balance"]

        for i in range(len(product_ids)):
            cursor.execute("""
        INSERT INTO entries
(
    group_id,
    entry_date,
    shop_id,
    product_id,
    liter,
    rate,
    total_amount,
    paid_amount,
    balance_amount
)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
    group_id,
    entry_date,
    shop_id,
    product_ids[i],
    liters[i],
    rates[i],
    totals[i],
    paid if i == 0 else 0,
    balance if i == 0 else 0
))

        conn.commit()

        return redirect("/entry")

    # Shop List
    cursor.execute("SELECT * FROM shops")
    shops = cursor.fetchall()

    # Product List
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    # Dashboard Cards
    cursor.execute("""
    SELECT IFNULL(SUM(total_amount),0)
    FROM entries
    """)
    total_collection = cursor.fetchone()[0]

    cursor.execute("""
    SELECT IFNULL(SUM(paid_amount),0)
    FROM entries
    """)
    total_paid = cursor.fetchone()[0]

    cursor.execute("""
    SELECT IFNULL(SUM(balance_amount),0)
    FROM entries
    """)
    total_balance = cursor.fetchone()[0]

    # Entry Report
    cursor.execute("""
SELECT
    e.group_id,
    e.entry_date,
    s.shop_name,
    MIN(e.shop_id) as shop_id,
    GROUP_CONCAT(
        p.product_name || ' - ' ||
        e.liter || 'L - ₹' ||
        e.total_amount,
        '<br>'
    ) as products,
    SUM(e.total_amount) as total,
    MAX(e.paid_amount) as paid,
    MAX(e.balance_amount) as balance
FROM entries e
JOIN shops s ON e.shop_id = s.id
JOIN products p ON e.product_id = p.id
GROUP BY e.group_id
ORDER BY e.entry_date DESC
""")

    entries = cursor.fetchall()
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
    today=today
)
@app.route("/delete-entry/<group_id>")
def delete_entry(group_id):

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM entries
    WHERE group_id = ?
    """, (group_id,))

    conn.commit()
    conn.close()

    return redirect("/entry")
@app.route("/")
def home():

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    where_clause = ""
    params = []

    if from_date and to_date:
        where_clause = """
        WHERE entry_date
        BETWEEN ? AND ?
        """
        params = [from_date, to_date]

    cursor.execute(f"""
        SELECT IFNULL(SUM(total_amount),0)
        FROM entries
        {where_clause}
    """, params)
    total_collection = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT IFNULL(SUM(paid_amount),0)
        FROM entries
        {where_clause}
    """, params)
    total_paid = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT IFNULL(SUM(balance_amount),0)
        FROM entries
        {where_clause}
    """, params)
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
@app.route("/edit-entry/<group_id>", methods=["GET", "POST"])
def edit_entry(group_id):

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    if request.method == "POST":

        entry_date = request.form["entry_date"]
        shop_id = request.form["shop_id"]

        product_ids = request.form.getlist("product_id[]")
        liters = request.form.getlist("liter[]")
        rates = request.form.getlist("rate[]")
        totals = request.form.getlist("total[]")

        paid = request.form["paid"]
        balance = request.form["balance"]

        cursor.execute(
            "DELETE FROM entries WHERE group_id=?",
            (group_id,)
        )

        for i in range(len(product_ids)):
            cursor.execute("""
            INSERT INTO entries
            (
                group_id,
                entry_date,
                shop_id,
                product_id,
                liter,
                rate,
                total_amount,
                paid_amount,
                balance_amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group_id,
                entry_date,
                shop_id,
                product_ids[i],
                liters[i],
                rates[i],
                totals[i],
                paid if i == 0 else 0,
                balance if i == 0 else 0
            ))

        conn.commit()
        conn.close()

        return redirect("/entry")

    cursor.execute("""
    SELECT *
    FROM entries
    WHERE group_id = ?
    """, (group_id,))

    rows = cursor.fetchall()
    print("ROWS =", rows)

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
        group_id=group_id
    )
@app.route("/edit-shop/<int:id>", methods=["GET","POST"])
def edit_shop(id):

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    if request.method == "POST":

        shop_name = request.form["shop_name"]

        cursor.execute(
            "UPDATE shops SET shop_name=? WHERE id=?",
            (shop_name, id)
        )

        conn.commit()
        conn.close()

        return redirect("/shops")

    cursor.execute(
        "SELECT * FROM shops WHERE id=?",
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

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM shops WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/shops")
@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    if request.method == "POST":

        product_name = request.form["product_name"]
        rate = request.form["rate"]

        cursor.execute("""
            UPDATE products
            SET product_name=?,
                rate=?
            WHERE id=?
        """, (product_name, rate, id))

        conn.commit()
        conn.close()

        return redirect("/products")

    cursor.execute(
        "SELECT * FROM products WHERE id=?",
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

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM products WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/products")
@app.route("/shop-report")
def shop_report():

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        s.shop_name,
        IFNULL(SUM(e.total_amount),0),
        IFNULL(SUM(e.paid_amount),0),
        IFNULL(SUM(e.balance_amount),0)
    FROM shops s
    LEFT JOIN entries e
        ON s.id = e.shop_id
    GROUP BY s.shop_name
    ORDER BY s.shop_name
    """)

    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "shop_report.html",
        reports=reports
    )
@app.route("/balance-report")
def balance_report():

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        s.shop_name,
        IFNULL(SUM(e.balance_amount),0) AS balance
    FROM shops s
    LEFT JOIN entries e
        ON s.id = e.shop_id
    GROUP BY s.shop_name
    HAVING balance > 0
    ORDER BY balance DESC
    """)

    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "balance_report.html",
        reports=reports
    )
@app.route("/export-excel")
def export_excel():

    conn = sqlite3.connect("milk.db")

    query = """
    SELECT
        e.entry_date,
        s.shop_name,
        p.product_name,
        e.liter,
        e.total_amount,
        e.paid_amount,
        e.balance_amount
    FROM entries e
    JOIN shops s ON e.shop_id = s.id
    JOIN products p ON e.product_id = p.id
    """

    df = pd.read_sql_query(query, conn)

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

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        p.product_name,
        IFNULL(SUM(e.liter),0),
        IFNULL(SUM(e.total_amount),0)
    FROM products p
    LEFT JOIN entries e
        ON p.id = e.product_id
    GROUP BY p.product_name
    ORDER BY p.product_name
    """)

    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "product_report.html",
        reports=reports
    )
@app.route("/daily-summary")
def daily_summary():

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        entry_date,
        SUM(total_amount),
        SUM(paid_amount),
        SUM(balance_amount)
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

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    shop_id = request.args.get("shop_id")
    product_id = request.args.get("product_id")

    query = """
    SELECT
        s.shop_name,
        IFNULL(SUM(e.total_amount),0),
        IFNULL(SUM(e.paid_amount),0),
        IFNULL(SUM(e.balance_amount),0)
    FROM shops s
    LEFT JOIN entries e
        ON s.id = e.shop_id
    LEFT JOIN products p
        ON e.product_id = p.id
    WHERE 1=1
    """

    params = []

    if from_date:
        query += " AND e.entry_date >= ? "
        params.append(from_date)

    if to_date:
        query += " AND e.entry_date <= ? "
        params.append(to_date)

    if shop_id:
        query += " AND s.id = ? "
        params.append(shop_id)

    if product_id:
        query += " AND p.id = ? "
        params.append(product_id)

    query += """
    GROUP BY s.shop_name
    ORDER BY s.shop_name
    """

    cursor.execute(query, params)
    reports = cursor.fetchall()

    cursor.execute("SELECT * FROM shops")
    shops = cursor.fetchall()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    conn.close()

    return render_template(
        "outstanding_report.html",
        reports=reports,
        shops=shops,
        products=products
    )
@app.route("/export-pdf")
def export_pdf():

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        e.entry_date,
        s.shop_name,
        p.product_name,
        e.liter,
        e.total_amount,
        e.paid_amount,
        e.balance_amount
    FROM entries e
    JOIN shops s ON e.shop_id = s.id
    JOIN products p ON e.product_id = p.id
    ORDER BY e.entry_date DESC
    """)

    rows = cursor.fetchall()

    cursor.execute("""
    SELECT
        IFNULL(SUM(total_amount),0),
        IFNULL(SUM(paid_amount),0),
        IFNULL(SUM(balance_amount),0)
    FROM entries
    """)

    totals = cursor.fetchone()

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
            "Paid",
            "Balance"
        ]
    ]

    for row in rows:
        data.append([
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            f"₹ {row[4]}",
            f"₹ {row[5]}",
            f"₹ {row[6]}"
        ])

    data.append([
        "",
        "",
        "TOTAL",
        "",
        f"₹ {totals[0]}",
        f"₹ {totals[1]}",
        f"₹ {totals[2]}"
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

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM entries")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='entries'")

    conn.commit()
    conn.close()

    return "Entries Cleared Successfully"   
@app.route("/payment-entry", methods=["GET", "POST"])
def payment_entry():

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    if request.method == "POST":

        payment_date = request.form["payment_date"] 
        person_name = request.form["person_name"] 
        received_amount = float( request.form.get("received_amount", 0) or 0 ) 
        paid_amount = float( request.form.get("paid_amount", 0) or 0 ) 
        balance_amount = ( received_amount - paid_amount ) 
        remarks = request.form["remarks"]
        cursor.execute("""
            INSERT INTO payment_entries
            (
                payment_date,
                person_name,
                received_amount,
                paid_amount,
                balance_amount,
                remarks
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            payment_date,
            person_name,
            received_amount,
            paid_amount,
            balance_amount,
            remarks
        ))

        conn.commit()

        return redirect("/payment-entry")

    from_date = request.args.get("from_date") 
    to_date = request.args.get("to_date") 
    search = request.args.get("search") 
    query = """ SELECT * FROM payment_entries WHERE 1=1 """ 
    params = [] 
    if from_date: 
        query += """ 
        AND payment_date >= ? 
        """ 
        params.append(from_date) 
    if to_date: 
        query += """ AND payment_date <= ? """ 
        params.append(to_date) 
    if search: 
        query += """ AND person_name LIKE ? """ 
        params.append( f"%{search}%" ) 
    query += """ ORDER BY payment_date DESC """ 
    cursor.execute( query, params ) 
    payments = cursor.fetchall() 
    today = date.today().strftime( "%Y-%m-%d" ) 
    conn.close() 
    return render_template( "payment_entry.html", payments=payments, today=today, from_date=from_date, to_date=to_date, search=search )
@app.route("/edit-payment/<int:id>", methods=["GET", "POST"])
def edit_payment(id):

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    if request.method == "POST":

        payment_date = request.form["payment_date"]
        person_name = request.form["person_name"]
        received_amount = request.form["received_amount"]
        paid_amount = request.form["paid_amount"]
        balance_amount = request.form["balance_amount"]
        remarks = request.form["remarks"]

        cursor.execute("""
            UPDATE payment_entries
            SET payment_date=?,
                person_name=?,
                received_amount=?,
                paid_amount=?,
                balance_amount=?,
                remarks=?
            WHERE id=?
        """, (
            payment_date,
            person_name,
            received_amount,
            paid_amount,
            balance_amount,
            remarks,
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/payment-entry")

    cursor.execute(
        "SELECT * FROM payment_entries WHERE id=?",
        (id,)
    )

    payment = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_payment.html",
        payment=payment
    )
@app.route("/delete-payment/<int:id>")
def delete_payment(id):

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM payment_entries WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/payment-entry")
@app.route("/export-payment-excel")
def export_payment_excel():

    conn = sqlite3.connect("milk.db")

    query = """
    SELECT
        payment_date,
        person_name,
        received_amount,
        paid_amount,
        balance_amount,
        remarks
    FROM payment_entries
    ORDER BY payment_date DESC
    """

    df = pd.read_sql_query(query, conn)

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

    conn = sqlite3.connect("milk.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        payment_date,
        person_name,
        received_amount,
        paid_amount,
        balance_amount,
        remarks
    FROM payment_entries
    ORDER BY payment_date DESC
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
            "Person Name",
            "Received Amount",
            "Paid Amount",
            "Balance Amount",
            "Remarks"
        ]
    ]

    for row in rows:
        data.append([
            str(row[0]),
            str(row[1]),
            f"₹ {row[2]}",
            f"₹ {row[3]}",
            f"₹ {row[4]}",
            str(row[5])
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
if __name__ == "__main__":
    app.run(debug=True)
