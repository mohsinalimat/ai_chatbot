# AI Chatbot — Tools Reference

Complete reference for all 80 registered business intelligence tools. Each tool is callable by the AI through natural language prompts.

All parameters are optional unless marked **(required)**. Date parameters default to the current fiscal year. Company defaults to the user's default company.

---

## CRM (6 tools)

### get_lead_statistics
Get statistics about leads including count, status breakdown, and conversion rates.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_opportunity_pipeline
Get sales opportunity pipeline with stages and values.

| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Filter by status (Open, Converted, Lost, Quotation, Replied, Closed) |
| company | string | Company name |

### get_lead_conversion_rate
Get lead conversion rate showing how many leads converted to opportunities or customers.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_lead_source_analysis
Analyze leads by source/campaign to identify the best-performing lead channels.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_sales_funnel
Get sales funnel showing conversion from leads to opportunities to quotations to sales orders.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_opportunity_by_stage
Get opportunities grouped by sales stage with total value and count per stage.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| status | string | Filter by opportunity status |
| company | string | Company name |

---

## Sales / Selling (5 tools)

### get_sales_analytics
Get sales analytics including revenue, orders, and growth trends.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| customer | string | Filter by customer name |
| company | string | Company name |

### get_top_customers
Get top customers by revenue.

| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Number of customers to return (default 10) |
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_sales_trend
Get monthly sales revenue trend over time.

| Parameter | Type | Description |
|-----------|------|-------------|
| months | integer | Number of months to show (default 12) |
| company | string | Company name |

### get_sales_by_territory
Get sales breakdown by territory/region.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_sales_by_item_group
Get sales breakdown by item group/product category.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| limit | integer | Number of item groups to return (default 10) |
| company | string | Company name |

---

## Buying / Purchase (4 tools)

### get_purchase_analytics
Get purchase analytics including spending, orders, and supplier performance.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_supplier_performance
Analyze supplier performance metrics.

| Parameter | Type | Description |
|-----------|------|-------------|
| supplier | string | Supplier name |
| company | string | Company name |

### get_purchase_trend
Get monthly purchase spending trend over time.

| Parameter | Type | Description |
|-----------|------|-------------|
| months | integer | Number of months to show (default 12) |
| company | string | Company name |

### get_purchase_by_item_group
Get purchase breakdown by item group/product category.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| limit | integer | Number of item groups to return (default 10) |
| company | string | Company name |

---

## Finance — General (5 tools)

### get_financial_summary
Get financial summary including revenue, expenses, and profit for a period.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_cash_flow_analysis
Analyze cash flow patterns and trends over a period.

| Parameter | Type | Description |
|-----------|------|-------------|
| months | integer | Number of months to analyze (default 6) |
| company | string | Company name |

### get_multidimensional_summary
Generate a multi-dimensional summary grouped by any combination of dimensions and time periods. Supports built-in dimensions (company, territory, customer_group, customer, item_group, cost_center, department) and any custom Accounting Dimensions.

| Parameter | Type | Description |
|-----------|------|-------------|
| metric | string | What to measure: revenue, expenses, profit, orders (default: revenue) |
| group_by | array | Dimensions to group by, in order (max 3). E.g. ["territory", "customer_group"] |
| period | string | Time grouping: monthly, quarterly, yearly (default: quarterly) |
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_financial_overview
High-level financial overview with key KPIs: revenue, COGS, gross profit, net profit, cash position, AR, and AP.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_monthly_comparison
Month-over-month comparison of revenue, expenses, and net profit with variance tracking.

| Parameter | Type | Description |
|-----------|------|-------------|
| months | integer | Number of recent months to compare (default 6, max 12) |
| company | string | Company name |

---

## Finance — CFO Dashboard (1 tool)

### get_cfo_dashboard
Comprehensive CFO dashboard with BI metric cards (Revenue, Net Profit, Cash, AR, AP with YoY comparisons), financial highlights, KPIs (margins, ratios, efficiency metrics), cash flow summary, receivables/payables aging, budget variance, and balance sheet snapshot.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

---

## Finance — General Ledger (3 tools)

### get_gl_summary
General Ledger summary with flexible grouping. Useful for cash/bank position, receivables, payables, and income/expense breakdowns.

| Parameter | Type | Description |
|-----------|------|-------------|
| group_by | string | Grouping: root_type, account_type, party_type, voucher_type, account_name (default: root_type) |
| root_type | string | Filter: Asset, Liability, Equity, Income, Expense |
| account_type | string | Filter: Bank, Cash, Receivable, Payable, etc. |
| party_type | string | Filter: Customer, Supplier, Employee |
| party | string | Filter by specific party name |
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_trial_balance
Trial balance showing opening balance, period debit/credit, and closing balance for all accounts, grouped by root type with subtotals.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| root_type | string | Filter: Asset, Liability, Equity, Income, Expense |
| company | string | Company name |

### get_account_statement
Detailed account statement showing all GL transactions with date, voucher, party, debit, credit, and running balance (bank statement view).

| Parameter | Type | Description |
|-----------|------|-------------|
| account | string | **(required)** Account name (e.g. 'Cash - TC', 'Debtors - TC') |
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| party_type | string | Filter: Customer, Supplier |
| party | string | Filter by specific party name |
| company | string | Company name |

---

## Finance — Budget (2 tools)

### get_budget_vs_actual
Compare budgeted amounts vs actual spending by account for a fiscal year.

| Parameter | Type | Description |
|-----------|------|-------------|
| fiscal_year | string | Fiscal year name (e.g. '2025-2026') |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |
| company | string | Company name |

### get_budget_variance
Detailed budget variance analysis with monthly breakdown for a specific account.

| Parameter | Type | Description |
|-----------|------|-------------|
| fiscal_year | string | Fiscal year name |
| account | string | Filter by specific account |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |
| company | string | Company name |

---

## Finance — Cash Flow (3 tools)

### get_cash_flow_statement
Structured cash flow statement with operating, investing, and financing activities.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

### get_cash_flow_trend
Monthly cash flow trend showing inflow, outflow, and net cash flow over time.

| Parameter | Type | Description |
|-----------|------|-------------|
| months | integer | Number of months to analyze (default 12) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

### get_bank_balance
Current bank and cash account balances.

| Parameter | Type | Description |
|-----------|------|-------------|
| account | string | Specific bank or cash account name |
| company | string | Company name |

---

## Finance — Receivables (2 tools)

### get_receivable_aging
Accounts receivable aging analysis with buckets (0-30, 31-60, 61-90, 90+ days overdue).

| Parameter | Type | Description |
|-----------|------|-------------|
| ageing_based_on | string | Aging basis: Due Date or Posting Date (default: Due Date) |
| customer | string | Filter by customer name |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

### get_top_debtors
Top customers with the highest outstanding receivables.

| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Number of debtors to return (default 10) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

---

## Finance — Payables (2 tools)

### get_payable_aging
Accounts payable aging analysis with buckets (0-30, 31-60, 61-90, 90+ days overdue).

| Parameter | Type | Description |
|-----------|------|-------------|
| ageing_based_on | string | Aging basis: Due Date or Posting Date (default: Due Date) |
| supplier | string | Filter by supplier name |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

### get_top_creditors
Top suppliers with the highest outstanding payables.

| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Number of creditors to return (default 10) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

---

## Finance — Profitability (3 tools)

### get_profitability_by_customer
Profitability by customer showing revenue, cost, and profit margin.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| limit | integer | Number of customers to return (default 10) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

### get_profitability_by_item
Profitability by item/product showing revenue, cost, and profit margin.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| limit | integer | Number of items to return (default 10) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

### get_profitability_by_territory
Profitability by territory/region showing revenue, cost, and margin.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

---

## Finance — Ratios (3 tools)

### get_liquidity_ratios
Calculate liquidity ratios: current ratio and quick ratio.

| Parameter | Type | Description |
|-----------|------|-------------|
| company | string | Company name |

### get_profitability_ratios
Calculate profitability ratios: gross margin, net margin, and return on assets (ROA).

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

### get_efficiency_ratios
Calculate efficiency ratios: inventory turnover, receivable days (DSO), and payable days (DPO).

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |
| cost_center | string | Filter by cost center |
| department | string | Filter by department |
| project | string | Filter by project |

---

## Finance — Working Capital (2 tools)

### get_working_capital_summary
Working capital summary: receivables, payables, inventory, and net working capital.

| Parameter | Type | Description |
|-----------|------|-------------|
| company | string | Company name |

### get_cash_conversion_cycle
Calculate the cash conversion cycle (CCC = DSO + DIO - DPO) for a period.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

---

## Finance — Consolidation (1 tool)

### get_consolidated_report
Run any analytics tool across a parent company and all its subsidiaries, then consolidate the results. Pass the name of the tool (e.g. 'get_sales_analytics') and its parameters.

| Parameter | Type | Description |
|-----------|------|-------------|
| tool_name | string | **(required)** Name of the tool to run across companies |
| tool_params | object | Parameters to pass to the tool (do NOT include 'company') |
| target_currency | string | Currency to display results in (defaults to parent company's currency) |
| company | string | Parent company name |

---

## Finance — Session Management (2 tools)

### set_include_subsidiaries
Enable or disable child company inclusion for the current chat session.

| Parameter | Type | Description |
|-----------|------|-------------|
| include | boolean | **(required)** True to include subsidiaries, False to exclude |

### set_target_currency
Set or reset the display currency for the current chat session.

| Parameter | Type | Description |
|-----------|------|-------------|
| currency | string | Currency code (e.g. 'USD', 'EUR'). Empty to reset to default. |

---

## Inventory / Stock (4 tools)

### get_inventory_summary
Get inventory summary including stock levels and valuation.

| Parameter | Type | Description |
|-----------|------|-------------|
| warehouse | string | Filter by warehouse |
| company | string | Company name |

### get_low_stock_items
Get items with stock below reorder level.

| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Maximum items to return (default 50) |
| company | string | Company name |

### get_stock_movement
Get stock movement (in/out quantities) for items over a period.

| Parameter | Type | Description |
|-----------|------|-------------|
| item_code | string | Filter by specific item code |
| warehouse | string | Filter by specific warehouse |
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

### get_stock_ageing
Get age of stock in warehouse — how long items have been sitting.

| Parameter | Type | Description |
|-----------|------|-------------|
| warehouse | string | Filter by specific warehouse |
| company | string | Company name |

---

## HRMS (6 tools)

Requires the HRMS app to be installed.

### get_employee_count
Get employee headcount with optional breakdown by department, status, or designation.

| Parameter | Type | Description |
|-----------|------|-------------|
| department | string | Filter by department |
| status | string | Active, Inactive, Suspended, or Left (default: Active) |
| designation | string | Filter by designation/job title |
| company | string | Company name |

### get_attendance_summary
Get attendance summary showing present, absent, on leave, half day, and WFH counts.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD, default: current month start) |
| to_date | string | End date (YYYY-MM-DD, default: current month end) |
| department | string | Filter by department |
| company | string | Company name |

### get_leave_balance
Get leave balance showing allocated, used, and remaining leaves by type.

| Parameter | Type | Description |
|-----------|------|-------------|
| employee | string | Employee ID or name (omit for company-wide summary) |
| leave_type | string | Filter by leave type (e.g. 'Casual Leave', 'Sick Leave') |
| company | string | Company name |

### get_payroll_summary
Get payroll summary with total gross pay, deductions, and net pay.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD, default: current month start) |
| to_date | string | End date (YYYY-MM-DD, default: current month end) |
| company | string | Company name |

### get_department_wise_salary
Get salary distribution by department showing gross and net pay per department.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD, default: current month start) |
| to_date | string | End date (YYYY-MM-DD, default: current month end) |
| company | string | Company name |

### get_employee_turnover
Get employee turnover showing new hires vs exits with turnover rate.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| company | string | Company name |

---

## IDP — Intelligent Document Processing (3 tools)

### extract_document_data
Extract structured data from an uploaded document (invoice, PO, quotation, receipt) and map it to an ERPNext DocType schema. Handles any language, any format (PDF, image, Excel, Word), non-uniform headers, and naming discrepancies. Returns extracted fields for user review before record creation.

| Parameter | Type | Description |
|-----------|------|-------------|
| file_url | string | **(required)** Frappe file URL of the uploaded document |
| target_doctype | string | **(required)** ERPNext DocType to map to (Sales Invoice, Purchase Invoice, Quotation, Sales Order, Purchase Order, Delivery Note, Purchase Receipt) |
| company | string | Company name |
| output_language | string | Language for extracted output values (default: per settings or English) |

### create_from_extracted_data
Create an ERPNext record from previously extracted document data. Only called after user confirms the extraction.

| Parameter | Type | Description |
|-----------|------|-------------|
| extracted_data_json | string | **(required)** JSON string of extracted data from extract_document_data |
| target_doctype | string | **(required)** ERPNext DocType to create |
| company | string | Company name |
| create_missing_masters | string | Set to 'true' to auto-create missing Customer, Supplier, Item, UOM records |
| item_defaults_json | string | JSON with defaults for missing Items: {"is_stock_item": 1, "is_fixed_asset": 0, "item_group": "Consumable"} |

### compare_document_with_record
Compare an uploaded document with an existing ERPNext record and highlight differences. Useful for reconciliation (e.g. vendor invoice vs Purchase Order).

| Parameter | Type | Description |
|-----------|------|-------------|
| file_url | string | **(required)** Frappe file URL of the document to compare |
| doctype | string | **(required)** ERPNext DocType of the existing record |
| docname | string | **(required)** Name/ID of the existing record |
| company | string | Company name |

---

## Predictive Analytics (5 tools)

### forecast_revenue
Forecast future revenue based on historical sales invoice data. Uses statistical methods (moving average, exponential smoothing, trend analysis). Returns predictions with confidence intervals and chart.

| Parameter | Type | Description |
|-----------|------|-------------|
| months_ahead | integer | Months to forecast (default 3, max 12) |
| company | string | Company name |

### forecast_by_territory
Forecast revenue by territory/region. Runs separate forecasts for top territories with comparison chart.

| Parameter | Type | Description |
|-----------|------|-------------|
| months_ahead | integer | Months to forecast (default 3, max 6) |
| company | string | Company name |

### forecast_demand
Forecast future demand (quantity) for a specific item based on historical sales.

| Parameter | Type | Description |
|-----------|------|-------------|
| item_code | string | **(required)** Item code or item name to forecast |
| months_ahead | integer | Months to forecast (default 3, max 12) |
| company | string | Company name |

### forecast_cash_flow
Forecast future cash flow (inflows and outflows) based on historical Payment Entry data.

| Parameter | Type | Description |
|-----------|------|-------------|
| months_ahead | integer | Months to forecast (default 3, max 12) |
| company | string | Company name |

### detect_anomalies
Detect unusual transactions and patterns in financial data. Flags large amounts and new suppliers/customers with big first orders. Uses z-score and IQR methods.

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date (YYYY-MM-DD) |
| to_date | string | End date (YYYY-MM-DD) |
| sensitivity | string | Detection sensitivity: low (z>3.0), medium (z>2.5, default), high (z>2.0) |
| company | string | Company name |

---

## Operations — Create (3 tools)

### create_lead
Create a new Lead in ERPNext.

| Parameter | Type | Description |
|-----------|------|-------------|
| first_name | string | **(required)** First name of the lead |
| last_name | string | Last name |
| company_name | string | Company/organization name |
| email_id | string | Email address |
| mobile_no | string | Mobile phone number |
| source | string | Lead source (Website, Referral, Campaign, Cold Calling) |
| company | string | Company name |

### create_opportunity
Create a new Opportunity in ERPNext. Accepts document ID or human name as party_name.

| Parameter | Type | Description |
|-----------|------|-------------|
| party_name | string | **(required)** Customer or Lead reference (ID or name) |
| opportunity_from | string | Source type: Customer or Lead (default: Lead) |
| opportunity_amount | number | Expected opportunity value |
| currency | string | Currency code |
| sales_stage | string | Sales stage (Prospecting, Qualification, Proposal/Price Quote) |
| company | string | Company name |

### create_todo
Create a new ToDo task in ERPNext.

| Parameter | Type | Description |
|-----------|------|-------------|
| description | string | **(required)** Task description |
| allocated_to | string | Email of user to assign to (defaults to current user) |
| date | string | Due date (YYYY-MM-DD) |
| priority | string | Low, Medium (default), or High |

---

## Operations — Search (3 tools)

### search_customers
Search for customers by name, customer group, or territory.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Search text for customer name |
| customer_group | string | Filter by customer group |
| territory | string | Filter by territory |
| limit | integer | Maximum results (default 10) |
| company | string | Company name |

### search_items
Search for items by name, item code, or item group.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | string | Search text for item name or code |
| item_group | string | Filter by item group |
| limit | integer | Maximum results (default 10) |
| company | string | Company name |

### search_documents
Search for documents of any DocType by name or status.

| Parameter | Type | Description |
|-----------|------|-------------|
| doctype | string | **(required)** DocType to search (e.g. 'Sales Invoice', 'Lead') |
| query | string | Search text for document name |
| status | string | Filter by status |
| limit | integer | Maximum results (default 10) |
| company | string | Company name |

---

## Operations — Update (3 tools)

### update_lead_status
Update the status of an existing Lead.

| Parameter | Type | Description |
|-----------|------|-------------|
| lead_name | string | **(required)** Lead document name/ID |
| status | string | **(required)** New status: Lead, Open, Replied, Opportunity, Quotation, Lost Quotation, Interested, Converted, Do Not Contact |

### update_opportunity_status
Update the status of an existing Opportunity.

| Parameter | Type | Description |
|-----------|------|-------------|
| opportunity_name | string | **(required)** Opportunity document name/ID |
| status | string | **(required)** New status: Open, Quotation, Converted, Lost, Replied, Closed |

### update_todo
Update an existing ToDo task.

| Parameter | Type | Description |
|-----------|------|-------------|
| todo_name | string | **(required)** ToDo document name/ID |
| status | string | Open, Closed, or Cancelled |
| priority | string | Low, Medium, or High |
| description | string | Updated task description |
| date | string | Updated due date (YYYY-MM-DD) |

---

## Summary

| Category | Tools |
|----------|-------|
| CRM | 6 |
| Sales / Selling | 5 |
| Buying / Purchase | 4 |
| Finance (General, CFO, GL, Budget, Cash Flow, Receivables, Payables, Profitability, Ratios, Working Capital, Consolidation, Session) | 38 |
| Inventory / Stock | 4 |
| HRMS | 6 |
| IDP (Document Processing) | 3 |
| Predictive Analytics | 5 |
| Operations (Create, Search, Update) | 9 |
| **Total** | **80** |
