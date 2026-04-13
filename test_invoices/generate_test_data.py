from fpdf import FPDF
import os
import random

def create_invoice(filename, vendor, inv_no, date, amount, items):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Header
    pdf.cell(0, 10, vendor, 0, 1, 'L')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Invoice Number: {inv_no}", 0, 1, 'L')
    pdf.cell(0, 10, f"Date: {date}", 0, 1, 'L')
    pdf.ln(10)
    
    # Table Header
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "Description", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(30, 10, "Price", 1)
    pdf.cell(30, 10, "Total", 1)
    pdf.ln()
    
    # Table Content
    pdf.set_font("Arial", '', 12)
    for item in items:
        pdf.cell(100, 10, item['desc'], 1)
        pdf.cell(30, 10, str(item['qty']), 1)
        pdf.cell(30, 10, f"${item['price']:.2f}", 1)
        pdf.cell(30, 10, f"${item['total']:.2f}", 1)
        pdf.ln()
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(160, 10, "Total Amount:", 0)
    pdf.cell(30, 10, f"${amount:.2f}", 0)
    
    # Create directory if not exists
    dir_name = os.path.dirname(filename)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    pdf.output(filename)

# Generate 3 Sample Invoices
samples = [
    {
        "vendor": "Cloud Services Inc.",
        "inv_no": "INV-2024-001",
        "date": "2024-03-01",
        "items": [{"desc": "Cloud Hosting", "qty": 1, "price": 450.00, "total": 450.00}],
        "amount": 450.00
    },
    {
        "vendor": "Office Supplies Co.",
        "inv_no": "SUP-98765",
        "date": "15/03/2024",
        "items": [
            {"desc": "Paper Reams", "qty": 5, "price": 10.00, "total": 50.00},
            {"desc": "Printer Ink", "qty": 2, "price": 75.00, "total": 150.00}
        ],
        "amount": 200.00
    },
    {
        "vendor": "Global Consulting Group",
        "inv_no": "GCG-2024-03",
        "date": "March 20, 2024",
        "items": [{"desc": "Strategic Review", "qty": 1, "price": 2500.00, "total": 2500.00}],
        "amount": 2500.00
    }
]

for i, s in enumerate(samples):
    create_invoice(f"invoice_{i+1}.pdf", s["vendor"], s["inv_no"], s["date"], s["amount"], s["items"])

print(f"Generated {len(samples)} test invoices.")
