from app.services.extraction_service import AIService, ValidationService


def test_heuristic_extraction_handles_sliced_invoice_layout():
    sample_text = """
    Sliced Invoices
    Invoice

    From:
    DEMO - Sliced Invoices
    Suite 5A-1204
    123 Somewhere Street
    Your City AZ 12345
    admin@slicedinvoices.com

    To:
    Test Business
    123 Somewhere St
    Melbourne, VIC 3000
    test@test.com

    Invoice Number INV-3337
    Order Number 12345
    Invoice Date January 25, 2016
    Due Date January 31, 2016
    Total Due $93.50

    Hrs/Qty Service Rate/Price Adjust Sub Total
    1.00 Web Design
    This is a sample description...
    $85.00 0.00% $85.00

    Sub Total $85.00
    Tax $8.50
    Total $93.50
    """

    payload = AIService._heuristic_extraction(
        {
            "text": sample_text,
            "lines": [line.strip() for line in sample_text.splitlines() if line.strip()],
            "tables": [
                [
                    ["Hrs/Qty", "Service", "Rate/Price", "Adjust", "Sub Total"],
                    ["1.00", "Web Design", "$85.00", "0.00%", "$85.00"],
                ]
            ],
        }
    )
    result = ValidationService.validate_invoice(payload)
    structured = result["normalized_data"]

    assert structured["vendor_name"] == "DEMO - Sliced Invoices"
    assert structured["invoice_number"] == "INV-3337"
    assert structured["invoice_date"] == "2016-01-25"
    assert structured["currency"] == "AUD"
    assert structured["total_amount"] == 93.50
    assert structured["tax_amount"] == 8.50
    assert structured["line_items"][0]["description"] == "Web Design"
    assert structured["line_items"][0]["line_total"] == 85.00
