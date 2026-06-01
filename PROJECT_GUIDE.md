# Vaishnavi Consultant Workstation — Project Guide

> **Business**: Consultant (Service Provider) | **GST**: None | **Domain**: EPF / ESIC / Professional Fee collections
> **Date**: 2026-06-01 | **Status**: Planning Phase

---

## 1. Understanding Your Business Domain

Your clients pay you in three components per billing cycle:

| Component | What it is |
|---|---|
| **EPF** | Employee Provident Fund contribution (govt statutory) |
| **ESIC** | Employee State Insurance Corporation contribution (govt statutory) |
| **Professional Fee** | Your consultancy charge for managing the above |

**Key accounting scenarios:**
- **Exact Payment** → Receipt matches invoice → ledger clears
- **Excess Payment** → Client paid more than invoice → tracked in Excess Payment Ledger (liability / advance credit)
- **Short Payment** → Client paid less than invoice → tracked in Short Payment Ledger (outstanding receivable)

---

## 2. Recommended Tech Stack

### Final Recommendation: **Streamlit + FastAPI + MongoDB**

```
┌─────────────────────────────────┐
│  Frontend: Streamlit (Python)   │  ← Tally-like desktop feel, no HTML needed
│  Pages: multi-page app          │
└──────────────┬──────────────────┘
               │ HTTP (REST)
┌──────────────▼──────────────────┐
│  Backend: FastAPI (Python)      │  ← Business logic, validations
│  Pydantic models + routers      │
└──────────────┬──────────────────┘
               │ pymongo / motor
┌──────────────▼──────────────────┐
│  Dev:  MongoDB Compass (local)  │
│  Prod: MongoDB Atlas (cloud)    │
└─────────────────────────────────┘
```

**Why Streamlit over PyQt5?**
- Pure Python, no UI toolkit knowledge needed
- Built-in tables, charts, file uploaders
- Easy to run on any machine (`streamlit run app.py`)
- Can be deployed to Streamlit Cloud / VPS later

**Why FastAPI over Flask?**
- Auto-generates API docs (`/docs`)
- Async-ready for bank statement parsing
- Pydantic validation built-in

---

## 3. System Architecture — Folder Structure

```
vaishnavi_tally/
│
├── backend/
│   ├── main.py                  # FastAPI app entry
│   ├── database.py              # MongoDB connection (env-based dev/prod)
│   ├── models/
│   │   ├── client.py            # Client / Sundry Debtor model
│   │   ├── voucher.py           # Receipt, Payment, Journal
│   │   ├── ledger.py            # Bank, Cash, individual ledgers
│   │   └── invoice.py           # Invoice / billing model
│   ├── routers/
│   │   ├── clients.py
│   │   ├── vouchers.py
│   │   ├── ledgers.py
│   │   ├── reports.py
│   │   └── bank_import.py
│   └── services/
│       ├── trial_balance.py
│       ├── profit_loss.py
│       ├── short_excess.py
│       └── statement_parser.py  # Bank statement CSV/PDF parser
│
├── frontend/
│   ├── app.py                   # Streamlit main (navigation)
│   └── pages/
│       ├── 1_Dashboard.py
│       ├── 2_Clients.py
│       ├── 3_Receipts.py
│       ├── 4_Payments.py
│       ├── 5_Journal.py
│       ├── 6_Ledgers.py
│       ├── 7_Reports.py
│       └── 8_Bank_Import.py
│
├── data/
│   └── sample_bank_statements/  # For testing import
│
├── .env                         # DB URI, secrets
├── requirements.txt
└── README.md
```

---

## 4. MongoDB Collections Design

### `clients` (Sundry Debtors + all parties)
```json
{
  "_id": "ObjectId",
  "name": "ABC Pvt Ltd",
  "type": "sundry_debtor",        // sundry_debtor | sundry_creditor | bank | cash
  "contact_person": "Ramesh Kumar",
  "phone": "9876543210",
  "email": "ramesh@abc.com",
  "address": "Mumbai, Maharashtra",
  "opening_balance": 0,
  "opening_balance_type": "dr",   // dr | cr
  "epf_account_no": "MH/BAN/0012345",
  "esic_account_no": "31000123456780000",
  "created_at": "ISODate",
  "is_active": true
}
```

### `invoices`
```json
{
  "_id": "ObjectId",
  "invoice_no": "INV-2025-001",
  "client_id": "ObjectId",
  "billing_month": "2025-05",
  "epf_amount": 15000,
  "esic_amount": 5500,
  "professional_fee": 2000,
  "total_amount": 22500,
  "paid_amount": 0,
  "balance_due": 22500,
  "status": "unpaid",             // unpaid | partial | paid | excess
  "due_date": "ISODate",
  "created_at": "ISODate"
}
```

### `vouchers`
```json
{
  "_id": "ObjectId",
  "voucher_no": "RCP-2025-001",
  "voucher_type": "receipt",      // receipt | payment | journal | contra
  "date": "ISODate",
  "narration": "EPF+ESIC+Fee from ABC Pvt Ltd for May 2025",
  "entries": [
    { "ledger_id": "ObjectId", "ledger_name": "Bank - SBI", "debit": 22500, "credit": 0 },
    { "ledger_id": "ObjectId", "ledger_name": "ABC Pvt Ltd", "debit": 0, "credit": 22500 }
  ],
  "invoice_id": "ObjectId",       // linked invoice (optional)
  "client_id": "ObjectId",
  "payment_mode": "bank_transfer", // bank_transfer | cash | cheque | upi
  "reference_no": "UTR123456789",
  "created_at": "ISODate",
  "created_by": "admin"
}
```

### `ledgers`
```json
{
  "_id": "ObjectId",
  "name": "SBI Current Account",
  "group": "bank",                // bank | cash | sundry_debtor | sundry_creditor | income | expense
  "account_no": "XXXXXXXXXX1234",
  "opening_balance": 125000,
  "opening_balance_type": "dr",
  "client_id": "ObjectId",        // only for client-linked ledgers
  "created_at": "ISODate"
}
```

### `short_excess_tracker`
```json
{
  "_id": "ObjectId",
  "client_id": "ObjectId",
  "invoice_id": "ObjectId",
  "voucher_id": "ObjectId",
  "billing_month": "2025-05",
  "invoiced_amount": 22500,
  "received_amount": 20000,
  "difference": -2500,
  "type": "short",                // short | excess
  "status": "pending",            // pending | adjusted | refunded
  "remarks": "Short by Rs 2500 — client informed",
  "date": "ISODate"
}
```

### `bank_statement_uploads`
```json
{
  "_id": "ObjectId",
  "bank_name": "SBI",
  "ledger_id": "ObjectId",
  "file_name": "SBI_May2025.csv",
  "upload_date": "ISODate",
  "from_date": "ISODate",
  "to_date": "ISODate",
  "total_transactions": 45,
  "matched": 38,
  "unmatched": 7,
  "transactions": [
    {
      "date": "ISODate",
      "description": "NEFT/CR/ABC PVT LTD",
      "debit": 0,
      "credit": 22500,
      "balance": 147500,
      "matched_voucher_id": "ObjectId",
      "match_status": "matched"   // matched | unmatched | ignored
    }
  ]
}
```

---

## 5. All Modules — User Flow

### 5.1 Client Management (Sundry Debtor)

```
[Clients Page]
  ├── Add New Client
  │     → Name, Contact, EPF No, ESIC No, Address
  │     → Opening Balance (if migrating from old system)
  │     → Save → auto-creates linked ledger in Ledgers collection
  │
  ├── Client List (searchable, filterable)
  │     → Click client → Client Card
  │           ├── View all invoices
  │           ├── View individual ledger
  │           ├── View short/excess history
  │           └── Print ledger statement
  │
  └── Edit / Deactivate Client
```

### 5.2 Invoice Creation

```
[Invoice Page]
  ├── New Invoice
  │     → Select Client
  │     → Select Billing Month
  │     → Enter: EPF Amount | ESIC Amount | Professional Fee
  │     → Auto-calculate Total
  │     → Save → status: "unpaid"
  │
  └── Invoice List
        → Filter by: Client | Month | Status (unpaid/partial/paid)
        → Print Invoice (PDF)
```

### 5.3 Receipt Voucher

```
[Receipts Page]
  ├── New Receipt
  │     → Date, Receipt No (auto)
  │     → Select Client
  │     → Select/Link Invoice (shows pending amount)
  │     → Amount Received
  │     → Payment Mode: Bank / Cash / UPI / Cheque
  │     → Reference No (UTR / Cheque No)
  │     → Narration
  │     → System auto-calculates:
  │           If received == invoiced  → mark invoice PAID
  │           If received < invoiced   → mark PARTIAL → create SHORT entry
  │           If received > invoiced   → mark PAID    → create EXCESS entry
  │     → Double-entry posted:
  │           DR: Bank/Cash Ledger
  │           CR: Client Ledger
  │
  └── Receipt List (searchable, printable)
```

### 5.4 Payment Voucher

```
[Payments Page]
  ├── New Payment
  │     → Date, Voucher No (auto)
  │     → Pay To (select ledger: vendor / expense)
  │     → Amount, Payment Mode, Reference
  │     → Purpose: EPF Deposit | ESIC Deposit | Office Expense | Other
  │     → Double-entry:
  │           DR: Expense / EPF Payable / ESIC Payable Ledger
  │           CR: Bank / Cash Ledger
  │
  └── Payment List
```

### 5.5 Journal Voucher

```
[Journal Page]
  ├── New Journal Entry
  │     → Multi-row debit/credit entry (like Tally)
  │     → Validation: Total DR must equal Total CR
  │     → Common uses:
  │           - Adjust short/excess payments
  │           - Month-end provisions
  │           - Opening balance corrections
  │
  └── Journal List
```

### 5.6 Short Payment Ledger

```
[Short Payment Page]
  ├── Auto-populated from Receipt entries
  ├── Columns: Client | Month | Invoiced | Received | Short Amount | Status
  ├── Actions per row:
  │     → Mark as Recovered (link to new receipt)
  │     → Write Off (journal entry)
  │     → Add Remark
  │
  └── Summary: Total short outstanding (client-wise / month-wise)
```

### 5.7 Excess Payment Ledger

```
[Excess Payment Page]
  ├── Auto-populated from Receipt entries
  ├── Columns: Client | Month | Invoiced | Received | Excess Amount | Status
  ├── Actions per row:
  │     → Adjust against next invoice (auto-link)
  │     → Refund (create payment voucher)
  │     → Add Remark
  │
  └── Summary: Total excess held (client-wise)
```

### 5.8 Bank Ledger

```
[Bank Ledger]
  ├── Select Bank Account
  ├── Date range filter
  ├── Running balance view (like passbook)
  ├── Each row: Date | Particulars | DR | CR | Balance
  ├── Reconciliation status indicator (matched / unmatched with bank statement)
  └── Print / Export to Excel
```

### 5.9 Cash Ledger

```
[Cash Ledger]
  ├── Same as Bank Ledger but for Cash
  ├── Daily closing balance visible
  └── Cash denominations entry (optional feature)
```

### 5.10 Individual Client Ledger Viewer

```
[Client Ledger]
  ├── Select Client → view all transactions
  ├── Columns: Date | Voucher No | Particulars | DR | CR | Balance
  ├── Running balance per client
  ├── Outstanding balance shown at top
  └── Print Button → generates PDF statement
        → Header: Your firm name, client name, period
        → Footer: "This is a computer-generated statement"
```

### 5.11 Trial Balance

```
[Trial Balance]
  ├── As-on-date selector
  ├── All ledgers with:
  │     Opening Balance | Total DR | Total CR | Closing Balance
  ├── Grouped by: Bank | Cash | Sundry Debtors | Income | Expenses
  ├── Must balance: Total DR = Total CR
  └── Export to Excel / Print
```

### 5.12 Profit & Loss Statement

```
[P&L Statement]
  ├── Period: From Date → To Date
  │
  ├── INCOME SIDE:
  │     Professional Fee Received  ₹ X,XX,XXX
  │     (EPF/ESIC are pass-through — not your income)
  │
  ├── EXPENSE SIDE:
  │     Office Expenses             ₹ XX,XXX
  │     Staff Salaries              ₹ XX,XXX
  │     Bank Charges                ₹ X,XXX
  │     Miscellaneous               ₹ X,XXX
  │
  └── NET PROFIT / LOSS            ₹ X,XX,XXX
```

### 5.13 Bank Statement Import

```
[Bank Import Page]
  ├── Select Bank (SBI / HDFC / ICICI / Axis / etc.)
  ├── Select Ledger to reconcile against
  ├── Upload File: CSV or PDF
  │
  ├── Auto-parsing:
  │     → CSV: pandas read_csv with bank-specific column mapping
  │     → PDF: pdfplumber extracts table rows
  │
  ├── Preview parsed transactions (editable)
  │
  ├── Smart Matching Engine:
  │     → Match by amount + date (±2 days tolerance)
  │     → Match by client name in description
  │     → Fuzzy match on narration
  │
  ├── Review unmatched entries:
  │     → Manually link to voucher
  │     → Create new voucher from bank entry
  │     → Mark as "ignore" (internal transfer, etc.)
  │
  └── Reconciliation Report:
        Matched: 38 | Unmatched: 7 | Ignored: 2
```

---

## 6. Additional Features I Suggest (Enhancements)

### 6.1 Dashboard (Home Screen)
- **Total Outstanding** from all clients (like Tally's company dashboard)
- **This Month Collections** vs **Last Month**
- **Short Payment Alert** — clients with pending short payments
- **Recent Transactions** (last 10 vouchers)
- **Cash in Hand** and **Bank Balance** at a glance
- Bar chart: Monthly Professional Fee collection trend

### 6.2 Invoice / Receipt Numbering
- Auto-increment: `RCP-2025-001`, `PAY-2025-001`, `JRN-2025-001`
- Financial year aware (resets on April 1 each year)

### 6.3 Monthly Billing Bulk Generator
- Select multiple clients → generate invoices for all in one click for a billing month
- Great for month-end routine

### 6.4 WhatsApp / Email Receipt Sharing
- After saving a receipt, generate PDF and share via:
  - Email (smtplib / SendGrid)
  - WhatsApp (Twilio API or wa.me link)

### 6.5 Reminder System
- Auto-flag clients who haven't paid by due date
- Show overdue badge on client list
- Optional: send reminder message

### 6.6 Multi-User Support (Future)
- Admin + Accountant roles
- Audit log: who entered what and when
- JWT-based login

### 6.7 Financial Year Selector
- Switch between FY 2024-25 / 2025-26
- All reports respect selected financial year

### 6.8 Backup & Restore
- One-click export of all MongoDB data to JSON/Excel
- Restore from backup file
- Auto-backup to Google Drive (optional)

### 6.9 Cheque Register
- Track post-dated cheques received
- Alert when a cheque is due for deposit
- Mark as deposited / bounced

### 6.10 Outstanding Statement (Age-wise)
```
Client         | 0-30 days | 31-60 days | 61-90 days | 90+ days | Total
ABC Pvt Ltd    |  22,500   |      0     |   5,000    |     0    | 27,500
XYZ Traders    |       0   |  18,000    |       0    |  12,000  | 30,000
```
This is very powerful for follow-up.

### 6.11 Cash Flow Statement
- Monthly inflow (receipts) vs outflow (payments)
- Net cash position per month

---

## 7. Bank Statement Import — Scraping Recommendation

### Recommendation: DO NOT screen-scrape bank websites

**Why not:**
- Banks use OTPs, CAPTCHAs, and 2FA → unreliable automation
- Against most banks' Terms of Service
- Risk of account flagging / blocking
- Maintenance nightmare when bank UI changes

### Recommended Approach: File-based Import

| Method | Banks | Library |
|---|---|---|
| CSV Upload | All banks (download from net banking) | `pandas` |
| Excel Upload | HDFC, Axis, Kotak | `openpyxl` |
| PDF Upload | SBI, Bank of Baroda, PNB | `pdfplumber`, `camelot-py` |

**Bank CSV column mappings to implement:**

| Bank | Date Col | Description Col | Credit Col | Debit Col |
|---|---|---|---|---|
| SBI | `Txn Date` | `Description` | `Credit` | `Debit` |
| HDFC | `Date` | `Narration` | `Deposit Amt (INR)` | `Withdrawal Amt (INR)` |
| ICICI | `Transaction Date` | `Transaction Remarks` | `CR` | `DR` |
| Axis | `Tran Date` | `PARTICULARS` | `CR` | `DR` |

**Future-ready option:** RBI Account Aggregator (AA) framework allows licensed fetch of bank data via API (Finvu, OneMoney). This is the legal, official route for automated bank data.

---

## 8. Dummy Data — 10 Clients

```python
clients = [
    {
        "name": "Sunrise Garments Pvt Ltd",
        "contact_person": "Rajesh Sharma",
        "phone": "9823456781",
        "epf_account_no": "MH/BAN/0045231",
        "esic_account_no": "31000456780000",
        "monthly_epf": 18500, "monthly_esic": 6800, "professional_fee": 2500,
        "opening_balance": 0
    },
    {
        "name": "Krishna Engineering Works",
        "contact_person": "Suresh Patil",
        "phone": "9712345678",
        "epf_account_no": "MH/PUN/0023441",
        "esic_account_no": "31000234560000",
        "monthly_epf": 12000, "monthly_esic": 4200, "professional_fee": 2000,
        "opening_balance": 2000  # short from previous month
    },
    {
        "name": "Mehta Brothers Trading Co",
        "contact_person": "Amit Mehta",
        "phone": "9634512378",
        "epf_account_no": "MH/MUM/0078923",
        "esic_account_no": "31000789230000",
        "monthly_epf": 32000, "monthly_esic": 11200, "professional_fee": 3500,
        "opening_balance": 0
    },
    {
        "name": "Patel Textiles",
        "contact_person": "Haresh Patel",
        "phone": "9512367890",
        "epf_account_no": "GJ/AHM/0034521",
        "esic_account_no": "61000345210000",
        "monthly_epf": 22000, "monthly_esic": 7700, "professional_fee": 2500,
        "opening_balance": -1500  # excess from previous month
    },
    {
        "name": "Gupta Pharma Distributors",
        "contact_person": "Vikram Gupta",
        "phone": "9823412345",
        "epf_account_no": "MH/BAN/0056732",
        "esic_account_no": "31000567320000",
        "monthly_epf": 8500, "monthly_esic": 3000, "professional_fee": 1500,
        "opening_balance": 0
    },
    {
        "name": "Shree Balaji Constructions",
        "contact_person": "Dinesh Yadav",
        "phone": "9765432109",
        "epf_account_no": "MH/NAS/0012398",
        "esic_account_no": "31000123980000",
        "monthly_epf": 45000, "monthly_esic": 15750, "professional_fee": 5000,
        "opening_balance": 0
    },
    {
        "name": "Laxmi Food Products",
        "contact_person": "Priya Deshmukh",
        "phone": "9898765432",
        "epf_account_no": "MH/PUN/0067821",
        "esic_account_no": "31000678210000",
        "monthly_epf": 14000, "monthly_esic": 4900, "professional_fee": 2000,
        "opening_balance": 3500  # short outstanding
    },
    {
        "name": "Jain Electronics",
        "contact_person": "Sanjay Jain",
        "phone": "9876123450",
        "epf_account_no": "MH/MUM/0089234",
        "esic_account_no": "31000892340000",
        "monthly_epf": 28000, "monthly_esic": 9800, "professional_fee": 3000,
        "opening_balance": 0
    },
    {
        "name": "Ramdas Agro Pvt Ltd",
        "contact_person": "Ramdas Kulkarni",
        "phone": "9712398765",
        "epf_account_no": "MH/AUR/0023451",
        "esic_account_no": "31000234510000",
        "monthly_epf": 9500, "monthly_esic": 3325, "professional_fee": 1500,
        "opening_balance": 0
    },
    {
        "name": "Modern Packaging Solutions",
        "contact_person": "Kavita Nair",
        "phone": "9654321098",
        "epf_account_no": "MH/BAN/0091234",
        "esic_account_no": "31000912340000",
        "monthly_epf": 19500, "monthly_esic": 6825, "professional_fee": 2500,
        "opening_balance": -2000  # excess credit held
    }
]
```

**Sample transaction scenarios:**
- Sunrise Garments: pays ₹27,800 (exact) → clean receipt
- Krishna Engineering: paid ₹12,000 last month against ₹14,200 → ₹2,200 short outstanding, this month pays ₹16,200 (current + adjustment)
- Patel Textiles: paid ₹32,700 against ₹32,200 → ₹500 excess → adjusted next month

---

## 9. Implementation Phases

### Phase 1 — Foundation (Week 1-2)
- [ ] Project setup (folders, venv, requirements)
- [ ] MongoDB connection (local + Atlas config via .env)
- [ ] Client CRUD (Add / Edit / View / Deactivate)
- [ ] Basic Ledger setup (Bank, Cash accounts)

### Phase 2 — Core Transactions (Week 3-4)
- [ ] Invoice creation and management
- [ ] Receipt voucher with short/excess auto-detection
- [ ] Payment voucher
- [ ] Journal entry (double-entry validation)

### Phase 3 — Ledgers & Reports (Week 5-6)
- [ ] Individual Client Ledger viewer + print
- [ ] Bank Ledger and Cash Ledger
- [ ] Trial Balance
- [ ] Short Payment and Excess Payment ledgers

### Phase 4 — Advanced Reports (Week 7)
- [ ] Profit & Loss Statement
- [ ] Dashboard with charts
- [ ] Outstanding age-wise report

### Phase 5 — Bank Import (Week 8)
- [ ] CSV/Excel bank statement upload
- [ ] Parsing for SBI/HDFC (configurable)
- [ ] Matching engine
- [ ] Reconciliation report

### Phase 6 — Polish (Week 9-10)
- [ ] PDF print for all reports
- [ ] Bulk invoice generator
- [ ] Backup / export feature
- [ ] Financial year management

---

## 10. Requirements File

```
# requirements.txt
fastapi==0.115.0
uvicorn==0.34.0
streamlit==1.45.0
pymongo==4.10.0
motor==3.6.0          # async MongoDB
python-dotenv==1.0.1
pydantic==2.10.0
pandas==2.2.0
openpyxl==3.1.5
pdfplumber==0.11.0
reportlab==4.2.0      # PDF generation
plotly==5.24.0        # charts in Streamlit
python-dateutil==2.9.0
```

---

## 11. Environment Configuration

```env
# .env
MONGO_URI_DEV=mongodb://localhost:27017
MONGO_URI_PROD=mongodb+srv://user:pass@cluster.mongodb.net/
DB_NAME=vaishnavi_tally
ENV=development          # development | production
FIRM_NAME=Vaishnavi Consultants
FINANCIAL_YEAR_START=2025-04-01
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Frontend | Streamlit | Pure Python, Tally-like forms, no JS needed |
| Backend | FastAPI | Auto docs, Pydantic validation, fast |
| Database | MongoDB | Flexible schema for accounting entries |
| PDF generation | ReportLab | Full control over layout (like Tally prints) |
| Bank import | File upload (CSV/PDF) | Safe, reliable, no ToS issues |
| Entry system | Double-entry | Proper accounting, Trial Balance will balance |

---

*Document Version: 1.0 | Ready for review and finalization*
