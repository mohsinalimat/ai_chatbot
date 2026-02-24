# AI Chatbot — Testing Guide

Step-by-step testing instructions for each phase of the AI Chatbot implementation.

---

## Prerequisites

```bash
# Ensure bench is running
bench start

# Site name used throughout this guide
SITE=test.local
```

Open the chatbot at:
- **With nginx**: `http://<SITE>/ai-chatbot` (recommended for production-like testing)
- **Without nginx (dev mode)**: `http://<SITE>:8005/ai-chatbot`

---

## Phase 1: Foundation — Core Framework, Data Layer & Security

### 1.1 Chatbot Settings

1. Go to **Chatbot Settings** (`/app/chatbot-settings`).
2. Verify the following fields exist:
   - **OpenAI section**: `Enable OpenAI`, `OpenAI API Key`, `OpenAI Model`, `Temperature`, `Max Tokens`
   - **Claude section**: `Enable Claude`, `Claude API Key`, `Claude Model`, `Temperature`, `Max Tokens`
   - **Tools section**: `Enable CRM Tools`, `Enable Sales Tools`, `Enable Purchase Tools`, `Enable Finance Tools`, `Enable Inventory Tools`
   - **Streaming section**: `Enable Streaming` (checkbox, default: checked)
3. Enter a valid API key for at least one provider (OpenAI or Claude).
4. Enable the corresponding provider checkbox.
5. Save.

### 1.2 Basic Chat (Non-Streaming)

1. Open the chatbot: `http://<SITE>:8005/ai-chatbot`
2. A new conversation should be auto-created.
3. Type a simple message: `Hello, who are you?`
4. **Expected**: "AI is thinking..." typing indicator appears, followed by an AI response.
5. The sidebar should show the conversation with an auto-generated title.

### 1.3 Conversation Management

1. Click **New Chat** in the sidebar — a new conversation should appear.
2. Switch between conversations — messages should load correctly.
3. Delete a conversation — it should disappear from the sidebar.

### 1.4 AI Provider Switching

1. In the chat header, switch between OpenAI and Claude (if both are configured).
2. Send a message — the response should come from the selected provider.

### 1.5 ERPNext Tool Calls

1. Ask a business question: `What is the total sales this month?`
2. **Expected**: The AI should use ERPNext tools (visible in the response as tool call indicators).
3. Try other tool-triggering questions:
   - `Show me the top 5 customers by revenue`
   - `What is the current stock level of [item name]?`
   - `List open purchase orders`

### 1.6 Multi-Company & Multi-Currency

1. If multiple companies are configured in ERPNext:
   - Ask: `What is the total revenue for [Company Name]?`
   - **Expected**: Response includes `company` and `currency` fields.
2. Verify that monetary values use `base_*` fields for company-currency amounts.

---

## Phase 2: Streaming — Frappe Realtime (Socket.IO/WebSocket)

### 2.0 Prerequisites

```bash
# Apply the new streaming field to Chatbot Settings
bench --site test.local migrate

# Rebuild frontend (if not already done)
cd apps/ai_chatbot/frontend && npm run build

# Restart bench to pick up Python changes
# (Ctrl+C on bench start, then bench start again)
bench start
```

Verify Socket.IO is running:
- Check that `socketio_port` in `sites/common_site_config.json` is set (e.g., `9005`).
- The Node.js Socket.IO server starts automatically with `bench start`.

### 2.1 Enable Streaming

1. Go to **Chatbot Settings** (`/app/chatbot-settings`).
2. Verify the **Streaming Configuration** section exists.
3. Check **Enable Streaming** (should be checked by default).
4. Save.

### 2.2 Socket.IO Connection

1. Open the chatbot: `http://<SITE>:8005/ai-chatbot`
2. Open browser DevTools → Console.
3. **Expected**: You should see `[AI Chatbot] Socket.IO connected` in the console.
4. If you see a connection error, check:
   - Is `bench start` running? (Socket.IO server needs to be up)
   - Is `socketio_port` correct in `common_site_config.json`?
   - Check browser Network tab for WebSocket connection to `/<site_name>` namespace.

### 2.3 Typing Indicator

1. Send a message: `Tell me about ERPNext`
2. **Expected**: The "AI is thinking..." typing indicator (bouncing dots) should appear immediately after sending.
3. The indicator should remain visible until the first streaming tokens arrive.

### 2.4 Token-by-Token Streaming

1. Send a message that will produce a longer response: `Explain the key features of ERPNext in detail`
2. **Expected**:
   - Typing indicator appears first (bouncing dots).
   - Text starts appearing word-by-word / chunk-by-chunk (not all at once).
   - A blinking blue cursor appears at the end of the streaming text.
   - Content renders as markdown (bold, lists, code blocks, etc.) as it streams.
3. The response should auto-scroll as new content arrives.

### 2.5 Streaming with Tool Calls

1. Ask a question that triggers tool usage: `What is the total sales amount this month?`
2. **Expected**:
   - Typing indicator appears.
   - Tool call indicator appears (spinning icon with tool name, e.g., "Sales Summary...").
   - Tool result indicator changes to a green checkmark when complete.
   - AI continues streaming its response after tool execution.
3. Try multi-tool questions: `Compare sales and purchase amounts this month`
   - **Expected**: Multiple tool call indicators appear sequentially.

### 2.6 Stop Generation

1. Send a message that will produce a long response: `Write a detailed essay about artificial intelligence`
2. While the response is streaming, click the red **Stop** button.
3. **Expected**:
   - Streaming stops immediately.
   - The partial response remains visible.
   - The input area becomes active again (Send button returns).

### 2.7 Streaming Fallback

1. Go to **Chatbot Settings** and uncheck **Enable Streaming**.
2. Save and refresh the chatbot page.
3. Send a message.
4. **Expected**: Falls back to non-streaming behavior — typing indicator shows, then complete response appears at once.
5. Re-enable streaming after testing.

### 2.8 Conversation Persistence

1. Send a streaming message and wait for it to complete.
2. Switch to another conversation and back.
3. **Expected**: The streamed message should be persisted — it loads from the database when you switch back.
4. The conversation title should auto-update based on the first message.

### 2.9 Error Handling

1. Temporarily set an invalid API key in Chatbot Settings.
2. Send a message.
3. **Expected**: An error should appear in the chat (not a silent failure).
4. Restore the correct API key.

### 2.10 Browser DevTools Verification

For deeper debugging, check these in browser DevTools:

**Console tab:**
- `[AI Chatbot] Socket.IO connected` — confirms Socket.IO is working.

**Network tab:**
- Look for a WebSocket connection to `ws://<host>:<socketio_port>/<site_name>`.
- You should see Socket.IO frames being exchanged.
- The `send_message` POST request should return quickly with `{"stream_id": "..."}`.

**Network tab — XHR filter:**
- The `send_message` POST should return almost immediately (not blocking until the AI finishes).
- The response body should contain `"success": true` and a `stream_id`.

---

## Phase 3: Data Operations (CRUD) + Fiscal Year Defaults + System Prompt

### 3.0 Prerequisites

```bash
# Apply the new settings field (enable_write_operations)
bench --site test.local migrate

# Rebuild frontend (new amber write-operation indicator)
cd apps/ai_chatbot/frontend && npm run build

# Restart bench to pick up Python changes
# (Ctrl+C on bench start, then bench start again)
bench start
```

### 3.1 Chatbot Settings — Data Operations Section

1. Go to **Chatbot Settings** (`/app/chatbot-settings`).
2. Verify a new **Data Operations** section exists between "ERPNext Tools Configuration" and "Streaming Configuration".
3. Verify the **Enable Write Operations** checkbox exists (should be **unchecked** by default).
4. Leave it unchecked for now — we'll test read-only tools first.
5. Save.

### 3.2 System Prompt — AI Persona

1. Open the chatbot: `http://<SITE>/ai-chatbot`
2. Send: `Who are you and what can you do?`
3. **Expected**: The AI should identify itself as an ERPNext business assistant (not a generic AI). It should mention it can help with business data, analytics, etc.
4. Send: `What company am I working with?`
5. **Expected**: The AI should know your company name, currency, and fiscal year — these are injected via the system prompt.

### 3.3 Fiscal Year Date Defaults

This is a key change — all date-based tools now default to the current fiscal year instead of arbitrary periods.

1. Send: `What is the total sales?` (no date mentioned)
2. **Expected**: The AI should use ERPNext tools and report sales for the **current fiscal year** (not "last 30 days" or "all time"). The response should mention the date range used (e.g., "From 2025-04-01 to 2026-03-31").
3. Send: `What is the financial summary?`
4. **Expected**: Revenue, expenses, and profit for the current fiscal year. Previously this defaulted to the last 30 days.
5. Send: `Show me top 5 customers by revenue`
6. **Expected**: Top customers for the current fiscal year.
7. Send: `What are the purchase analytics?`
8. **Expected**: Purchase data for the current fiscal year.
9. Send: `What are the lead statistics?`
10. **Expected**: Lead stats for the current fiscal year.
11. **Explicit date override**: Send: `What were the total sales in January 2026?`
12. **Expected**: The AI should use the explicit date range (2026-01-01 to 2026-01-31), not the fiscal year default.

### 3.4 Search Tools (Read-Only)

These work even with "Enable Write Operations" unchecked, because search tools are in the `operations` category but are read-only in practice. **Note**: The `operations` category must be enabled for search tools to appear. Enable "Enable Write Operations" in settings for this test, or verify the tools appear.

1. Go to **Chatbot Settings** → check **Enable Write Operations** → Save.
2. Send: `Search for customers matching "Acme"`
3. **Expected**: The AI uses the `search_customers` tool and returns matching customer records. The blue "Used ERPNext Tools" indicator should show "Customers" (with `search_` prefix stripped).
4. Send: `Find items in the "Raw Material" item group`
5. **Expected**: The AI uses `search_items` and returns matching items.
6. Send: `Search for open Sales Orders`
7. **Expected**: The AI uses `search_documents` with doctype="Sales Order" and status="Open" (or similar). Returns matching documents.

### 3.5 Create Tools (Write Operations)

1. Ensure **Enable Write Operations** is checked in Chatbot Settings.
2. Send: `Create a lead named John Smith from Acme Corp with email john@acme.com`
3. **Expected**:
   - The AI should **NOT** immediately create the lead.
   - Instead, it should present the details in a formatted summary and ask: "Shall I proceed?" (or similar confirmation).
   - This is enforced by the system prompt and tool description.
4. Reply: `Yes, proceed`
5. **Expected**:
   - The AI calls the `create_lead` tool.
   - A new Lead document is created in ERPNext.
   - The response confirms creation with the Lead document name (e.g., "Lead CRM-LEAD-00042 created successfully").
   - The amber **"Document Operations Performed"** indicator appears below the response with "Create Lead" tag.
6. **Verify in ERPNext**: Go to `/app/lead` and confirm the new lead exists with the correct details.

### 3.6 Create Opportunity

1. Send: `Create an opportunity for customer "John Smith" worth 50000 INR at Prospecting stage`
2. **Expected**: AI presents details and asks for confirmation.
3. Confirm with: `Yes`
4. **Expected**: Opportunity created. Amber indicator shows "Create Opportunity".
5. **Verify**: Check `/app/opportunity` for the new record.

### 3.7 Create ToDo

1. Send: `Create a task to follow up with John Smith by next Friday`
2. **Expected**: AI presents the ToDo details (description, date, priority) and asks for confirmation.
3. Confirm.
4. **Expected**: ToDo created. Amber indicator shows "Create Todo".
5. **Verify**: Check `/app/todo` for the new task.

### 3.8 Update Tools (Write Operations)

1. First, find a Lead name: Send `Search for leads matching "John Smith"`
2. Note the Lead name from the response (e.g., `CRM-LEAD-00042`).
3. Send: `Update lead CRM-LEAD-00042 status to Interested`
4. **Expected**: AI confirms the change and asks for approval.
5. Confirm.
6. **Expected**: Lead status updated. Amber indicator shows "Update Lead Status".
7. **Verify**: Check the Lead document in ERPNext — status should be "Interested".

### 3.9 Update ToDo

1. Send: `Mark my latest todo as closed`
2. **Expected**: AI may first search for your ToDos, then ask to confirm which one to close.
3. After confirmation, the ToDo status should be updated.
4. **Verify**: Check `/app/todo`.

### 3.10 Write Operations Disabled

1. Go to **Chatbot Settings** → **uncheck** "Enable Write Operations" → Save.
2. Refresh the chatbot page.
3. Send: `Create a lead named Jane Doe`
4. **Expected**: The AI should **not** have access to create/update/search tools. It should respond that it cannot create records or suggest going to the Lead form manually.
5. Re-enable Write Operations after testing.

### 3.11 Permission Check

1. Log in as a user with **limited permissions** (not System Manager).
2. Open the chatbot.
3. Try: `Create a lead named Test User`
4. **Expected**: If the user doesn't have create permission on Lead, the tool should return a permission error, and the AI should relay this to the user.

### 3.12 Tool Call Indicators — Read vs Write

1. Send a question that triggers both read and write tools in the same conversation (across different messages):
   - First: `What are the total sales this month?` → should show **blue** "Used ERPNext Tools" indicator.
   - Then: `Create a todo to review sales report` → after confirmation, should show **amber** "Document Operations Performed" indicator.
2. **Expected**: Blue indicator for read-only tools (get_*, search_*), amber indicator for write tools (create_*, update_*).

### 3.13 Error Handling — Invalid Status

1. Send: `Update lead CRM-LEAD-00042 status to "InvalidStatus"`
2. **Expected**: The AI (or the tool) should return an error indicating the status is invalid and list valid options.

### 3.14 Error Handling — Non-Existent Document

1. Send: `Update lead NONEXISTENT-LEAD-999 status to Open`
2. **Expected**: The tool should return an error that the document doesn't exist.

---

## Phase 4: Finance Tools & Business Intelligence + ECharts

### 4.0 Prerequisites

```bash
# Apply new fields (tool_results on Chatbot Message)
bench --site test.local migrate

# Rebuild frontend (ECharts + chart components)
cd apps/ai_chatbot/frontend && npm run build

# Restart bench
bench start
```

Ensure you have **sample data** in ERPNext for meaningful results:
- Sales Invoices (posted, with items) for revenue/profitability
- Purchase Invoices (posted) for payables/purchasing
- Journal Entries for financial summaries
- Budget records (optional, for budget tools)
- Multiple Customers and Suppliers for aging/top-N tools

### 4.1 Chatbot Settings — Finance Tools

1. Go to **Chatbot Settings** (`/app/chatbot-settings`).
2. Verify **Enable Finance Tools** is checked.
3. Also verify **Enable Sales Tools**, **Enable Purchase Tools**, and **Enable Inventory Tools** are checked (needed for enhanced analytics).
4. Save.

---

### 4.2 Financial Summary & Ratios

#### 4.2.1 Liquidity Ratios

1. Send: `What are the current liquidity ratios?`
2. **Expected**: AI calls `get_liquidity_ratios`. Response includes:
   - Current ratio and quick ratio values
   - Component breakdown (current assets, current liabilities, inventory)
   - Blue "Used ERPNext Tools" indicator with "Liquidity Ratios" tag

#### 4.2.2 Profitability Ratios

1. Send: `Show me profitability ratios for this fiscal year`
2. **Expected**: AI calls `get_profitability_ratios`. Response includes:
   - Gross margin %, net margin %, ROA %
   - Revenue, COGS, gross profit, net profit, total assets
   - Date range mentioned in response

#### 4.2.3 Efficiency Ratios

1. Send: `What are the efficiency ratios?`
2. **Expected**: AI calls `get_efficiency_ratios`. Response includes:
   - Inventory turnover, receivable days (DSO), payable days (DPO)
   - Component breakdown

---

### 4.3 Profitability Analysis

#### 4.3.1 Profitability by Customer

1. Send: `Show me the most profitable customers`
2. **Expected**: AI calls `get_profitability_by_customer`. Response includes:
   - Table or list of customers with revenue, cost, margin, margin %
   - An **ECharts horizontal bar chart** rendered inline (if data exists)
   - Blue tool indicator with "Profitability By Customer" tag

#### 4.3.2 Profitability by Item

1. Send: `Which products are most profitable?`
2. **Expected**: AI calls `get_profitability_by_item`. Response includes:
   - Items with revenue, cost, margin, margin %, quantity
   - ECharts chart rendered inline

#### 4.3.3 Profitability by Territory

1. Send: `Show profitability breakdown by territory`
2. **Expected**: AI calls `get_profitability_by_territory`. Response includes:
   - Territory-level revenue, cost, margin
   - ECharts **pie chart** rendered inline

---

### 4.4 Receivables & Payables

#### 4.4.1 Receivable Aging

1. Send: `Show me the accounts receivable aging`
2. **Expected**: AI calls `get_receivable_aging`. Response includes:
   - Aging buckets: 0–30, 31–60, 61–90, 90+ days
   - Total outstanding amount
   - ECharts **bar chart** with aging buckets

#### 4.4.2 Top Debtors

1. Send: `Who are the top 10 debtors?`
2. **Expected**: AI calls `get_top_debtors`. Response includes:
   - List of customers with outstanding amounts
   - ECharts horizontal bar chart

#### 4.4.3 Payable Aging

1. Send: `Show accounts payable aging`
2. **Expected**: AI calls `get_payable_aging`. Response includes:
   - Aging buckets with amounts
   - ECharts bar chart

#### 4.4.4 Top Creditors

1. Send: `Who do we owe the most money to?`
2. **Expected**: AI calls `get_top_creditors`. Response includes:
   - Suppliers with outstanding amounts
   - ECharts horizontal bar chart

---

### 4.5 Working Capital

#### 4.5.1 Working Capital Summary

1. Send: `What is our working capital position?`
2. **Expected**: AI calls `get_working_capital_summary`. Response includes:
   - Receivables, inventory value, current assets
   - Payables, current liabilities
   - Net working capital

#### 4.5.2 Cash Conversion Cycle

1. Send: `What is the cash conversion cycle?`
2. **Expected**: AI calls `get_cash_conversion_cycle`. Response includes:
   - DSO (Days Sales Outstanding)
   - DIO (Days Inventory Outstanding)
   - DPO (Days Payable Outstanding)
   - CCC = DSO + DIO − DPO

---

### 4.6 Budget Analysis

> **Note**: Budget tools require Budget records in ERPNext. If no budgets are configured, the tools will return empty results or an appropriate message.

#### 4.6.1 Budget vs Actual

1. Send: `Show budget vs actual for this fiscal year`
2. **Expected**: AI calls `get_budget_vs_actual`. Response includes:
   - Accounts with budget amount, actual amount, variance
   - Totals row
   - ECharts **multi-series bar chart** (Budget vs Actual)

#### 4.6.2 Budget Variance

1. Send: `Show monthly budget variance`
2. **Expected**: AI calls `get_budget_variance`. Response includes:
   - Monthly breakdown with budget, actual, variance
   - ECharts **multi-series line chart**

---

### 4.7 Cash Flow

#### 4.7.1 Cash Flow Statement

1. Send: `Generate a cash flow statement`
2. **Expected**: AI calls `get_cash_flow_statement`. Response includes:
   - Operating activities: inflow, outflow, net
   - Financing & other activities: inflow, outflow, net
   - Total net cash flow
   - Period used

#### 4.7.2 Cash Flow Trend

1. Send: `Show cash flow trend for the last 12 months`
2. **Expected**: AI calls `get_cash_flow_trend`. Response includes:
   - Monthly data points
   - ECharts **multi-series line chart** (inflow, outflow, net)

#### 4.7.3 Bank Balance

1. Send: `What are the current bank balances?`
2. **Expected**: AI calls `get_bank_balance`. Response includes:
   - Bank/cash accounts with individual balances
   - Total balance across all accounts

---

### 4.8 Enhanced Selling Analytics

#### 4.8.1 Sales Trend

1. Send: `Show the sales trend for the last 12 months`
2. **Expected**: AI calls `get_sales_trend`. Response includes:
   - Monthly revenue figures
   - ECharts **line chart** with revenue trend

#### 4.8.2 Sales by Territory

1. Send: `Break down sales by territory`
2. **Expected**: AI calls `get_sales_by_territory`. Response includes:
   - Territory-wise revenue breakdown
   - ECharts **pie chart**

#### 4.8.3 Sales by Item Group

1. Send: `Show sales by product category`
2. **Expected**: AI calls `get_sales_by_item_group`. Response includes:
   - Item groups with revenue amounts
   - ECharts **bar chart**

---

### 4.9 Enhanced Buying Analytics

#### 4.9.1 Purchase Trend

1. Send: `Show the purchase trend for the last 12 months`
2. **Expected**: AI calls `get_purchase_trend`. Response includes:
   - Monthly purchase figures
   - ECharts **line chart**

#### 4.9.2 Purchases by Item Group

1. Send: `Break down purchases by item group`
2. **Expected**: AI calls `get_purchase_by_item_group`. Response includes:
   - Item groups with purchase amounts
   - ECharts **bar chart**

---

### 4.10 Enhanced Stock Tools

#### 4.10.1 Stock Movement

1. Send: `Show stock movement for [item_code]` (use a real item code from your data)
2. **Expected**: AI calls `get_stock_movement`. Response includes:
   - In/out movements with dates and quantities
   - ECharts **multi-series bar chart** (in vs out) when item_code is specified

#### 4.10.2 Stock Ageing

1. Send: `Show stock ageing report`
2. **Expected**: AI calls `get_stock_ageing`. Response includes:
   - Items with age in days, warehouse, quantity, value
   - Aging summary buckets (0–30, 31–60, 61–90, 90+)
   - ECharts **bar chart** by age bucket

---

### 4.11 Chart Rendering (Frontend)

This section tests the ECharts integration across all chart-producing tools.

#### 4.11.1 Chart Appears Inline

1. Send any chart-producing query (e.g., `Show sales trend for 12 months`).
2. **Expected**: An interactive ECharts chart renders **inline** within the chat message, below the text response.
3. The chart should have a title, axes labels, and tooltip on hover.

#### 4.11.2 Chart Responsiveness

1. Resize the browser window while a chart is visible.
2. **Expected**: The chart resizes proportionally — no overflow or clipping.

#### 4.11.3 Chart Data Toggle

1. Below the chart, look for a **data toggle** button (bar chart icon).
2. Click it.
3. **Expected**: Raw JSON data appears below the chart. Click again to hide it.

#### 4.11.4 Multiple Charts

1. In a new conversation, send several chart-producing queries in sequence:
   - `Show sales trend`
   - `Show receivable aging`
   - `Show profitability by customer`
2. Scroll up through the conversation.
3. **Expected**: Each message has its own independent chart. Charts do not interfere with each other.

#### 4.11.5 No Chart When No Data

1. Send a query where no data exists (e.g., `Show budget vs actual` with no budgets configured).
2. **Expected**: The AI responds with a text explanation. No empty or broken chart renders.

---

### 4.12 Date Defaults & Company Context (Finance Tools)

#### 4.12.1 Fiscal Year Default

1. Send: `What is the cash flow statement?` (no dates)
2. **Expected**: AI does **not** ask for dates. Tool uses current fiscal year automatically. Response mentions the date range used.

#### 4.12.2 Explicit Date Override

1. Send: `Show profitability by customer for January 2026`
2. **Expected**: Tool uses 2026-01-01 to 2026-01-31 (not the fiscal year default).

#### 4.12.3 Company Default

1. Send: `Show liquidity ratios` (no company mentioned)
2. **Expected**: AI does **not** ask for company name. Tool uses user's default company.

---

### 4.13 Currency in Responses

1. Send: `What is the total accounts receivable?`
2. **Expected**: Response includes currency symbol/code (e.g., "INR 5,00,000" or "₹5,00,000").
3. All monetary values across finance tools should include the company's base currency.

---

### 4.14 Error Handling

#### 4.14.1 No Data Scenario

1. Send: `Show budget variance for a cost center that doesn't exist`
2. **Expected**: The AI should relay that no data was found, not throw an error.

#### 4.14.2 Missing Fiscal Year

1. If no fiscal year covers the current date, finance tools should return a clear error message.
2. **Expected**: AI relays the error: "No fiscal year found" or similar.

---

## Phase 5: HRMS Tools & Enhanced CRM

### 5.0 Prerequisites

```bash
# Apply new settings field (enable_hrms_tools)
bench --site test.local migrate

# Rebuild frontend
cd apps/ai_chatbot/frontend && npm run build

# Restart bench
bench start
```

Ensure you have **sample data** for meaningful results:

**HRMS data:**
- Employee records (Active, with department and designation)
- Attendance records (Present, Absent, On Leave, Half Day, Work From Home)
- Leave Allocations and Leave Applications (Approved)
- Salary Slips (Submitted, docstatus=1) with gross pay, deductions, net pay

**CRM data:**
- Leads (various statuses: Lead, Open, Replied, Opportunity, Converted, Quotation, Lost)
- Opportunities (with sales stages and amounts)
- Quotations (submitted)
- Sales Orders (submitted)
- UTM Source records (for lead source analysis)

### 5.1 Chatbot Settings — HRMS Tools

1. Go to **Chatbot Settings** (`/app/chatbot-settings`).
2. Verify the **Enable HRMS Tools** checkbox exists in the ERPNext Tools Configuration section.
3. It should be **checked** by default.
4. Save.

---

### 5.2 HRMS Tools

> **Note**: HRMS tools require the `hrms` Frappe app to be installed. If HRMS is not installed, these tools will not appear in the tool schema.

#### 5.2.1 Employee Count

1. Send: `How many active employees do we have?`
2. **Expected**: AI calls `get_employee_count`. Response includes:
   - Total employee count
   - Department-wise breakdown
   - ECharts **pie chart** of employees by department
   - Blue "Used ERPNext Tools" indicator with "Employee Count" tag

#### 5.2.2 Employee Count by Department

1. Send: `Show employee count for the Engineering department`
2. **Expected**: AI calls `get_employee_count` with `department="Engineering"`. Response includes:
   - Filtered count for that department
   - Department breakdown (may be a single department)
   - Pie chart (if multiple designations exist within the department)

#### 5.2.3 Employee Count by Status

1. Send: `How many employees have left the company?`
2. **Expected**: AI calls `get_employee_count` with `status="Left"`. Response includes:
   - Count of employees with "Left" status

#### 5.2.4 Attendance Summary

1. Send: `Show attendance summary for this month`
2. **Expected**: AI calls `get_attendance_summary`. Response includes:
   - Breakdown by status: Present, Absent, On Leave, Half Day, Work From Home
   - Total records and attendance rate (Present / (Present + Absent))
   - ECharts **bar chart** of attendance by status
   - Period used (defaults to current month)

#### 5.2.5 Attendance Summary by Department

1. Send: `Show attendance summary for HR department this month`
2. **Expected**: AI calls `get_attendance_summary` with `department="HR"`. Response includes:
   - Filtered attendance for that department only

#### 5.2.6 Leave Balance

1. Send: `What is the leave balance for [employee name or ID]?`
2. **Expected**: AI calls `get_leave_balance`. Response includes:
   - Leave type breakdown: allocated, consumed, balance for each type
   - Employee name and ID
   - Does **not** include expired allocations or Leave Without Pay types

#### 5.2.7 Leave Balance by Type

1. Send: `How many casual leaves does [employee name] have left?`
2. **Expected**: AI calls `get_leave_balance` with `leave_type="Casual Leave"`. Response includes:
   - Single leave type with allocated, consumed, balance

#### 5.2.8 Payroll Summary

1. Send: `Show payroll summary for this month`
2. **Expected**: AI calls `get_payroll_summary`. Response includes:
   - Total gross pay, total deductions, total net pay
   - Slip count and average per employee
   - ECharts **bar chart** with three bars (Gross Pay, Deductions, Net Pay)
   - Period defaults to current month
   - Currency and company fields in response

#### 5.2.9 Payroll Summary with Date Range

1. Send: `Show payroll summary from January to March 2026`
2. **Expected**: AI calls `get_payroll_summary` with explicit date range. Response uses the specified period.

#### 5.2.10 Department-wise Salary

1. Send: `Show department-wise salary distribution`
2. **Expected**: AI calls `get_department_wise_salary`. Response includes:
   - Departments with gross pay, deductions, net pay, slip count
   - ECharts **pie chart** of net pay by department
   - Period defaults to current month

#### 5.2.11 Employee Turnover

1. Send: `Show employee turnover for this year`
2. **Expected**: AI calls `get_employee_turnover`. Response includes:
   - New hires count (joined in period)
   - Exits count (left in period, status="Left" with relieving_date)
   - Current active employees
   - Turnover rate percentage: exits / (active + exits) * 100
   - ECharts **multi-series bar chart** (Joined vs Left)
   - Period defaults to current fiscal year

#### 5.2.12 Employee Turnover with Date Range

1. Send: `Show employee turnover for Q1 2026 (January to March)`
2. **Expected**: AI calls `get_employee_turnover` with explicit dates. Response uses the specified period.

---

### 5.3 Enhanced CRM Tools

> **Note**: CRM tools require ERPNext to be installed. All CRM tools use the `crm` category.

#### 5.3.1 Lead Statistics (Updated with ECharts)

1. Send: `Show me lead statistics`
2. **Expected**: AI calls `get_lead_statistics`. Response includes:
   - Total leads count
   - Status breakdown (Lead, Open, Replied, Opportunity, Converted, etc.)
   - ECharts **pie chart** of lead status distribution
   - Period defaults to current fiscal year
   - Blue tool indicator with "Lead Statistics" tag

#### 5.3.2 Opportunity Pipeline (Updated with ECharts)

1. Send: `Show opportunity pipeline`
2. **Expected**: AI calls `get_opportunity_pipeline`. Response includes:
   - List of opportunities with amounts and stages
   - Total pipeline value (with currency conversion for multi-currency opportunities)
   - ECharts **bar chart** of pipeline value grouped by sales stage
   - Currency and company fields in response

#### 5.3.3 Opportunity Pipeline Filtered

1. Send: `Show open opportunities`
2. **Expected**: AI calls `get_opportunity_pipeline` with `status="Open"`. Response filters to open opportunities only.

#### 5.3.4 Lead Conversion Rate

1. Send: `What is our lead conversion rate?`
2. **Expected**: AI calls `get_lead_conversion_rate`. Response includes:
   - Total leads in period
   - Converted leads (status: Opportunity, Converted, or Quotation)
   - Conversion rate percentage
   - Replied count and lost count
   - Period defaults to current fiscal year
   - Company name

#### 5.3.5 Lead Conversion Rate with Dates

1. Send: `What was the lead conversion rate in January 2026?`
2. **Expected**: AI uses explicit date range 2026-01-01 to 2026-01-31.

#### 5.3.6 Lead Source Analysis

1. Send: `Which lead sources are performing best?`
2. **Expected**: AI calls `get_lead_source_analysis`. Response includes:
   - List of sources with lead counts, sorted by count descending
   - Total number of distinct sources
   - ECharts **pie chart** of leads by source
   - Period defaults to current fiscal year

#### 5.3.7 Sales Funnel

1. Send: `Show the sales funnel`
2. **Expected**: AI calls `get_sales_funnel`. Response includes:
   - Four funnel stages with counts:
     - Leads created
     - Opportunities created
     - Quotations submitted (docstatus=1)
     - Sales Orders submitted (docstatus=1)
   - Conversion rates between stages:
     - Lead → Opportunity %
     - Opportunity → Quotation %
     - Quotation → Order %
     - Overall Lead → Order %
   - ECharts **horizontal bar chart** (funnel-style, widest at top)
   - Period defaults to current fiscal year

#### 5.3.8 Sales Funnel with Dates

1. Send: `Show the sales funnel for Q4 2025`
2. **Expected**: AI uses explicit date range (2025-10-01 to 2025-12-31).

#### 5.3.9 Opportunity by Stage

1. Send: `Show opportunities by sales stage`
2. **Expected**: AI calls `get_opportunity_by_stage`. Response includes:
   - Sales stages with count and total value per stage
   - Total opportunities and total pipeline value
   - ECharts **bar chart** of value by sales stage
   - Period defaults to current fiscal year
   - Currency and company fields

#### 5.3.10 Opportunity by Stage Filtered

1. Send: `Show open opportunities by stage`
2. **Expected**: AI calls `get_opportunity_by_stage` with `status="Open"`. Response filters to open opportunities only.

---

### 5.4 Conditional App Detection

These tests verify that tools are only loaded when their required app is installed.

#### 5.4.1 HRMS Tools Visibility

1. Verify HRMS app is installed: Run `bench --site test.local list-apps` — should include `hrms`.
2. In **Chatbot Settings**, ensure **Enable HRMS Tools** is checked.
3. Send: `How many employees do we have?`
4. **Expected**: AI uses `get_employee_count` tool. HRMS tools are available.
5. Verify in bench console:
   ```python
   from ai_chatbot.tools.registry import get_registered_tools
   tools = get_registered_tools()
   hrms_tools = [name for name, cat in tools.items() if cat == "hrms"]
   print(hrms_tools)
   # Should include: get_employee_count, get_attendance_summary, get_leave_balance,
   #                  get_payroll_summary, get_department_wise_salary, get_employee_turnover
   ```

#### 5.4.2 HRMS Tools Disabled via Settings

1. Go to **Chatbot Settings** → **uncheck** "Enable HRMS Tools" → Save.
2. Refresh the chatbot page.
3. Send: `How many employees do we have?`
4. **Expected**: AI does **not** have HRMS tools available. It should respond that it cannot access HR data or suggest checking ERPNext directly.
5. Re-enable HRMS Tools after testing.

#### 5.4.3 ERPNext Tools Conditional Loading

1. Verify ERPNext is installed: Run `bench --site test.local list-apps` — should include `erpnext`.
2. **Expected**: All CRM, selling, buying, finance, and inventory tools are loaded and available.
3. Verify in bench console:
   ```python
   from ai_chatbot.tools.registry import get_registered_tools
   tools = get_registered_tools()
   crm_tools = [name for name, cat in tools.items() if cat == "crm"]
   print(f"CRM tools: {len(crm_tools)}")  # Should be 6
   ```

#### 5.4.4 Tool Schema Verification

1. In bench console, verify the complete tool list:
   ```python
   from ai_chatbot.tools.registry import get_all_tools_schema
   schema = get_all_tools_schema()
   tool_names = [t["function"]["name"] for t in schema]
   print(sorted(tool_names))
   ```
2. **Expected**: HRMS tools (`get_employee_count`, `get_attendance_summary`, `get_leave_balance`, `get_payroll_summary`, `get_department_wise_salary`, `get_employee_turnover`) are present.
3. **Expected**: CRM tools (`get_lead_statistics`, `get_opportunity_pipeline`, `get_lead_conversion_rate`, `get_lead_source_analysis`, `get_sales_funnel`, `get_opportunity_by_stage`) are present.

---

### 5.5 Chart Rendering (Phase 5 Tools)

#### 5.5.1 Employee Count Pie Chart

1. Send: `Show employee distribution by department`
2. **Expected**: Pie chart renders inline with department segments. Hovering shows department name and count.

#### 5.5.2 Attendance Bar Chart

1. Send: `Show attendance summary`
2. **Expected**: Bar chart renders with one bar per status (Present, Absent, On Leave, etc.). Each bar has a distinct color.

#### 5.5.3 Payroll Summary Bar Chart

1. Send: `Show payroll summary`
2. **Expected**: Bar chart with three bars: Gross Pay, Deductions, Net Pay. Y-axis shows currency label.

#### 5.5.4 Department Salary Pie Chart

1. Send: `Show salary by department`
2. **Expected**: Pie chart with department segments showing net pay distribution.

#### 5.5.5 Employee Turnover Multi-Series Bar

1. Send: `Show employee turnover`
2. **Expected**: Multi-series bar chart with "Joined" and "Left" bars. Legend toggle works.

#### 5.5.6 Lead Statistics Pie Chart

1. Send: `Show lead statistics`
2. **Expected**: Pie chart with lead status segments. Hover tooltip shows status and count.

#### 5.5.7 Opportunity Pipeline Bar Chart

1. Send: `Show opportunity pipeline`
2. **Expected**: Bar chart with sales stages on x-axis and pipeline value on y-axis. Y-axis shows currency label.

#### 5.5.8 Lead Source Pie Chart

1. Send: `Show lead source analysis`
2. **Expected**: Pie chart with source name segments.

#### 5.5.9 Sales Funnel Horizontal Bar

1. Send: `Show sales funnel`
2. **Expected**: Horizontal bar chart with stages on y-axis (Leads at top, Sales Orders at bottom). Bars narrow from top to bottom in a funnel pattern.

#### 5.5.10 Opportunity by Stage Bar Chart

1. Send: `Show opportunities by stage`
2. **Expected**: Bar chart with sales stages and total value per stage.

---

### 5.6 Date & Company Defaults (Phase 5 Tools)

#### 5.6.1 HRMS Fiscal Year Default

1. Send: `Show employee turnover` (no dates)
2. **Expected**: Tool uses current fiscal year automatically. Response mentions the date range used.

#### 5.6.2 HRMS Current Month Default

1. Send: `Show attendance summary` (no dates)
2. **Expected**: Tool defaults to **current month** (not fiscal year). Response mentions the month range.

#### 5.6.3 HRMS Explicit Date Override

1. Send: `Show payroll summary for January 2026`
2. **Expected**: Tool uses 2026-01-01 to 2026-01-31.

#### 5.6.4 CRM Fiscal Year Default

1. Send: `What is the lead conversion rate?` (no dates)
2. **Expected**: Tool uses current fiscal year. Response mentions the date range.

#### 5.6.5 CRM Explicit Date Override

1. Send: `Show sales funnel for Q1 2026`
2. **Expected**: Tool uses 2026-01-01 to 2026-03-31.

#### 5.6.6 Company Default

1. Send: `Show employee count` (no company)
2. **Expected**: Tool uses user's default company. Response includes company name.

---

### 5.7 Error Handling (Phase 5)

#### 5.7.1 No HRMS Data

1. If no attendance records exist, send: `Show attendance summary`
2. **Expected**: AI responds with "no attendance data found" or similar. No broken chart renders.

#### 5.7.2 Invalid Employee for Leave Balance

1. Send: `Show leave balance for NONEXISTENT-EMPLOYEE`
2. **Expected**: Tool returns an error or empty result. AI relays that the employee was not found.

#### 5.7.3 No Salary Slips

1. If no submitted salary slips exist, send: `Show payroll summary`
2. **Expected**: AI responds with "no payroll data" or similar. Totals show as zero.

#### 5.7.4 No Leads

1. If no leads exist, send: `Show lead statistics`
2. **Expected**: Response shows total_leads: 0 with no chart (or an empty chart).

#### 5.7.5 No Opportunities

1. If no opportunities exist, send: `Show opportunity pipeline`
2. **Expected**: Response shows count: 0 with no chart.

---

## Phase 5A: UX & Accessibility — File Upload, Voice, @Mentions, Sidebar

### 5A.0 Prerequisites

```bash
# Rebuild frontend (new composables, updated components)
cd apps/ai_chatbot/frontend && npm run build

# Restart bench to pick up Python changes (api/files.py, updated chat.py, streaming.py)
bench start
```

**Browser requirements:**
- **Chrome/Edge/Safari**: Full support (voice input + output, file upload)
- **Firefox**: File upload and voice output work; voice input (SpeechRecognition) is NOT supported — mic button will be hidden

---

### 5A.1 File Upload Tests

#### 5A.1.1 Upload Button Visible

1. Open the chatbot.
2. **Expected**: A paperclip icon button (📎) appears to the left of the textarea.

#### 5A.1.2 Select Image File

1. Click the paperclip button.
2. Select an image file (JPEG, PNG, or WebP).
3. **Expected**: A file chip appears above the textarea with:
   - A small thumbnail preview of the image
   - The file name (truncated if long)
   - File size (e.g., "245 KB")
   - An X button to remove it

#### 5A.1.3 Select Non-Image File

1. Click the paperclip button.
2. Select a PDF or DOCX file.
3. **Expected**: A file chip appears with a file icon (not a thumbnail), the file name, and size.

#### 5A.1.4 Send Message with Image — Vision API

1. Attach an image (e.g., a screenshot of an ERPNext report or a photo of an invoice).
2. Type: `What do you see in this image?`
3. Click Send.
4. **Expected**:
   - The user message appears with the image attachment chip.
   - The AI analyzes the image content using Vision API (OpenAI or Claude).
   - The response describes what's in the image.

#### 5A.1.5 Send Message with PDF

1. Attach a PDF file.
2. Type: `I've attached a file for reference`
3. Click Send.
4. **Expected**: The AI acknowledges the file attachment. (Note: PDF text extraction is planned for Phase 7 — for now, the AI sees the file metadata but not the PDF content.)

#### 5A.1.6 Multiple Files (up to 5)

1. Click the paperclip button and select 3 image files.
2. **Expected**: All 3 file chips appear in the attachment preview strip.
3. Try adding 3 more (total would be 6).
4. **Expected**: An error message appears indicating the maximum of 5 files has been reached.

#### 5A.1.7 Drag-and-Drop

1. Drag an image file from your file manager onto the textarea area.
2. **Expected**: A "Drop files here" overlay with a dashed blue border appears.
3. Drop the file.
4. **Expected**: The file chip appears in the attachment preview strip.

#### 5A.1.8 File Too Large (>10MB)

1. Click the paperclip button and select a file larger than 10MB.
2. **Expected**: An error message appears: "File too large" or similar. The file is not added to the pending list.

#### 5A.1.9 Invalid File Type

1. Click the paperclip button and try to select a `.exe`, `.zip`, or other unsupported file type.
2. **Expected**: The file input dialog should filter these out (via `accept` attribute). If somehow selected, an error should appear.

#### 5A.1.10 Remove File from Pending List

1. Add a file attachment.
2. Click the X button on the file chip.
3. **Expected**: The file is removed from the attachment preview strip.

#### 5A.1.11 Attachment Display on Sent Message

1. Send a message with an image attachment.
2. **Expected**: The user message bubble displays the attachment chips (thumbnail for images, file icon for documents) below the message text.

#### 5A.1.12 File Upload with Streaming

1. Ensure streaming is enabled in Chatbot Settings.
2. Attach an image and send a message.
3. **Expected**: Files upload first, then the streaming response begins. Tokens stream normally with tool calls if applicable.

---

### 5A.2 Voice Input Tests

#### 5A.2.1 Microphone Button Visible (Supported Browsers)

1. Open the chatbot in Chrome, Edge, or Safari.
2. **Expected**: A microphone icon button appears to the right of the textarea (between textarea and Send button).

#### 5A.2.2 Microphone Button Hidden (Unsupported Browsers)

1. Open the chatbot in Firefox.
2. **Expected**: No microphone button appears. The textarea and Send button are still functional.

#### 5A.2.3 Start Recording

1. Click the microphone button.
2. **Expected**: Browser shows a microphone permission prompt (first time only).
3. Grant permission.
4. **Expected**: The mic button turns red with a pulsing animation (`animate-recording` — red glow effect).

#### 5A.2.4 Speak and See Transcript

1. While recording, speak clearly: "Show me this month's sales summary"
2. **Expected**: Interim text appears in the textarea in real-time as you speak. The text may change/correct itself as the speech recognition refines its output.

#### 5A.2.5 Stop Recording

1. Click the red mic button to stop recording.
2. **Expected**:
   - The mic button returns to its idle gray state.
   - The final transcript is in the textarea and is editable before sending.

#### 5A.2.6 Send Voice Message

1. After recording, click Send (or press Enter).
2. **Expected**: The message is sent. The payload includes `voiceInput: true` (used for auto-speak behavior).

#### 5A.2.7 Permission Denied

1. When the microphone permission prompt appears, click "Block" or "Deny".
2. **Expected**: An error message appears below the input (e.g., "Microphone access denied"). The mic button returns to idle state.

---

### 5A.3 Voice Output Tests

#### 5A.3.1 Listen Button on Assistant Messages

1. Send a text message and wait for the AI response.
2. **Expected**: Below the assistant message, next to the token count, there is a "Listen" button with a speaker icon.

#### 5A.3.2 Click Listen — Browser Speaks

1. Click the "Listen" button on an assistant message.
2. **Expected**: The browser's text-to-speech reads the response aloud. Markdown formatting is stripped (no "hash hash" for headers, no "asterisk" for bold).

#### 5A.3.3 Click Stop While Speaking

1. While the browser is speaking, click the button again (now shows "Stop" with a muted speaker icon).
2. **Expected**: Speech stops immediately. The button returns to "Listen" state.

#### 5A.3.4 Auto-Speak After Voice Input

1. Use voice input (mic button) to ask a question.
2. Send the message.
3. Wait for the AI response to complete (including streaming).
4. **Expected**: The AI response is automatically spoken aloud via text-to-speech, without clicking "Listen".

#### 5A.3.5 No Auto-Speak for Typed Messages

1. Type a message using the keyboard (do NOT use voice input).
2. Send the message and wait for the AI response.
3. **Expected**: The AI response is NOT automatically spoken. The "Listen" button is available for manual use.

#### 5A.3.6 Auto-Speak with Streaming

1. Ensure streaming is enabled.
2. Use voice input to send a message.
3. **Expected**: Auto-speak triggers **after** the stream ends (not during streaming). The complete response is spoken.

---

### 5A.4 Sidebar Toggle Tests

#### 5A.4.1 Toggle Button Visible

1. Open the chatbot.
2. **Expected**: In the header bar (left side, before the Bot icon), there is a sidebar toggle button with a panel icon (`PanelLeftClose` when sidebar is visible).

#### 5A.4.2 Collapse Sidebar

1. Click the toggle button.
2. **Expected**:
   - The sidebar smoothly collapses (width transitions to 0).
   - The chat area expands to full width.
   - The toggle icon changes to `PanelLeftOpen`.

#### 5A.4.3 Expand Sidebar

1. With the sidebar collapsed, click the toggle button again.
2. **Expected**: The sidebar smoothly re-expands to its original width (320px). Conversations list is visible.

#### 5A.4.4 Persistence Across Refresh

1. Collapse the sidebar.
2. Refresh the page (`F5` or `Ctrl+R`).
3. **Expected**: The sidebar remains collapsed after refresh (state persisted in `localStorage` key `ai_chatbot_sidebar`).
4. Expand the sidebar.
5. Refresh again.
6. **Expected**: The sidebar remains expanded.

---

### 5A.5 @Mention Autocomplete Tests

#### 5A.5.1 Trigger @Mention Dropdown

1. In the textarea, type `@`.
2. **Expected**: A dropdown appears above the textarea with 8 mention categories:
   - company, period, cost_center, department, warehouse, customer, item, accounting_dimension

#### 5A.5.2 Filter Categories

1. Type `@com`.
2. **Expected**: The dropdown filters to show only `@company` (and possibly `@cost_center` if "com" matches).

#### 5A.5.3 Select @company

1. Type `@` and click on `company` in the dropdown.
2. **Expected**: Your default company name is inserted into the textarea (e.g., "My Company Pvt Ltd"), replacing `@company`.

#### 5A.5.4 Select @period — Sub-Menu

1. Type `@` and click on `period`.
2. **Expected**: The dropdown changes to show period presets:
   - "This Week" (e.g., "2026-02-16 to 2026-02-22")
   - "This Month" (e.g., "2026-02-01 to 2026-02-28")
   - "Last Month" (e.g., "2026-01-01 to 2026-01-31")
   - "This Quarter" (e.g., "2026-01-01 to 2026-03-31")
   - "This FY" (e.g., "2025-04-01 to 2026-03-31")
   - "Last FY" (e.g., "2024-04-01 to 2025-03-31")
3. Click "This Month".
4. **Expected**: The date range string is inserted into the textarea.

#### 5A.5.5 Select @cost_center

1. Type `@` and click on `cost_center`.
2. **Expected**: The dropdown shows a list of cost centers from your ERPNext instance. Click one to insert it.

#### 5A.5.6 Search Within @customer

1. Type `@` and click on `customer`.
2. **Expected**: The dropdown shows customer names. The list is fetched from the backend.

#### 5A.5.7 @accounting_dimension

1. Type `@` and click on `accounting_dimension`.
2. **Expected**: The dropdown shows available accounting dimensions (e.g., Cost Center, Department, Project, or custom dimensions defined in ERPNext). If no accounting dimensions are configured, an empty list or "No matches found" appears.

#### 5A.5.8 Keyboard Navigation

1. Type `@` to open the dropdown.
2. Press **Arrow Down** — selection moves down.
3. Press **Arrow Up** — selection moves up.
4. Press **Enter** — selects the highlighted option.
5. Press **Escape** — closes the dropdown without selecting.

#### 5A.5.9 Click Outside Dropdown

1. Type `@` to open the dropdown.
2. Click anywhere outside the dropdown and textarea.
3. **Expected**: The dropdown closes.

---

### 5A.6 Prompt Suggestions Tests

#### 5A.6.1 Suggestions Visible for New Conversation

1. Create a new conversation (click "New Chat" in sidebar).
2. **Expected**: Above the input area, 4 suggestion chips are visible:
   - "Show me this month's sales summary"
   - "What are the top 10 customers by revenue?"
   - "Show accounts receivable aging"
   - "How many active employees do we have?"

#### 5A.6.2 Click Suggestion — Auto-Send

1. Click one of the suggestion chips (e.g., "Show me this month's sales summary").
2. **Expected**: The suggestion text is inserted into the textarea and automatically sent.

#### 5A.6.3 Suggestions Hidden After First Message

1. After the first message is sent, check the input area.
2. **Expected**: The suggestion chips are no longer visible.

#### 5A.6.4 No Suggestions for Existing Conversations

1. Switch to a conversation that already has messages.
2. **Expected**: No suggestion chips are shown above the input area.

---

### 5A.7 Error Handling

#### 5A.7.1 File Upload Server Error

1. Temporarily make the upload endpoint fail (e.g., by revoking file permissions or using a very large file that exceeds server limits).
2. Attach a file and send a message.
3. **Expected**: An error message appears. The text message is still sent without the attachment (graceful degradation).

#### 5A.7.2 Vision API Not Supported by Model

1. Configure a model that doesn't support vision (e.g., GPT-3.5-Turbo).
2. Attach an image and send.
3. **Expected**: The AI may not analyze the image but should still respond to the text. No crash or unhandled error.

#### 5A.7.3 Speech Recognition Network Error

1. Start voice recording, then disconnect from the network.
2. **Expected**: An error is displayed. The input field remains functional for typing.

---

## Phase 5B: Enterprise Analytics & Configuration

### 5B.0 Prerequisites

1. Run `bench --site test.local migrate` to apply new Chatbot Settings fields (query limits, prompt configuration).
2. Restart bench: `bench restart` (or `bench start` if using dev mode).
3. Verify new settings fields exist: go to **Chatbot Settings** and check for "Query Configuration" and "Prompt Configuration" sections.

---

### 5B.1 Permission Enforcement Tests

#### 5B.1.1 Admin User — All Tools Visible

1. Log in as **Administrator**.
2. Open the chatbot and ask: `What tools do you have?`
3. **Expected**: The AI lists all tool categories (selling, buying, inventory, CRM, finance, HRMS).
4. Verify in bench console:
   ```python
   import frappe
   frappe.set_user("Administrator")
   from ai_chatbot.tools.registry import get_all_tools_schema
   tools = get_all_tools_schema()
   print(f"Total tools: {len(tools)}")  # Should be 40+
   ```

#### 5B.1.2 Restricted User — Tools Filtered by Permission

1. Create or use a test user with limited roles (e.g., only "Accounts User" role — no "Sales User" or "Stock User").
2. Open chatbot as this user and ask about sales data.
3. **Expected**: The AI does not have selling tools available and cannot fetch sales data.
4. Verify in bench console:
   ```python
   import frappe
   frappe.set_user("restricted@example.com")
   from ai_chatbot.tools.registry import get_all_tools_schema
   tools = get_all_tools_schema()
   tool_names = [t["function"]["name"] for t in tools]
   print("get_sales_analytics" in tool_names)  # Should be False if user lacks Sales Invoice read
   print("get_payable_aging" in tool_names)     # Should be True if user has Purchase Invoice read
   ```

#### 5B.1.3 Tool Schema Verification — Restricted User Sees Fewer Tools

1. Compare the number of tools returned by `get_all_tools_schema()` for Administrator vs a restricted user.
2. **Expected**: The restricted user sees fewer tools — only those whose declared doctypes the user has read permission on.

#### 5B.1.4 Direct Tool Execution — Permission Error

1. In bench console, set a restricted user and try to execute a tool directly:
   ```python
   import frappe
   frappe.set_user("restricted@example.com")
   from ai_chatbot.tools.registry import execute_tool
   result = execute_tool("get_sales_analytics", {})
   print(result)  # Should be {"success": False, "error": "You do not have permission to access Sales Invoice"}
   ```
2. **Expected**: Returns a permission error, not sales data.

#### 5B.1.5 Permission Error Message in Chat

1. If a restricted user somehow triggers a tool they lack permission for, the AI should relay the error clearly.
2. **Expected**: The AI says something like "You don't have permission to access this data" — no unhandled exceptions.

---

### 5B.2 Accounting Dimension Tests

#### 5B.2.1 AR Aging Filtered by Cost Center

1. Ask: `Show me receivable aging for cost center "Main - TC"`
2. **Expected**: The AI calls `get_receivable_aging` with `cost_center="Main - TC"`. Results are filtered to only invoices matching that cost center.
3. Verify in bench console:
   ```python
   from ai_chatbot.tools.finance.receivables import get_receivable_aging
   result = get_receivable_aging(cost_center="Main - TC")
   print(result)  # Should show filtered results
   ```

#### 5B.2.2 Profitability Filtered by Department

1. Ask: `Show me profitability by customer for the Sales department`
2. **Expected**: The AI calls `get_profitability_by_customer` with `department="Sales"`. Only invoices tagged to the Sales department are included.

#### 5B.2.3 Budget vs Actual Filtered by Project

1. Ask: `What's the budget variance for Project Alpha?`
2. **Expected**: The AI calls `get_budget_vs_actual` with `project="Project Alpha"`. Results show budget performance for that project only.

#### 5B.2.4 Cash Flow Filtered by Cost Center

1. Ask: `Show me cash flow for cost center "Main - TC"`
2. **Expected**: The AI calls `get_cash_flow_statement` with `cost_center="Main - TC"`. Payment entries are filtered by cost center.

#### 5B.2.5 No Dimension Filter — Returns All Data

1. Ask: `Show me receivable aging`  (no dimension mentioned)
2. **Expected**: The AI calls `get_receivable_aging` without dimension parameters. All data is returned — dimension params are optional and default to None.

#### 5B.2.6 System Prompt Mentions Dimensions

1. Check that the system prompt includes dimension filtering context:
   ```python
   from ai_chatbot.core.prompts import build_system_prompt
   prompt = build_system_prompt()
   print("cost_center" in prompt or "dimension" in prompt.lower())  # Should be True
   ```

---

### 5B.4 CFO Reporting Tests

#### 5B.4.1 Financial Overview

1. Ask: `Give me a financial overview` or `Show me the key financial metrics`
2. **Expected**: The AI calls `get_financial_overview` and returns:
   - Revenue, COGS, gross profit, net profit
   - Cash position (bank balance)
   - Total AR and AP outstanding
   - A bar chart showing these KPIs
3. Verify in bench console:
   ```python
   from ai_chatbot.tools.finance.cfo import get_financial_overview
   result = get_financial_overview()
   print(list(result.keys()))  # Should include: revenue, cogs, gross_profit, net_profit, cash_position, ar_outstanding, ap_outstanding, echart_option
   ```

#### 5B.4.2 CFO Dashboard — Comprehensive Report

1. Ask: `Show me the CFO dashboard` or `Give me a full financial dashboard`
2. **Expected**: The AI calls `get_cfo_dashboard` and returns a structured report with sections:
   - Financial highlights (revenue, profit, cash)
   - KPIs — financial (gross margin %, net margin %), operational (DSO, DPO, DIO, CCC), liquidity (current ratio, quick ratio)
   - Cash flow summary (operating, investing, financing)
   - Receivables and payables aging summaries
   - Budget variance summary
3. Verify in bench console:
   ```python
   from ai_chatbot.tools.finance.cfo import get_cfo_dashboard
   result = get_cfo_dashboard()
   print(list(result.keys()))  # Should include: financial_highlights, kpis, cash_flow, receivables_summary, payables_summary, budget_summary
   ```

#### 5B.4.3 Monthly Comparison — MoM Variance

1. Ask: `Show me month-over-month comparison for the last 3 months`
2. **Expected**: The AI calls `get_monthly_comparison(months=3)` and returns:
   - Monthly revenue, expenses, net profit for each of the last 3 months
   - Month-over-month variance (amount and %)
   - A multi-series line chart
3. Verify in bench console:
   ```python
   from ai_chatbot.tools.finance.cfo import get_monthly_comparison
   result = get_monthly_comparison(months=3)
   print(f"Months: {len(result.get('months', []))}")  # Should be 3
   print("echart_option" in result)  # Should be True
   ```

#### 5B.4.4 CFO Dashboard with No Data

1. Use a company with no transactions.
2. Ask for the CFO dashboard.
3. **Expected**: Returns zeros/empty values gracefully — no crashes or unhandled exceptions.

---

### 5B.5 Multi-Company / Consolidation Tests

#### 5B.5.1 Parent Company Detection in System Prompt

1. Set up a company hierarchy (parent company with subsidiaries) in ERPNext.
2. Log in as a user whose default company is the parent company.
3. Verify the system prompt includes consolidation context:
   ```python
   from ai_chatbot.core.prompts import build_system_prompt
   prompt = build_system_prompt()
   print("subsidiaries" in prompt.lower() or "parent company" in prompt.lower())  # Should be True
   ```

#### 5B.5.2 Non-Parent Company — No Consolidation Context

1. Set the user's default company to a company with no subsidiaries.
2. Verify the system prompt does NOT include consolidation/subsidiary mentions:
   ```python
   from ai_chatbot.core.prompts import build_system_prompt
   prompt = build_system_prompt()
   print("subsidiaries" in prompt.lower())  # Should be False
   ```

#### 5B.5.3 Consolidation Functions in Bench Console

1. Verify helper functions work:
   ```python
   from ai_chatbot.core.consolidation import is_parent_company, get_child_companies
   print(is_parent_company("Your Parent Company"))  # True if it has children
   print(get_child_companies("Your Parent Company"))  # List of subsidiary company names
   ```

---

### 5B.6 Configurable Prompts Tests

#### 5B.6.1 Custom Persona

1. Go to Chatbot Settings → Prompt Configuration.
2. Set **AI Persona** to: `a friendly CFO assistant named FinBot`
3. Open the chatbot and ask: `Who are you?`
4. **Expected**: The AI identifies itself as "FinBot" or references the custom persona.

#### 5B.6.2 Response Language

1. Set **Response Language** to "Hindi" (or any non-English language).
2. Ask a question in the chatbot.
3. **Expected**: The AI responds in the configured language.
4. Set back to blank (default English) and verify normal behavior.

#### 5B.6.3 Custom System Prompt

1. Set **Custom System Prompt** to: `Always end your responses with "— FinBot"`
2. Ask a question.
3. **Expected**: The AI follows the custom instruction and appends "— FinBot" to responses.

#### 5B.6.4 Default Behavior — All Blank

1. Leave all prompt configuration fields blank.
2. **Expected**: The AI uses the default persona ("an intelligent ERPNext business assistant") and responds in English. Standard behavior unchanged.

---

### 5B.7 Configurable Constants Tests

#### 5B.7.1 Change Default Query Limit

1. Go to Chatbot Settings → Query Configuration.
2. Set **Default Query Limit** to 5.
3. Ask: `Show me stock movement` (which uses the default query limit).
4. **Expected**: The result returns at most 5 items.
5. Verify in bench console:
   ```python
   from ai_chatbot.core.config import get_query_limit
   print(get_query_limit())  # Should be 5
   ```

#### 5B.7.2 Max Query Limit Caps Requests

1. Set **Max Query Limit** to 25.
2. Ask for top 50 customers.
3. **Expected**: The result is capped at 25, even though 50 was requested.
4. Verify in bench console:
   ```python
   from ai_chatbot.core.config import get_query_limit
   print(get_query_limit(50))  # Should be 25 (capped at max)
   ```

#### 5B.7.3 Default Values When Fields Are Empty

1. Clear all query configuration fields (set to 0 or blank).
2. Verify the system uses fallback defaults from constants:
   ```python
   from ai_chatbot.core.config import get_query_limit, get_top_n_limit
   print(get_query_limit())    # Should be 20 (DEFAULT_QUERY_LIMIT)
   print(get_top_n_limit())    # Should be 10 (DEFAULT_TOP_N_LIMIT)
   ```

---

### 5B.8 Plugin System Tests

#### 5B.8.1 Verify Hooks Configuration

1. Check that `hooks.py` declares the tool module hook:
   ```python
   import ai_chatbot.hooks as hooks
   print(hasattr(hooks, "ai_chatbot_tool_modules"))  # Should be True
   ```

#### 5B.8.2 External App Can Register Tools via Hooks

1. In another Frappe app's `hooks.py`, add:
   ```python
   ai_chatbot_tool_modules = ["my_app.chatbot_tools"]
   ```
2. Create `my_app/chatbot_tools.py` with a `@register_tool(...)` decorated function.
3. Restart bench and verify the tool appears in the registry:
   ```python
   from ai_chatbot.tools.registry import get_registered_tools
   print(get_registered_tools())  # Should include the new tool
   ```

#### 5B.8.3 Failed Plugin Import — Logged, Doesn't Crash

1. Add a non-existent module path to the hook: `ai_chatbot_tool_modules = ["nonexistent.module"]`
2. Restart bench. The chatbot should still work.
3. Check Error Log (`/app/error-log`) for: `Failed to load AI Chatbot tool plugin: nonexistent.module`
4. **Expected**: Other tools still load and function normally.

#### 5B.8.4 Dynamic Category Registration

1. In bench console, register a custom category:
   ```python
   from ai_chatbot.tools.registry import register_tool_category
   register_tool_category("manufacturing", settings_field=None)
   ```
2. **Expected**: Tools registered with `category="manufacturing"` will now be included in the schema (always enabled since `settings_field=None`).

---

## Pre-Phase 6A: Favicon, Logo & User Avatar

### Pre-6A.0 Prerequisites

```bash
# Rebuild frontend (updated ChatMessage, ChatView with avatar/logo)
cd apps/ai_chatbot/frontend && npm run build

# Restart bench to pick up Python changes (updated get_settings endpoint)
bench start
```

---

### Pre-6A.1 Favicon

#### Pre-6A.1.1 Favicon Visible in Browser Tab

1. Open the chatbot: `http://<SITE>:8005/ai-chatbot`
2. **Expected**: The browser tab shows the AI Chatbot favicon (purple/teal chat bubble icon) instead of the default Frappe/browser icon.
3. Check the page source: the `<head>` should contain:
   ```html
   <link rel="icon" type="image/svg+xml" href="/assets/ai_chatbot/frontend/favicon.svg">
   ```

---

### Pre-6A.2 AI Message Avatar (Logo)

#### Pre-6A.2.1 AI Messages Show Logo

1. Open the chatbot and send a message (e.g., `Hello`).
2. Wait for the AI response.
3. **Expected**: The AI message displays the app logo SVG (purple gradient circle with chat bubble + neural network icon) as a 32×32 rounded avatar — replacing the old "AI" text badge.

#### Pre-6A.2.2 Streaming Message Shows Logo

1. Ensure streaming is enabled in Chatbot Settings.
2. Send a message that produces a longer response (e.g., `Explain the key features of ERPNext`).
3. **Expected**: While the response is streaming, the streaming message also shows the app logo avatar (not "AI" text).

#### Pre-6A.2.3 Logo Consistent Across Messages

1. Send several messages in a conversation.
2. Scroll through the message history.
3. **Expected**: Every AI message (both streamed and loaded from history) displays the same logo avatar.

---

### Pre-6A.3 User Avatar

#### Pre-6A.3.1 User Avatar from Profile Image

1. Ensure the current user has a profile image set:
   - Go to **User Settings** (`/app/user/<your-email>`) → **Profile** → set an image.
2. Open the chatbot and send a message.
3. **Expected**: The user message bubble displays the user's profile image as a 32×32 rounded avatar.

#### Pre-6A.3.2 User Initials Fallback (No Avatar)

1. Log in as a user who does **not** have a profile image set (or remove the current user's image).
2. Open the chatbot and send a message.
3. **Expected**: The user message bubble displays the user's initials (e.g., "SK" for "Sanjay Kumar", "A" for "Administrator") in a rounded badge with semi-transparent white background.

#### Pre-6A.3.3 User Info from API

1. Open browser DevTools → Network tab.
2. Load/refresh the chatbot page.
3. Find the `get_settings` API call.
4. **Expected**: The response JSON includes a `user` object:
   ```json
   {
     "success": true,
     "settings": { ... },
     "user": {
       "fullname": "Sanjay Kumar",
       "avatar": "/files/user-avatar.png"
     }
   }
   ```
   - `avatar` will be `null` if no profile image is set.
   - `fullname` should match the logged-in user's full name.

#### Pre-6A.3.4 Avatar Across All Messages

1. Send multiple messages in a conversation.
2. Scroll through the conversation.
3. **Expected**: Every user message (both newly sent and loaded from history) displays the same avatar (image or initials).

---

## Phase 6: Settings Overhaul, Gemini Provider & Token Optimization

### 6.0 Prerequisites

```bash
# Migrate database (new fields + Token Usage DocType)
bench --site <SITE> migrate

# Rebuild frontend
cd apps/ai_chatbot/frontend && npm run build

# Restart bench
bench start
```

---

### 6.1 Chatbot Settings Overhaul

#### 6.1.1 Tabbed Interface

1. Go to **Chatbot Settings** (`/app/chatbot-settings`).
2. **Expected**: The settings page shows 5 tabs:
   - **API Configuration** — AI Provider dropdown, API Key, Model, Temperature, Max Tokens, Max Context Messages
   - **Tools** — CRM, Sales, Purchase, Finance, Inventory, HRMS checkboxes + Write Operations
   - **Query Configuration** — Default Query Limit, Default Top-N Limit, Max Query Limit
   - **Prompts** — AI Persona, Response Language, Custom System Prompt, Custom Instructions
   - **Streaming** — Enable Streaming checkbox

#### 6.1.2 Unified Provider Dropdown

1. In the **API Configuration** tab, set **AI Provider** to "OpenAI".
2. Enter a valid OpenAI API key in the **API Key** field.
3. Leave **Model** blank (should default to `gpt-4o`).
4. Save the settings.
5. **Expected**: Settings save without error. The API Key field is a Password field (encrypted).

#### 6.1.3 Switch Provider to Claude

1. Change **AI Provider** to "Claude".
2. Enter a valid Claude API key.
3. Set **Model** to `claude-sonnet-4-5-20250929`.
4. Save.
5. Open the chatbot and send a message.
6. **Expected**: Response comes from Claude (check response style or model mentions).

#### 6.1.4 Legacy Compatibility

1. If you have existing settings with `openai_enabled=1` and `openai_api_key` set (legacy fields):
   - Clear the new **API Key** field.
   - **Expected**: The system falls back to legacy `openai_api_key` for OpenAI provider.
2. This is backward-compatible — existing deployments continue to work without re-configuration.

---

### 6.2 Gemini Provider

#### 6.2.1 Gemini Configuration

1. In **Chatbot Settings**, set **AI Provider** to "Gemini".
2. Enter a valid Google AI Studio API key.
3. Leave **Model** blank (defaults to `gemini-2.5-flash`).
4. Save.

#### 6.2.2 Gemini Chat Response

1. Open the chatbot and send: `Hello, what model are you?`
2. **Expected**: Response from Gemini model. The header dropdown should show "Gemini".

#### 6.2.3 Gemini with Tools

1. Send: `What are my top 5 customers by sales?`
2. **Expected**: Gemini calls the appropriate tool and returns results (same as OpenAI — uses OpenAI-compatible endpoint).

#### 6.2.4 Gemini Streaming

1. Ensure **Enable Streaming** is checked.
2. Send a message that generates a longer response.
3. **Expected**: Tokens stream in real-time (same as OpenAI streaming).

#### 6.2.5 Provider Selector in Header

1. Open the chatbot.
2. Click the provider dropdown in the header.
3. **Expected**: Three options visible — OpenAI, Claude, Gemini.
4. Select Gemini from the dropdown.
5. Start a new conversation.
6. **Expected**: New conversation uses Gemini as the provider.

---

### 6.3 Financial Analysis Behaviour

#### 6.3.1 Finance Prompt Active

1. Ensure **Enable Finance Tools** is checked in settings.
2. Send: `What is our accounts receivable aging?`
3. **Expected**: The response includes:
   - Professional financial terminology (DSO, aging buckets)
   - Comparison context (if available)
   - Risk highlights for overdue amounts
   - Suggested next steps

#### 6.3.2 Finance Prompt Inactive

1. Uncheck **Enable Finance Tools** in settings.
2. Send a finance question.
3. **Expected**: The AI responds generically (no CFO-style analysis) because finance tools and behaviour are disabled.

---

### 6.4 Token Optimization

#### 6.4.1 History Trimming

1. In **Chatbot Settings**, set **Max Context Messages** to `5`.
2. Send 10+ messages in a single conversation.
3. Open browser DevTools → Network → check the `send_message` request payload.
4. **Expected**: The conversation remains functional even with the context limit. Earlier messages are trimmed but the AI still responds coherently.

#### 6.4.2 Unlimited Context

1. Set **Max Context Messages** to `0` (unlimited).
2. Send several messages.
3. **Expected**: All messages are included in context (no trimming).

#### 6.4.3 Tool Result Compression

1. Send a query that returns a large dataset (e.g., `List all sales invoices this year`).
2. Follow up with another question.
3. **Expected**: The follow-up works correctly — tool results in history are compressed (echart_option removed, data truncated) to save tokens.

---

### 6.5 Cost Monitoring

#### 6.5.1 Token Usage Recorded

1. Send a message via the chatbot (non-streaming).
2. Go to **Chatbot Token Usage** list view (`/app/chatbot-token-usage`).
3. **Expected**: A new record exists with:
   - User = your user
   - Provider = the selected provider
   - Model = the model used
   - Prompt Tokens, Completion Tokens, Total Tokens filled
   - Estimated Cost > 0 (for known models)
   - Date = today

#### 6.5.2 Streaming Token Tracking

1. Send a message with streaming enabled.
2. Check the Token Usage list.
3. **Expected**: A new record for the streaming request (note: streaming uses estimated tokens).

#### 6.5.3 Cost Estimation

1. Check the **Estimated Cost** column for different providers.
2. **Expected**: OpenAI GPT-4o costs differ from Claude Sonnet, which differ from Gemini Flash (Gemini should be cheapest).

### 6.6 Source File Header Policy

#### 6.6.1 Python File Headers

1. Open any Python file in the project (e.g., `ai_chatbot/api/chat.py`, `ai_chatbot/core/token_tracker.py`, `ai_chatbot/tools/crm.py`).
2. **Expected**: The file starts with:
   ```python
   # Copyright (c) 2026, Sanjay Kumar and contributors
   # For license information, please see license.txt
   ```
3. Check DocType-generated files (e.g., `ai_chatbot/chatbot/doctype/chatbot_settings/chatbot_settings.py`).
4. **Expected**: Same header with "Sanjay Kumar" (not "Your Company") and year 2026.

#### 6.6.2 JavaScript File Headers

1. Open any JavaScript file (e.g., `frontend/src/utils/api.js`, `frontend/src/utils/markdown.js`).
2. **Expected**: The file starts with:
   ```javascript
   // Copyright (c) 2026, Sanjay Kumar and contributors
   // For license information, please see license.txt
   ```

#### 6.6.3 Vue File Headers

1. Open any Vue single-file component (e.g., `frontend/src/pages/ChatView.vue`, `frontend/src/components/ChatMessage.vue`).
2. **Expected**: The file starts with:
   ```html
   <!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
   <!-- For license information, please see license.txt -->
   ```

#### 6.6.4 Spot-Check Coverage

1. Run a quick spot-check across the project:
   ```bash
   # Count Python files missing the header
   grep -rL "Copyright (c) 2026, Sanjay Kumar" --include="*.py" ai_chatbot/ | grep -v __pycache__ | grep -v ".pyc"

   # Count JS files missing the header
   grep -rL "Copyright (c) 2026, Sanjay Kumar" --include="*.js" frontend/src/

   # Count Vue files missing the header
   grep -rL "Copyright (c) 2026, Sanjay Kumar" --include="*.vue" frontend/src/
   ```
2. **Expected**: No files returned (all source files have the header).
3. **Note**: Empty `__init__.py` files may legitimately be header-only (just the 2-line copyright).

---

## Troubleshooting

### File upload not working

1. Check browser console for errors during upload (look for failed `POST` to `/api/method/ai_chatbot.api.files.upload_chat_file`).
2. Verify the file size is under 10MB.
3. Verify the MIME type is in the allowed list (images, PDF, CSV, XLSX, DOCX, TXT).
4. Check Error Log (`/app/error-log`) for server-side upload errors.
5. Verify the conversation exists and belongs to the current user (ownership check).

### Microphone button not appearing

1. This is expected in Firefox — Web Speech API (`SpeechRecognition`) is not supported.
2. In Chrome/Edge/Safari, ensure the page is served over HTTPS or localhost. SpeechRecognition requires a secure context.
3. Check browser console for `SpeechRecognition is not defined` errors.

### Voice output not speaking

1. Verify browser supports `SpeechSynthesis`: open DevTools console and type `window.speechSynthesis` — should not be `undefined`.
2. Some browsers require a user interaction before first speech — click the "Listen" button (not triggered programmatically from page load).
3. Check if the system has voice packs installed (some Linux distros need `espeak` or similar).

### Sidebar toggle state not persisting

1. Check `localStorage` in DevTools: Application → Local Storage → look for key `ai_chatbot_sidebar`.
2. Value should be `collapsed` or `expanded`.
3. If localStorage is blocked (privacy mode), the state won't persist.

### @mention dropdown not showing

1. Ensure you type `@` at the start of input or after a space. Typing `@` in the middle of a word (e.g., `email@`) will not trigger the dropdown.
2. Check browser console for errors from the `get_mention_values` API call.
3. Verify the backend endpoint works: test in bench console:
   ```python
   from ai_chatbot.api.chat import get_mention_values
   print(get_mention_values("company"))
   print(get_mention_values("period"))
   ```

### Streaming not working (message appears all at once)

1. **Check Socket.IO connection**: Open DevTools Console and look for:
   - `[AI Chatbot] Socket.IO connecting to: http://test.local:9005 (namespace: /test.local)` (dev mode) or `http://test.local (namespace: /test.local)` (nginx).
   - `[AI Chatbot] Socket.IO connected` — confirms connection is established.
2. **Check `common_site_config.json`**: Ensure `socketio_port` is set (default: `9000`, your bench uses `9005`).
3. **Check background workers**: The streaming job runs as a background job via `frappe.enqueue`. Ensure `bench start` is running (it starts workers automatically).
4. **Check Redis**: Socket.IO relies on Redis Pub/Sub. Ensure Redis is running: `redis-cli -p 13005 ping` should return `PONG`.
5. **Check background jobs**: Go to `/app/background-jobs` in Frappe desk and verify the streaming job is being processed (not stuck in queue).

### Socket.IO connection error (`xhr poll error`)

1. **Check the URL in console**: Look for `[AI Chatbot] Socket.IO connecting to:` — verify the URL looks correct:
   - **With nginx**: `http://test.local` (same origin, nginx proxies `/socket.io` to the socketio process)
   - **Without nginx**: `http://test.local:9005` (direct connection to socketio port)
2. **Access via the site name**: Make sure you access the chatbot via the Frappe site name (e.g., `http://test.local/ai-chatbot` or `http://test.local:8005/ai-chatbot`), NOT via `localhost`. The Socket.IO auth middleware checks that the request origin matches the host.
3. **With nginx — check CORS**: If you see "Cross-Origin Request Blocked", ensure your nginx config has the `location /socket.io` proxy block. The Socket.IO client connects to the same origin as the page, so nginx must proxy `/socket.io` requests to the socketio process.
4. **Verify socketio process**: Check `bench start` output for the socketio line like `Realtime service listening on: ws://0.0.0.0:9005`.
5. **Check if port is accessible**: `curl http://test.local:9005/socket.io/?EIO=4&transport=polling` — should return a JSON response (Socket.IO handshake), not a connection error.
6. **Check `/etc/hosts`**: Ensure your site name resolves: `ping test.local` should return `127.0.0.1`.

### Cross-Origin Request Blocked (with nginx)

If you're using nginx and see CORS errors for `/socket.io`:
1. Ensure your nginx site config has a `location /socket.io` block that proxies to the socketio process.
2. Example nginx config for Socket.IO:
   ```nginx
   location /socket.io {
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
       proxy_set_header X-Frappe-Site-Name $host;
       proxy_set_header Origin $scheme://$http_host;
       proxy_set_header Host $host;
       proxy_pass http://127.0.0.1:9005;
   }
   ```
3. After updating nginx config: `sudo nginx -t && sudo systemctl reload nginx`

### Typing indicator not showing

1. The typing indicator shows when `isLoading` is `true` and no streaming content has arrived yet.
2. If it never appears, check if the `send_message` HTTP request is failing (check Network tab for errors).

### "AI is thinking..." shows but no response

1. Check the Error Log in Frappe (`/app/error-log`) for streaming errors.
2. Check the background job queue: `/app/background-jobs` — look for failed jobs.
3. Verify the AI provider API key is valid and the provider is reachable.
4. Check if workers are running: `bench doctor` shows worker status.

### AI doesn't know company/fiscal year (Phase 3)

1. The system prompt injects user context (company, currency, fiscal year) dynamically.
2. If the AI says it doesn't know your company, check:
   - Is a **default company** set for the user? Go to **User Settings** → **Defaults** → **Company**.
   - Or set a global default: `bench --site test.local set-config default_company "Your Company Name"`.
3. If fiscal year is wrong, check **Fiscal Year** DocType in ERPNext — ensure a fiscal year exists that covers today's date and is linked to your company.

### Create/Update tools not appearing (Phase 3)

1. Ensure **Enable Write Operations** is checked in Chatbot Settings.
2. After changing settings, **refresh** the chatbot page (the tool schema is fetched on page load).
3. Check the Error Log (`/app/error-log`) — if a tool module fails to import, the registry may be incomplete.
4. Verify in bench console:
   ```python
   from ai_chatbot.tools.registry import get_registered_tools
   print(get_registered_tools())
   # Should include: create_lead, create_opportunity, create_todo,
   #                  update_lead_status, update_opportunity_status, update_todo,
   #                  search_customers, search_items, search_documents
   ```

### AI creates records without asking for confirmation (Phase 3)

1. The confirmation pattern is prompt-driven — the system prompt instructs the AI to confirm before writes.
2. If the AI skips confirmation, this is an LLM behavioral issue, not a code bug.
3. The tool descriptions also include "IMPORTANT: Always confirm details with the user before calling this tool."
4. Try switching to a more instruction-following model (e.g., GPT-4o instead of GPT-3.5-Turbo).

### Permission error when creating/updating records (Phase 3)

1. The operations layer checks `frappe.has_permission()` before every write.
2. If you get "You do not have permission", ensure the logged-in user has the appropriate role (e.g., "Sales User" for Leads, "System Manager" for full access).
3. Check role permissions: **Setup** → **Role Permission Manager** → search for the DocType.

### Amber indicator not showing for write operations (Phase 3)

1. The amber "Document Operations Performed" indicator appears when tool calls have names starting with `create_` or `update_`.
2. If you see write tool calls in the blue indicator instead, hard-refresh the page (`Ctrl+Shift+R`) to clear cached frontend assets.
3. Ensure the frontend was rebuilt: `cd apps/ai_chatbot/frontend && npm run build`.

### Charts not rendering (Phase 4)

1. Ensure echarts is installed: `cd apps/ai_chatbot/frontend && npm ls echarts` — should show `echarts@6.x.x`.
2. Rebuild frontend after installing: `npm run build`.
3. Hard-refresh the browser (`Ctrl+Shift+R`) to clear cached bundles.
4. Check browser console for errors — look for "echarts is not defined" or chunk loading failures.
5. Verify the tool response includes `echart_option` — check Error Log or bench console:
   ```python
   from ai_chatbot.tools.finance.receivables import get_receivable_aging
   result = get_receivable_aging()
   print("echart_option" in result.get("data", {}))  # Should be True
   ```

### Finance tools not appearing (Phase 4)

1. Ensure **Enable Finance Tools** is checked in Chatbot Settings.
2. Refresh the chatbot page after changing settings.
3. Verify tools are registered:
   ```python
   from ai_chatbot.tools.registry import get_registered_tools
   tools = get_registered_tools()
   finance_tools = [t for t in tools if t.get("category") == "finance"]
   print(f"Finance tools: {len(finance_tools)}")  # Should be 17
   ```
4. Check Error Log (`/app/error-log`) for import errors in finance modules.

### Finance tools return empty results (Phase 4)

1. Finance tools query **posted** (submitted) documents. Draft invoices are excluded.
2. Verify you have submitted Sales Invoices: `/app/sales-invoice?docstatus=1`.
3. Verify you have submitted Purchase Invoices: `/app/purchase-invoice?docstatus=1`.
4. Budget tools require Budget records: `/app/budget`.
5. Working capital tools use GL Entry balances — ensure journal entries are posted.
6. Check that the fiscal year covers today's date: `/app/fiscal-year`.

### HRMS tools not appearing (Phase 5)

1. Ensure the **HRMS app** is installed: `bench --site test.local list-apps` — should include `hrms`.
2. If HRMS is not installed, HRMS tools will **not** be loaded into the registry (by design).
3. Ensure **Enable HRMS Tools** is checked in Chatbot Settings.
4. Refresh the chatbot page after changing settings.
5. Verify tools are registered:
   ```python
   from ai_chatbot.tools.registry import get_registered_tools
   tools = get_registered_tools()
   hrms_tools = [name for name, cat in tools.items() if cat == "hrms"]
   print(f"HRMS tools: {len(hrms_tools)}")  # Should be 6
   ```
6. Check Error Log (`/app/error-log`) for import errors in `ai_chatbot.tools.hrms`.

### HRMS tools return empty results (Phase 5)

1. HRMS tools query ERPNext/HRMS DocTypes. Ensure you have data:
   - **Employee records**: `/app/employee` — at least some Active employees.
   - **Attendance records**: `/app/attendance` — attendance marked for the period.
   - **Leave Allocations**: `/app/leave-allocation?docstatus=1` — submitted allocations for the current period.
   - **Salary Slips**: `/app/salary-slip?docstatus=1` — submitted salary slips.
2. Payroll tools only count **submitted** salary slips (docstatus=1). Draft slips are excluded.
3. Leave balance checks `total_leaves_allocated` from active allocations (current date within from_date/to_date).
4. Employee turnover counts `date_of_joining` (new hires) and `relieving_date` with status="Left" (exits).

### CRM tools not appearing (Phase 5)

1. Ensure **ERPNext** is installed: `bench --site test.local list-apps` — should include `erpnext`.
2. If ERPNext is not installed, CRM, selling, buying, finance, and inventory tools will **not** load.
3. Ensure **Enable CRM Tools** is checked in Chatbot Settings.
4. Verify:
   ```python
   from ai_chatbot.tools.registry import get_registered_tools
   tools = get_registered_tools()
   crm_tools = [name for name, cat in tools.items() if cat == "crm"]
   print(f"CRM tools: {len(crm_tools)}")  # Should be 6
   ```

### Tools hidden unexpectedly (Phase 5B — Permissions)

1. Phase 5B added doctype-based permission checks. If a tool suddenly disappears for a user, the user likely lacks **read** permission on one of the tool's declared doctypes.
2. Check which doctypes a tool requires:
   ```python
   from ai_chatbot.tools.registry import get_tool_info
   info = get_tool_info("get_sales_analytics")
   print(info["doctypes"])  # e.g., ["Sales Invoice"]
   ```
3. Check user permissions for those doctypes:
   ```python
   import frappe
   frappe.set_user("user@example.com")
   print(frappe.has_permission("Sales Invoice", "read"))  # True or False
   ```
4. Fix by granting the appropriate role (e.g., "Sales User" for Sales Invoice access).

### Dimension filters not working (Phase 5B)

1. Dimension filtering is optional — if no `cost_center`, `department`, or `project` is passed, all data is returned.
2. Verify the dimension value exists in ERPNext: `/app/cost-center`, `/app/department`, `/app/project`.
3. Verify the field exists on the doctype being queried. The `apply_dimension_filters` helper only applies filters for fields that exist on the table's meta.
4. Test in bench console:
   ```python
   from ai_chatbot.tools.finance.receivables import get_receivable_aging
   result = get_receivable_aging(cost_center="Main - TC")
   print(result)
   ```

### CFO dashboard returns zeros (Phase 5B)

1. The CFO dashboard aggregates data from multiple sources (Sales Invoice, Purchase Invoice, GL Entry, Payment Entry, Budget).
2. Ensure you have **submitted** transactions for the current fiscal year.
3. `cash_position` requires GL entries in bank/cash accounts. Check that bank accounts exist: `/app/account?account_type=Bank`.
4. Budget data requires Budget records linked to cost centers. Check: `/app/budget`.
5. KPIs like DSO, DPO, DIO require both revenue and outstanding receivables/payables.

### Query limits not applying (Phase 5B)

1. After changing query limits in Chatbot Settings, **restart bench** — the settings object is cached.
2. Verify the settings values:
   ```python
   import frappe
   settings = frappe.get_single("Chatbot Settings")
   print(settings.default_query_limit, settings.default_top_n_limit, settings.max_query_limit)
   ```
3. If all values are 0 or blank, the system uses fallback defaults from `core/constants.py` (20, 10, 100).

### Custom prompt not taking effect (Phase 5B)

1. After changing prompt settings (persona, language, custom instructions), open a **new conversation**. The system prompt is set at the start of each conversation.
2. Verify in bench console:
   ```python
   from ai_chatbot.core.prompts import build_system_prompt
   prompt = build_system_prompt()
   print(prompt[:500])  # Check the beginning for custom persona
   ```
3. If blank, check Chatbot Settings → Prompt Configuration fields.

### Plugin tools not loading (Phase 5B)

1. External app tools are loaded via the `ai_chatbot_tool_modules` Frappe hook.
2. Check your external app's `hooks.py` has:
   ```python
   ai_chatbot_tool_modules = ["your_app.your_module"]
   ```
3. Check Error Log (`/app/error-log`) for: `Failed to load AI Chatbot tool plugin`.
4. Ensure the module path is correct and the module uses `@register_tool(...)` decorator.
5. After adding hooks, restart bench: `bench restart`.

---

## Phase 6A: UI Overhaul

### 6A.1 Sidebar Redesign

#### 6A.1.1 Expanded Sidebar

1. Open `/ai-chatbot`.
2. **Expected**: Sidebar is visible on the left (w-72) with: hamburger toggle icon + logo + settings gear in the header row, grey "New Chat" button, search input, date-grouped conversation list (Today, Yesterday, Last 7 Days, Older), provider selector dropdown at the bottom.
3. Click the **settings gear icon** → should navigate to Chatbot Settings.
4. Click the **provider dropdown** at the bottom → should show available providers (OpenAI, Claude, Gemini). Selecting one should change the provider.

#### 6A.1.2 Collapsed Sidebar

1. Click the **hamburger icon** (PanelLeftClose) in the sidebar header.
2. **Expected**: Sidebar collapses to a narrow icon strip (w-14) showing: expand button, new chat (+), search icon.
3. Click expand button → sidebar returns to full width.
4. Refresh the page → sidebar state should persist (stored in localStorage).

#### 6A.1.3 Date Grouping

1. Create conversations on different days (or have existing ones).
2. **Expected**: Conversations are grouped under "Today", "Yesterday", "Last 7 Days", "Older" headers based on their `updated_at` timestamp.
3. Empty groups should not be shown.

#### 6A.1.4 Header Removed

1. Verify there is **no header bar** above the chat area.
2. All header functionality (provider selector, settings, sidebar toggle) is now in the sidebar.

---

### 6A.2 ChatInput Cleanup

#### 6A.2.1 Icon-Only Buttons

1. Look at the chat input area.
2. **Expected**: Send button shows only a blue arrow icon (no "Send" text), Stop button shows only a red square icon (no "Stop" text).
3. Both buttons are 52×52px squares with rounded corners.

#### 6A.2.2 Suggestions Removed

1. Start a new conversation.
2. **Expected**: No suggestion chips appear. Instead, a personalized greeting is shown in the center of the chat area.

---

### 6A.3 Personalized Greeting

#### 6A.3.1 New Chat Greeting

1. Click "New Chat" in the sidebar.
2. **Expected**: The chat area shows a centered greeting: the orbital logo SVG, "Hello, {YourFullName}!", and "How can I help you today?" with the ChatInput centered below.

#### 6A.3.2 Input Moves to Bottom

1. Type a message and send it.
2. **Expected**: The greeting disappears, messages appear in the scrollable area, and the ChatInput moves to its bottom-pinned position.

---

### 6A.4 Chat Search

#### 6A.4.1 Search by Title

1. In the expanded sidebar, type a conversation title (or part of it) in the search input.
2. **Expected**: After a brief debounce, matching conversations appear, replacing the grouped list. A loading spinner shows during search.

#### 6A.4.2 Search by Message Content

1. Search for a word or phrase that exists in a message but NOT in the conversation title.
2. **Expected**: The conversation containing that message appears in results.

#### 6A.4.3 Clear Search

1. Clear the search input (backspace or click the X icon).
2. **Expected**: The search results disappear and the normal date-grouped conversation list returns.

#### 6A.4.4 No Results

1. Search for a nonsensical string (e.g., "xyzzy123").
2. **Expected**: "No results" empty state is shown.

---

### 6A.5 Wider AI Messages

1. Send a prompt that returns a table or long content (e.g., "Show me a summary of all sales invoices").
2. **Expected**: The AI response bubble is wider than before (`max-w-[85%]` on small screens, `max-w-5xl` on large screens). User messages remain narrower (`max-w-3xl`).
3. Tables and code blocks should use the full available width within the response bubble.

---

### 6A.6 Dark Mode

#### 6A.6.1 OS Dark Mode Detection

1. Set your OS to dark mode (System Settings → Appearance → Dark).
2. Open or refresh `/ai-chatbot`.
3. **Expected**: The entire UI switches to dark mode — dark backgrounds, light text, dark sidebar, dark input area, dark message bubbles for AI responses.

#### 6A.6.2 OS Light Mode

1. Set your OS to light mode.
2. Refresh the page.
3. **Expected**: The UI switches to light mode — white backgrounds, dark text.

#### 6A.6.3 Dynamic Theme Change

1. Open `/ai-chatbot` in a browser.
2. Without refreshing, change your OS theme from light to dark (or vice versa).
3. **Expected**: The UI updates automatically without a page refresh.

#### 6A.6.4 Dark Mode Markdown

1. In dark mode, send a prompt that returns markdown with code blocks, links, blockquotes, and tables.
2. **Expected**: All markdown elements are readable — code has dark background, links are blue, tables have visible borders, blockquotes have proper styling.

---

### 6A.7 Process Step Indicators

#### 6A.7.1 Basic Streaming

1. Send a simple message (e.g., "Hello").
2. **Expected**: While waiting for the response, the typing indicator shows the orbital logo with bouncing dots and text like "Preparing context...", then "Communicating with LLM...", then "Saving response..." before the final content appears.

#### 6A.7.2 Tool Call Steps

1. Send a query that triggers tool calls (e.g., "Show sales summary for this month").
2. **Expected**: Process steps show: "Preparing context..." → "Communicating with LLM..." → "Executing Get Sales Analytics..." (tool name) → "Processing results..." → "Saving response...".

#### 6A.7.3 Typing Indicator Design

1. Observe the typing indicator during streaming.
2. **Expected**: Shows the orbital logo SVG (not the old "AI" text circle) with three bouncing blue dots and the process step text.

---

### Troubleshooting Phase 6A

### Dark mode not working

1. Check that `tailwind.config.js` has `darkMode: 'class'`.
2. Check that the `<html>` element has the `dark` class when OS is in dark mode (inspect with DevTools).
3. If not, check `App.vue` — it should detect `prefers-color-scheme: dark` and toggle the class.

### Search not returning results

1. Verify the backend endpoint exists: `bench --site <SITE> console` → `frappe.get_attr('ai_chatbot.api.chat.search_conversations')`.
2. Check the search query is at least 2 characters.
3. Check Error Log for any search errors.

### Process steps not showing

1. Ensure streaming is enabled in Chatbot Settings.
2. Check browser console for `ai_chat_process_step` events (they should appear in the Socket.IO log).
3. Verify `useStreaming.js` exports `processStep` — check browser DevTools → Sources.
