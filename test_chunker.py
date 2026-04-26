import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from graph.agents.ingestion_agent import Chunker

# ── Sample invoice state ──────────────────────────────────────────────────────
state = {
    'job_id': 'TEST-001',
    'invoice_path': '',
    'error': None,
    'raw_invoice_text': (
        'BLUE LOGISTIC VIETNAM\nNO 89--98 HAM MG STREET\nNGUYEN THAI BINH , DISTRICT 3\n'
        'HO CHI MAN CITY\nVIETNAM\nTEL:0084-8-4329XXX67 FAX:0084-8-4329XXX7\n'
        'Payment_Info DEBIT NOTE COPY\nBill of Lading: SGN24XXX25\nVNEX2134XXX\n'
        'Customer: 00015XXX42/001\nyour Ref:: NAXXX\n'
        'Date: 03-Dec-2024 Payment Ref/Local inv no : C24TAA0XXX3406\n'
        'Payable to : Invoice To\nINFOSYS VIETNAM INFOSYS VIETNAM\n'
        's6 83 examu ham nagi s6 83 examu ham nagi\nquhan quhan\n'
        'TEL:0084-8-87865457 FAX0084-8--897767232: TEL:0084-8-8786XXX7 FAX0084-8--8977XXX2:\n'
        'VAT NO.:03042XXX43\nContract_Info\nInvoiced By:XXXX\n'
        'Voyage: 1TUB2XXXA Vessel: ROOSEVELT Call Date: 28 NOV 2024\n'
        'Place of Receipt: HO CHII MINH CITY Discharge Port: RIO DE JANEIRO\n'
        'Load Port: VUNG TAU Place of Delivery: -\n'
        'Commodity Code Description Package Qty\n'
        '030XXX Frozen fillets of catfish (Pan 40RH 1\n'
        'Container Number(s): TCLUXXXX377\n'
        'Size/Type Charge Description Tax Based on Rate Currency Amount Amount in VND\n'
        'C Cuoc van tai bien, gom cac phu phi 1 USD 5000 127,495,000.00\n'
        '40RH C Phi xep hang tai noi xep hang F1 1UNI 6,050,000.00 VND 6,050,000.00 6,050,000.00\n'
        '40RH C Phi an ninh tau va cang 1UNI 14.00 USD 14.00 356,986.00\n'
        '40RH C Phi chi F1 1UNI 230,000.00 VND 230,000.00 230,000.00\n'
        'Rate of Exchange Currency Change Totals\n'
        'VND 6,280,000.00\n1USD= 25,499.00000VND\nUSD 5014.00\n'
        'Total Excluding tax 134,131,986.00\n'
        'VAT applied as indicated on charges\n'
        'F1 C Freight tax 6,280,000.00 @5.26% 330526 VND 12.89 USD Total VAT 5.26 330,526.00\n'
        'Total VAT 330,526.00\nTotal Including Tax 134,462,512.00'
    ),
    'tables': [{'page': 1, 'table_index': 0, 'rows': [['BLUE LOGISTIC VIETNAM\nNO 89--98 HAM MG STREET\nNGUYEN THAI BINH , DISTRICT 3\nHO CHI MAN CITY\nVIETNAM\nTEL:0084-8-4329XXX67 FAX:0084-8-4329XXX7', None, None], ['Payment_Info\nBill of Lading: SGN24XXX25\nCustomer: 00015XXX42/001\nyour Ref:: NAXXX', 'DEBIT NOTE COPY\nVNEX2134XXX\nDate: 03-Dec-2024 Payment Ref/Local inv no : C24TAA0XXX3406', None], ['Payable to :\nINFOSYS VIETNAM\ns6 83 examu ham nagi\nquhan\nTEL:0084-8-87865457 FAX0084-8--897767232:', 'Invoice To\nINFOSYS VIETNAM\ns6 83 examu ham nagi\nquhan\nTEL:0084-8-8786XXX7 FAX0084-8--8977XXX2:', None], ['VAT NO.:03042XXX43\nContract_Info\nInvoiced By:XXXX\nVoyage: 1TUB2XXXA Vessel: ROOSEVELT\nPlace of Receipt: HO CHII MINH CITY\nLoad Port: VUNG TAU', 'Call Date: 28 NOV 2024\nDischarge Port: RIO DE JANEIRO\nPlace of Delivery: -', None], ['Commodity Code Description Package Qty', None, None], ['030XXX Frozen fillets of catfish (Pan 40RH 1', None, None], ['Container Number(s): TCLUXXXX377', None, None], ['Size/Type Charge Description Tax Based on Rate Currency Amount Amount in VND', None, None], ['C Cước vận tải biển, gồm các phụ phí 1 USD 5000', None, '127,495,000.00'], ['40RH C Phí xếp hàng tại nơi xếp hàng F1 1UNI 6,050,000.00 VND 6,050,000.00\n40RH C Phí an ninh tàu và cảng 1UNI 14.00 USD 14.00\n40RH C Phí chỉ F1 1UNI 230,000.00 VND 230,000.00', None, '6,050,000.00\n356,986.00\n230,000.00'], ['Rate of Exchange Currency Change Totals', None, ''], ['VND 6,280,000.00\n1USD= 25,499.00000VND\nUSD 5014.00', None, ''], ['Total Excluding tax134,131,986.00\nVAT applied as indicated on charges\nF1 C Freight tax 6,280,000.00 @5.26% 330526 VND 12.89 USD Total VAT 5.26 330,526.00\nTotal VAT 330,526.00', None, None], ['Total Including Tax 134,462,512.00', None, None]], 'row_count': 14, 'col_count': 3}],
    'metadata': {
        'sender': 'accounts@oceanfreight.in',
        'subject': 'Invoice for Container Transport - PO-1006',
        'received_timestamp': '2025-06-01T09:00:00Z',
        'language': 'en',
        'attachments': ['INV_EN_006_malformed.pdf']
    }
}

# ── Run Chunker ───────────────────────────────────────────────────────────────
print("\nInitialising Chunker...")
chunker = Chunker(state)

print("Running invoice_data_chunker()...")
chunks = chunker.invoice_data_chunker()

# ── Display Results ───────────────────────────────────────────────────────────
if not chunks:
    print("\n[RESULT] No chunks produced — raw_invoice_text was empty/None.")

else:
    print(chunks)
