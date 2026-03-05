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

---

## Phase 6B: Multi-Dimensional Analytics & GL-Based Finance

### 6B.1 Multi-Dimensional Grouping

#### 6B.1.1 Single Dimension

1. Ask: `Show revenue by territory`
2. **Expected**: A stacked bar chart + hierarchical table showing territories with total and period columns (quarterly by default). Tool name `Multidimensional Summary` should appear in the "Used ERPNext Tools" badge.

#### 6B.1.2 Multiple Dimensions

1. Ask: `Show sales by territory and customer group, quarterly`
2. **Expected**: Hierarchical table with territory as group headers (bold, tinted background), customer groups as indented children. Each group header has subtotals. Stacked bar chart shows top-level territories.

#### 6B.1.3 Different Metrics

1. Ask: `Show expenses by department, monthly`
2. **Expected**: Purchase Invoice-based expenses grouped by department with monthly columns.
3. Ask: `Show profit by territory`
4. **Expected**: Computed profit (revenue - expenses) by territory.

#### 6B.1.4 Accounting Dimensions

1. If you have created Accounting Dimensions in ERPNext (e.g., "Business Vertical", "Business Segment"):
   - Ask: `Show sales by business_vertical` (use the exact fieldname)
   - **Expected**: The tool automatically discovers the accounting dimension and groups by it. If the dimension exists on Sales Invoice, data is returned.
2. If the dimension does NOT exist on the target doctype:
   - **Expected**: A clear error message: "Dimension 'xyz' does not exist on Sales Invoice. It may not be set up as an accounting dimension for this doctype."
3. If no accounting dimensions are set up, ask: `Show sales by some_random_field`
   - **Expected**: An error message listing the supported dimensions.

#### 6B.1.5 Item Group (Child Table JOIN)

1. Ask: `Show revenue by item group`
2. **Expected**: Revenue grouped by item group using Sales Invoice Item child table JOIN with `base_amount` aggregation.

---

### 6B.2 GL Entry Analytics

#### 6B.2.1 GL Summary

1. Ask: `Show GL summary by root type`
2. **Expected**: Aggregated debit/credit by root type (Asset, Liability, Equity, Income, Expense) with bar chart.
3. Ask: `Show GL summary by account type for expenses`
4. **Expected**: Filtered to Expense root type, grouped by account type.

#### 6B.2.2 Trial Balance

1. Ask: `Show trial balance for this fiscal year`
2. **Expected**: Accounts grouped by root type with opening balance, debit, credit, closing balance columns. Subtotals per root type. Grand total row at the bottom.

#### 6B.2.3 Account Statement

1. Ask: `Show account statement for [specific account name]`
2. **Expected**: Opening balance + individual GL entries with running balance column. Line chart showing balance trend over time.

---

### 6B.3 CFO Dashboard BI Cards

#### 6B.3.1 BI Cards Display

1. Ask: `Show CFO dashboard` or `Show financial overview`
2. **Expected**: A row of 5 metric cards appears above the chart: Revenue, Net Profit, Cash Position, AR Outstanding, AP Outstanding.
3. Revenue and Net Profit cards should show YoY change percentage with green (up) or red (down) trend indicator.
4. Values should be abbreviated (e.g., 1.2M, 450K).

#### 6B.3.2 BI Cards Responsiveness

1. Resize the browser window to different widths.
2. **Expected**: Cards reflow — 5 columns on large screens, 3 on medium, 2 on small.

---

### 6B.4 Sidebar Header

1. Open `/ai-chatbot` with sidebar expanded.
2. **Expected**: Sidebar header shows: App logo (left side), Settings gear button + Collapse toggle button (right side, grouped together).
3. **Before (6A)**: `[Toggle] [Logo] [Settings]` — centered logo.
4. **After (6B)**: `[Logo] ... [Settings] [Toggle]` — logo anchored left, actions right.

---

### 6B.5 Personalized Greeting Avatar

1. Click "New Chat" to see the greeting screen.
2. **Expected**: Shows your **user avatar** (profile picture) in a large circle (96×96px), NOT the app's orbital logo.
3. If you don't have a profile picture, it should show your initials in a gray circle.
4. Below the avatar: "Hello, {YourName}!" and "How can I help you today?"

---

### 6B.6 Hierarchical Table Rendering

1. Ask any multi-dimensional query (e.g., `Show revenue by territory and customer`)
2. **Expected hierarchical table features**:
   - Group rows (level 0) are **bold** with a slightly tinted background
   - Child rows are indented based on their level
   - Values are right-aligned with consistent decimal formatting
   - Table has horizontal scroll if many period columns
   - Table has proper dark mode styling (borders, text colors)

---

### Troubleshooting Phase 6B

#### BI cards not showing

1. Ensure the CFO dashboard tool returns `bi_cards` in the response. Check browser DevTools → Network → response payload.
2. Verify `ChatMessage.vue` imports `BiCards` component and has the `biCardsData` computed property.

#### Hierarchical table not rendering

1. Check that the tool result contains `hierarchical_table` with `headers` and `rows` arrays.
2. Verify `ChatMessage.vue` imports `HierarchicalTable` component.

#### Accounting dimension not recognized

1. Verify the accounting dimension exists: Go to **Accounting Dimension** list in ERPNext.
2. Ensure it is not disabled.
3. Check that the dimension's custom field was created on the target doctype (e.g., Sales Invoice).
4. Use the exact fieldname (not the label). Check fieldname in the Accounting Dimension document.
5. Run: `bench --site <SITE> console` → `from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions; print(get_accounting_dimensions(as_list=False))`

#### GL tools not registered

1. Verify `tools/registry.py` imports both `ai_chatbot.tools.finance.analytics` and `ai_chatbot.tools.finance.gl_analytics`.
2. Run: `bench --site <SITE> console` → `from ai_chatbot.tools.registry import get_registered_tools; print([t for t in get_registered_tools() if 'gl' in t or 'multi' in t])`

---

## Phase 6B+: Parent-Child Company, Session Context & Refinements

### 6B+.0 Prerequisites

```bash
# Apply the new session_context field on Chatbot Conversation
bench --site test.local migrate

# Rebuild frontend (markdown table stripping fix)
cd apps/ai_chatbot/frontend && npm run build

# Restart bench
bench start
```

Verify session tools are registered:
```bash
bench --site test.local console
>>> from ai_chatbot.tools.registry import get_registered_tools
>>> print([t for t in get_registered_tools() if 'session' in t or 'subsidiar' in t or 'currency' in t])
# Should include set_include_subsidiaries, set_target_currency
```

---

### 6B+.1 Session Context — Include Subsidiaries

#### 6B+.1.1 Proactive Subsidiary Detection (New Chat)

1. Ensure your ERPNext has a **parent company** with at least one **child company** (Settings → Company → set `Parent Company` on the child).
2. Verify your default company: `frappe.defaults.get_user_default("Company")` — should return the parent company name.
3. Start a **new chat session** and ask any business question: `What is the total sales this month?`
4. **Expected**: Since this is the first query and the user's company has subsidiaries, the AI should **proactively ask** whether to include subsidiary data:
   > "Your company [Parent] has subsidiaries: [Child1, Child2, ...]. Would you like to include subsidiary data in your reports, or show only [Parent]?"
5. Reply: `Yes, include subsidiaries`
6. **Expected**: AI calls `set_include_subsidiaries` tool with `include=True`, confirms the setting, then proceeds to answer the original question with consolidated data.

#### 6B+.1.2 Verify Subsidiaries in Queries

1. After enabling subsidiaries (6B+.1.1), ask: `What is the total sales this month?`
2. **Expected**:
   - Response mentions **"[Parent Company] including its subsidiaries"** (the `company_label` field).
   - Revenue aggregates data from the parent AND all child companies.
   - Currency is the parent company's default currency.
   - AI does NOT ask about subsidiaries again — it uses the saved session preference.
3. Ask: `Show revenue by territory`
4. **Expected**: Grouped data includes transactions from all companies in the hierarchy.

#### 6B+.1.3 Disable Subsidiaries

1. Say: `Don't include subsidiaries` or `Exclude child companies`
2. **Expected**: AI calls `set_include_subsidiaries` with `include=False`. Confirms change.
3. Ask: `What is the total sales this month?`
4. **Expected**: Response now shows only the parent company data. Label says just the company name without "including its subsidiaries".

---

### 6B+.2 Session Context — Target Currency

#### 6B+.2.1 Set Target Currency

1. Say: `Show all amounts in USD` or mention `@USD` in your message.
2. **Expected**: AI calls `set_target_currency` with `currency="USD"`. Confirms target currency is set.
3. Ask: `What is total revenue this quarter?`
4. **Expected**: Response `currency` field shows "USD" regardless of the company's default currency.

#### 6B+.2.2 Reset Target Currency

1. Say: `Don't use target currency` or `Reset to default currency`
2. **Expected**: AI calls `set_target_currency` with `currency=None`. Confirms reset.
3. Ask: `What is total revenue this quarter?`
4. **Expected**: Response `currency` field shows the company's default currency.

#### 6B+.2.3 Company Grouping with Currency

1. Ask: `Show revenue by company` (requires multiple companies in ERPNext).
2. **Expected**: Each company's revenue is shown in its own default currency (unless target currency is set).
3. Set a target currency: `Use EUR for all amounts`
4. Ask again: `Show revenue by company`
5. **Expected**: All values shown in EUR.

---

### 6B+.3 BI Cards Display (Fix)

#### 6B+.3.1 CFO Dashboard

1. Ask: `Show CFO dashboard`
2. **Expected**: A row of 5 BI metric cards appears: Revenue, Gross Profit (with margin %), Cash Position, Receivables, Payables.

#### 6B+.3.2 Financial Overview

1. Ask: `Show financial overview`
2. **Expected**: Same 5 BI cards appear. The `get_financial_overview` tool now includes `bi_cards` in the response.

---

### 6B+.4 Duplicate Table Fix

1. Ask: `Show revenue by territory and customer`
2. **Expected**:
   - The hierarchical table appears **once** (the compact, styled `HierarchicalTable` component after the chart).
   - There should be NO raw markdown table (pipe-delimited `| ... |` format) in the text above the chart.
3. If the AI still outputs markdown text alongside, the markdown table portion should be stripped automatically — only the Vue component table renders.

---

### 6B+.5 Dimension Name Partial Matching

#### 6B+.5.1 Suffix Match

1. If you have an accounting dimension `business_vertical`:
   - Ask: `Show revenue by vertical`
   - **Expected**: Resolves `vertical` → `business_vertical` via suffix match. Returns grouped data.
2. If you have `business_segment`:
   - Ask: `Show sales by segment`
   - **Expected**: Resolves `segment` → `business_segment`.

#### 6B+.5.2 Label Word Match

1. Ask: `Show revenue by Business Vertical` (using the dimension label, not fieldname).
2. **Expected**: Resolves via label matching. Returns grouped data.

#### 6B+.5.3 Ambiguous Match

1. If you have both `business_vertical` and `custom_vertical`:
   - Ask: `Show revenue by vertical`
   - **Expected**: Returns `None` (ambiguous — multiple matches). AI should inform the user to be more specific.

---

### 6B+.6 Hierarchical Table "Particular" Column

1. Ask any grouped query: `Show revenue by territory`
2. **Expected**: The hierarchical table's first column header is **"Particular"** (not the dimension name like "Territory").
3. Ask: `Show profit by territory`
4. **Expected**: Same — first column header is "Particular".

---

### 6B+.7 Company Label in All Tool Responses

#### 6B+.7.1 Monetary Tools

1. Ask: `What are the total purchases this month?`
2. **Expected**: Response includes `company_label` field (e.g., "My Company Ltd").
3. Enable subsidiaries, then ask the same question.
4. **Expected**: `company_label` is "My Company Ltd including its subsidiaries".

#### 6B+.7.2 Non-Monetary Tools (CRM, Stock, HRMS)

1. Ask: `How many employees do we have?`
2. **Expected**: Response includes `company_label` field with company name.
3. Ask: `Show lead conversion rate`
4. **Expected**: `company_label` field present.
5. Ask: `Show low stock items`
6. **Expected**: `company_label` field present.

---

### 6B+.8 Session Persistence

1. Enable subsidiaries and set target currency in one conversation.
2. Switch to a different conversation.
3. Switch back to the original conversation.
4. Ask a business question.
5. **Expected**: Session context (subsidiaries + target currency) is **preserved** — settings persist because they are stored in the Chatbot Conversation DocType's `session_context` field.

---

### 6B+.9 Multi-Company Query Migration Verification

All 51+ tool functions across 15 modules have been migrated from `get_default_company` to `get_company_filter` for session-aware multi-company support. Test each category with subsidiaries enabled.

#### 6B+.9.1 Selling Tools

1. Enable subsidiaries: `Include subsidiary data`
2. Ask: `What are the total sales this month?`
3. **Expected**: Response aggregates sales from parent + child companies. `company_label` shows "including its subsidiaries".
4. Ask: `Who are the top 5 customers?`
5. **Expected**: Customers from all companies in the hierarchy appear.
6. Ask: `Show sales by item`
7. **Expected**: Item sales consolidated across companies.

#### 6B+.9.2 Buying Tools

1. With subsidiaries enabled, ask: `What are the total purchases this quarter?`
2. **Expected**: Purchase data from all companies. `company_label` includes subsidiary notation.
3. Ask: `Who are the top suppliers?`
4. **Expected**: Suppliers from parent and child companies combined.

#### 6B+.9.3 Finance Tools

1. Ask: `Show CFO dashboard`
2. **Expected**: All KPIs (revenue, COGS, receivables, payables, cash position) aggregate across companies.
3. Ask: `Show budget vs actual`
4. **Expected**: Budget data uses primary company (budget is per-company), actuals aggregate if subsidiaries enabled.
5. Ask: `Show cash flow statement`
6. **Expected**: Payment entries from all companies included.
7. Ask: `Show receivable aging`
8. **Expected**: Outstanding invoices from all companies.
9. Ask: `Show working capital summary`
10. **Expected**: Receivables, payables, inventory consolidated.
11. Ask: `Show financial ratios`
12. **Expected**: Ratios calculated from consolidated data.
13. Ask: `Show month over month comparison`
14. **Expected**: Monthly revenue/expenses aggregate across companies.

#### 6B+.9.4 GL Entry Tools

1. Ask: `Show trial balance`
2. **Expected**: GL balances from all companies in the hierarchy.
3. Ask: `Show account statement for Cash - [Company]`
4. **Expected**: GL entries from all companies included.

#### 6B+.9.5 Stock Tools

1. Ask: `Show low stock items`
2. **Expected**: Items from warehouses across all companies.
3. Ask: `Show stock ageing`
4. **Expected**: Stock age data from all company warehouses.

#### 6B+.9.6 HRMS Tools

1. Ask: `How many employees do we have?`
2. **Expected**: Headcount from all companies. Department breakdown includes all.
3. Ask: `Show payroll summary`
4. **Expected**: Salary slips from all companies aggregated.
5. Ask: `Show department wise salary`
6. **Expected**: Departments from all companies in pie chart.
7. Ask: `Show employee turnover`
8. **Expected**: Hires and exits across all companies.

#### 6B+.9.7 CRM Tools

1. Ask: `Show lead statistics`
2. **Expected**: Leads from all companies.
3. Ask: `Show sales funnel`
4. **Expected**: Funnel stages aggregate across companies.
5. Ask: `Show opportunity by stage`
6. **Expected**: Opportunities from all companies.

#### 6B+.9.8 Single Company Mode (Disable Subsidiaries)

1. Say: `Don't include subsidiaries`
2. Repeat any query from above (e.g., `What are the total sales this month?`)
3. **Expected**: Data is scoped to only the default company. `company_label` shows just the company name.

#### 6B+.9.9 Code-Level Verification

Run in bench console to verify no session-aware tool still uses `get_default_company`:

```bash
# Should show only: consolidation.py, operations/search.py, session.py, finance/analytics.py
cd apps/ai_chatbot && grep -rn "get_default_company" ai_chatbot/tools/ --include="*.py"
```

Verify all tool modules import `get_company_filter`:
```bash
# Should list 15 tool modules
cd apps/ai_chatbot && grep -rln "get_company_filter" ai_chatbot/tools/ --include="*.py"
```

---

### Troubleshooting Phase 6B+

#### Session tools not appearing

1. Verify `tools/registry.py` imports `ai_chatbot.tools.session`.
2. Run: `bench --site <SITE> console` → `from ai_chatbot.tools.registry import get_registered_tools; print([t for t in get_registered_tools()])`
3. Look for `set_include_subsidiaries` and `set_target_currency` in the output.

#### Session context not persisting

1. Check that the `session_context` field exists on Chatbot Conversation DocType:
   - `bench --site <SITE> console` → `frappe.get_meta("Chatbot Conversation").has_field("session_context")`
   - Should return `True`. If not, run `bench --site <SITE> migrate`.
2. Verify `frappe.flags.current_conversation_id` is set:
   - Check `api/chat.py` and `api/streaming.py` — both should set `frappe.flags.current_conversation_id = conversation_id` before tool execution.

#### Subsidiaries not included in queries

1. Confirm parent-child relationship in ERPNext: Company list → child company has `Parent Company` set.
2. Check `get_companies_for_query()` in console:
   ```python
   from ai_chatbot.core.session_context import get_companies_for_query
   print(get_companies_for_query("Parent Company Name"))
   ```
3. Verify the function returns `["Parent Company", "Child Company 1", "Child Company 2", ...]`.

#### Markdown table still showing alongside hierarchical table

1. Check `ChatMessage.vue` `renderedContent` computed property — it should strip markdown tables when `hierarchicalTables.value.length > 0`.
2. Open DevTools → Elements → inspect the message content area. Look for `<table>` elements generated by markdown rendering vs `HierarchicalTable` Vue component.

#### Dimension partial match not working

1. Run in console:
   ```python
   from ai_chatbot.data.grouping import resolve_dimension_name, _get_all_dimensions
   dims = _get_all_dimensions("Sales Invoice")
   print(dims.keys())
   print(resolve_dimension_name("vertical", dims))
   ```
2. If `None` is returned, check that `business_vertical` exists in the dimensions dict and that there are no multiple matches.

---

## Phase 6C: Workspace, Help Button & Language Selection

### Prerequisites

```bash
# Run migration to sync workspace and number card fixtures
bench --site <SITE> migrate
bench --site <SITE> clear-cache

# Rebuild frontend
cd apps/ai_chatbot/frontend && npm run build
```

---

### 6C.1 Frappe Workspace & Number Cards

#### 6C.1.1 Workspace Visibility

1. Open Frappe desk: `http://<SITE>/app`
2. Look at the left sidebar navigation.
3. **Expected**: "AI Chatbot" workspace appears in the sidebar with a chat icon.
4. Click on it, or navigate directly to `/app/ai-chatbot`.
5. **Expected**: The workspace page loads with number cards, shortcuts, and administration links.

#### 6C.1.2 Number Cards

1. On the AI Chatbot workspace page, verify 3 number cards are displayed at the top:
   - **Total Conversations** — count of all `Chatbot Conversation` records
   - **Messages Today** — count of `Chatbot Message` records created today
   - **Total Token Usage** — sum of `total_tokens` across all conversations
2. **Expected**: Each card shows a numeric value. If no data exists yet, values will be 0.
3. Create a new chat at `/ai-chatbot` and send a message, then refresh the workspace.
4. **Expected**: "Total Conversations" and "Messages Today" counts increase.

#### 6C.1.3 Workspace Shortcuts

1. On the workspace page, verify 4 shortcut buttons are visible:
   - **Open AI Chatbot** — links to `/ai-chatbot`
   - **Chatbot Settings** — opens `Chatbot Settings` DocType
   - **Chatbot Conversation** — opens conversation list view
   - **Chatbot Message** — opens message list view
2. Click each shortcut.
3. **Expected**: Each opens the correct page.

#### 6C.1.4 Administration Links

1. Below the shortcuts, verify an "Administration" card with links:
   - Chatbot Settings
   - Chatbot Conversation
   - Chatbot Message
   - Chatbot Token Usage
2. Click each link.
3. **Expected**: Each opens the correct DocType list or form view.

#### 6C.1.5 Fixture Verification (Console)

```bash
bench --site <SITE> execute "frappe.get_all('Workspace', filters={'module': 'Chatbot'}, fields=['name', 'label', 'icon', 'public'])"
# Expected: [{"name": "AI Chatbot", "label": "AI Chatbot", "icon": "chat", "public": 1}]

bench --site <SITE> execute "frappe.get_all('Number Card', filters={'module': 'Chatbot'}, fields=['name', 'label'])"
# Expected: 3 number cards (Total Conversations, Messages Today, Total Token Usage)
```

---

### 6C.2 Help Button & Sample Prompts Modal

#### 6C.2.1 Help Button Placement

1. Open the chatbot at `/ai-chatbot`.
2. Look at the chat input area at the bottom.
3. **Expected**: A help icon button (circle with question mark) appears alongside the send button — after the microphone button, before the stop/send button.
4. The button order should be: `[Paperclip] [Textarea] [Microphone] [Help] [Send]`

#### 6C.2.2 Help Modal Opening

1. Click the help icon button.
2. **Expected**: A modal overlay appears with the title "Sample Prompts".
3. The modal should have a semi-transparent backdrop.

#### 6C.2.3 Sample Prompt Categories

1. Inside the modal, verify 6 categories are listed:
   - **Sales** (TrendingUp icon)
   - **Finance** (DollarSign icon)
   - **HR** (Users icon)
   - **CRM** (Target icon)
   - **Stock** (Package icon)
   - **Purchasing** (ShoppingCart icon)
2. Each category should have 4 sample prompts.
3. **Expected**: 24 prompts total across all categories.

#### 6C.2.4 Prompt Type Badges

1. Each prompt should show a colored badge indicating the output type:
   - **table** — blue badge
   - **chart** — green badge
   - **number** — amber badge
2. **Expected**: Badges are visible and correctly colored for each prompt.

#### 6C.2.5 Prompt Selection

1. Click any sample prompt (e.g., "What is the total sales amount this quarter?").
2. **Expected**: The modal closes and the prompt text is filled into the chat input textarea.
3. The textarea should be focused and ready to send.
4. Press Enter to send the prompt.
5. **Expected**: The AI processes the prompt and returns a response matching the expected output type.

#### 6C.2.6 Modal Closing

1. Open the help modal again.
2. Click the X button in the top-right corner.
3. **Expected**: Modal closes.
4. Open the modal again.
5. Click the backdrop (dark area outside the modal).
6. **Expected**: Modal closes.
7. Open the modal again.
8. Press the Escape key.
9. **Expected**: Modal closes.

#### 6C.2.7 SAMPLE_USER_PROMPT.md

1. Verify the file exists at the project root: `apps/ai_chatbot/SAMPLE_USER_PROMPT.md`
2. **Expected**: Contains all 24 sample prompts organized by the same 6 categories as the modal.
3. Each prompt shows the expected output format (table, chart, or number).

---

### 6C.3 Response Language Selector

#### 6C.3.1 Language Dropdown in Sidebar

1. Open the chatbot at `/ai-chatbot`.
2. Expand the sidebar (if collapsed).
3. Look at the bottom of the sidebar, below the AI provider selector.
4. **Expected**: A language dropdown is visible with a globe/languages icon and the text "Default".

#### 6C.3.2 Available Languages

1. Click the language dropdown.
2. **Expected**: A list of available languages appears (configured in Chatbot Settings).
3. If no languages are configured in settings, the dropdown should still show "Default".

#### 6C.3.3 Dropdown Mutual Exclusion

1. Open the provider dropdown (e.g., showing "OpenAI").
2. While it's open, click the language dropdown.
3. **Expected**: The provider dropdown closes and the language dropdown opens.
4. Repeat in reverse: open language, then click provider.
5. **Expected**: Language dropdown closes, provider dropdown opens.

#### 6C.3.4 Language Selection

1. Select a non-English language from the dropdown (e.g., "Hindi", "Spanish", "French").
2. **Expected**: The dropdown closes and shows the selected language name.
3. Send a message: `What is the total sales this month?`
4. **Expected**: The AI responds in the selected language.

#### 6C.3.5 Per-Conversation Persistence

1. Set the language to "Hindi" in the current conversation.
2. Click "New Chat" to create a new conversation.
3. **Expected**: The language selector resets to "Default" for the new conversation.
4. Switch back to the previous conversation.
5. **Expected**: The language selector shows "Hindi" (the previously saved language).

#### 6C.3.6 Language in Backend

1. Set a language in the chatbot UI.
2. Verify it persists in the database:
   ```bash
   bench --site <SITE> execute "frappe.get_value('Chatbot Conversation', '<CONVERSATION_ID>', 'session_context')"
   ```
3. **Expected**: The `session_context` JSON includes `"response_language": "Hindi"` (or whichever language was selected).

#### 6C.3.7 Language Fallback

1. In Chatbot Settings (`/app/chatbot-settings`), set a global **Response Language** (e.g., "French").
2. Start a new conversation (no per-conversation language set).
3. Send a message.
4. **Expected**: AI responds in French (global fallback).
5. Now set the conversation language to "Spanish" using the sidebar dropdown.
6. Send another message.
7. **Expected**: AI responds in Spanish (per-conversation override takes priority over global).

---

### 6C.4 Settings Integration

#### 6C.4.1 Available Languages in Settings

1. Go to Chatbot Settings (`/app/chatbot-settings`).
2. Find the **Available Languages** field (small text or table field).
3. Add languages separated by newlines or commas (e.g., "English, Hindi, Spanish, French, German, Japanese").
4. Save.
5. Reload the chatbot UI.
6. **Expected**: The language dropdown in the sidebar shows all configured languages.

#### 6C.4.2 Default Response Language

1. In Chatbot Settings, set **Response Language** to "German".
2. Save.
3. Open a new conversation in the chatbot.
4. **Expected**: The language selector shows "Default" but the AI uses German as the fallback language.

---

### Troubleshooting Phase 6C

#### Workspace not appearing in sidebar

1. Ensure `bench --site <SITE> migrate` has been run after adding the workspace fixture.
2. Run `bench --site <SITE> clear-cache` and hard-refresh the browser (Ctrl+Shift+R).
3. Verify the workspace exists:
   ```bash
   bench --site <SITE> execute "frappe.get_all('Workspace', filters={'module': 'Chatbot'})"
   ```
4. Check that `ai_chatbot/modules.txt` contains `Chatbot`.

#### Number cards showing 0 or error

1. Verify number cards exist in the database:
   ```bash
   bench --site <SITE> execute "frappe.get_all('Number Card', filters={'module': 'Chatbot'}, fields=['name', 'document_type', 'function'])"
   ```
2. Check that the DocTypes referenced (`Chatbot Conversation`, `Chatbot Message`) have data.
3. For "Total Token Usage", ensure the `total_tokens` field exists on `Chatbot Conversation` and has values > 0.

#### Help modal not appearing

1. Check browser console for JavaScript errors.
2. Verify `HelpModal.vue` is imported in `ChatInput.vue`.
3. Ensure the frontend was rebuilt: `cd apps/ai_chatbot/frontend && npm run build`

#### Language selector not showing languages

1. Check that `available_languages` is configured in Chatbot Settings.
2. Verify the `get_settings()` API returns languages:
   ```bash
   bench --site <SITE> execute "from ai_chatbot.api.chat import get_settings; print(get_settings())"
   ```
3. Look for `available_languages` in the response.

#### Language not persisting per conversation

1. Verify the `set_conversation_language` endpoint works:
   ```bash
   bench --site <SITE> execute "from ai_chatbot.api.chat import set_conversation_language; print(set_conversation_language('<CONV_ID>', 'Hindi'))"
   ```
2. Check that `session_context` field on `Chatbot Conversation` DocType exists and is writable.
3. Verify `get_conversation_messages()` returns `session_context` in its response.

---

## Phase 7: Intelligent Document Processing (IDP)

Phase 7 adds LLM-powered document extraction — upload a PDF, image, Excel, or Word file and the AI extracts structured data, maps it to an ERPNext DocType schema, and optionally creates the record.

### Prerequisites

```bash
# 1. Install IDP optional dependencies
cd apps/ai_chatbot
pip install ".[idp]"
# This installs: pypdf>=4.0, openpyxl>=3.1, python-docx>=1.1

# 2. Run migrations (adds enable_idp_tools field to Chatbot Settings)
bench --site <SITE> migrate

# 3. Clear cache
bench --site <SITE> clear-cache

# 4. Rebuild frontend
cd apps/ai_chatbot/frontend && npm run build

# 5. Restart bench
bench restart
```

### 7.1 Enable IDP in Chatbot Settings

#### 7.1.1 Enable IDP Tools

1. Go to **Chatbot Settings** (`/app/chatbot-settings`).
2. Switch to the **Tools** tab.
3. Find the **Document Processing (IDP)** section.
4. Check **Enable IDP Tools**.
5. Save.
6. **Expected**: The setting saves without errors.

#### 7.1.2 Verify IDP Tools Are Registered

1. Open a terminal and run:
   ```bash
   bench --site <SITE> execute "from ai_chatbot.tools.registry import get_all_tools_schema; tools = get_all_tools_schema(); idp_tools = [t['function']['name'] for t in tools if 'document' in t['function']['name'].lower() or 'extract' in t['function']['name'].lower()]; print(idp_tools)"
   ```
2. **Expected**: Output includes `['extract_document_data', 'create_from_extracted_data', 'compare_document_with_record']`.

#### 7.1.3 Verify Optional Dependencies Installed

1. Run:
   ```bash
   bench --site <SITE> execute "import pypdf; print('pypdf', pypdf.__version__)"
   bench --site <SITE> execute "import openpyxl; print('openpyxl', openpyxl.__version__)"
   bench --site <SITE> execute "import docx; print('python-docx OK')"
   ```
2. **Expected**: All three commands print version info without ImportError.

---

### 7.2 Extract Data from a PDF Invoice

This is the primary use case — extracting structured data from a PDF invoice and mapping it to the Sales Invoice DocType.

#### 7.2.1 Prepare a Test PDF

1. Create or obtain a sample PDF invoice containing:
   - Customer name
   - Invoice date and due date
   - Line items with item codes/descriptions, quantities, and rates
   - A total amount
   - A currency symbol (e.g., $, €, ₹)
2. The invoice can be in **any language** — the LLM handles multi-language documents.

#### 7.2.2 Upload and Extract via Chat

1. Open the chatbot at `/ai-chatbot`.
2. Start a new conversation.
3. Upload the PDF using the file attachment button (📎).
4. Send a message:
   > "Extract data from this invoice and map it to a Sales Invoice."
5. **Expected**:
   - The AI calls the `extract_document_data` tool with the file URL and `target_doctype: "Sales Invoice"`.
   - After processing, the AI presents the extracted fields:
     - **Header fields**: customer, posting_date (YYYY-MM-DD format), due_date, currency, grand_total
     - **Items table**: item_code, qty, rate, description for each line item
     - **Validation results**: any errors or warnings
     - **Unmapped fields**: source fields that couldn't be mapped
   - Dates are in YYYY-MM-DD format.
   - Numbers are clean (no currency symbols or commas, e.g., `1234.56` not `$1,234.56`).
   - The AI asks for confirmation before creating any record.

#### 7.2.3 Verify Extraction Quality

1. Compare the extracted fields against the original PDF:
   - Customer name should match (or be fuzzy-resolved to an existing Customer record).
   - Dates should be correctly parsed to YYYY-MM-DD.
   - Amounts should be clean numbers.
   - Each line item should have qty, rate, and description.
2. Check the `unmapped_fields` list — these are source fields the LLM couldn't map to ERPNext fields.
3. Check the `warnings` list — these are non-blocking issues (e.g., "Could not find Customer matching 'XYZ Corp'").
4. **Expected**: The extraction is accurate for well-formatted invoices. Minor discrepancies are acceptable for handwritten or poorly scanned documents.

---

### 7.3 Extract Data from an Image

Tests the Vision API path — when an image is uploaded, it's sent as base64 to the LLM's Vision endpoint.

#### 7.3.1 Upload an Image of an Invoice

1. Take a photo or screenshot of a paper invoice (PNG, JPG, or WEBP).
2. Open the chatbot and upload the image.
3. Send:
   > "Extract the data from this invoice image as a Purchase Invoice."
4. **Expected**:
   - The AI uses the Vision API to read the image.
   - Extracted fields are presented in the same format as PDF extraction.
   - The AI maps header info (supplier, posting_date, due_date) and line items (item_code, qty, rate).

#### 7.3.2 Multi-Language Image

1. Upload an invoice image in a non-English language (e.g., Spanish, Hindi, Arabic, Japanese).
2. Send:
   > "Extract this invoice data and map it to a Sales Invoice."
3. **Expected**: The LLM uses semantic reasoning to identify fields regardless of language. Field names in the document (e.g., "Fecha" for date, "Cantidad" for quantity) are mapped to their English ERPNext equivalents.

#### 7.3.3 Scanned PDF Fallback

1. Upload a scanned PDF (a PDF where the text is embedded as an image, not selectable text).
2. Send:
   > "Extract data from this scanned invoice."
3. **Expected**: The system detects that pypdf extracted no text and falls back to the Vision API path (base64 image). Extraction proceeds as for a regular image.

---

### 7.4 Extract Data from Excel and CSV

#### 7.4.1 Excel File (XLSX)

1. Prepare an Excel file (`.xlsx`) with invoice-like data:
   - A header section with customer name, date, and totals
   - A table of line items with columns: Item, Qty, Rate, Amount
2. Upload the file and send:
   > "Extract data from this Excel file as a Sales Order."
3. **Expected**:
   - openpyxl parses the Excel file into tabular text.
   - The LLM maps the columns to ERPNext Sales Order fields.
   - Items are extracted into the child table.

#### 7.4.2 CSV File

1. Prepare a CSV file with similar data.
2. Upload and send:
   > "Extract this CSV data as a Purchase Order."
3. **Expected**: Same as Excel — the CSV is parsed and the LLM maps fields semantically.

---

### 7.5 Extract Data from Word Documents

#### 7.5.1 DOCX File

1. Prepare a Word document (`.docx`) containing a quotation or invoice with paragraphs and a table of items.
2. Upload and send:
   > "Extract data from this Word document as a Quotation."
3. **Expected**: python-docx extracts paragraphs and tables. The LLM maps the content to Quotation fields.

---

### 7.6 Create ERPNext Record from Extracted Data

This tests the two-step confirmation pattern: extract → confirm → create.

#### 7.6.1 Prerequisites

1. Ensure **Enable Write Operations** is checked in Chatbot Settings (Tools tab → Data Operations section).
2. Ensure the target customer/supplier exists in ERPNext (or the fuzzy resolver can find a match).

#### 7.6.2 Full Extraction-to-Creation Flow

1. Upload a PDF invoice and send:
   > "Extract this invoice and create a Sales Invoice from it."
2. **Expected** — Step 1 (Extraction):
   - The AI extracts the data and presents it for review.
   - The AI asks: "The extracted data looks correct. Shall I create the Sales Invoice?"
3. Confirm by replying:
   > "Yes, create it."
4. **Expected** — Step 2 (Creation):
   - The AI calls `create_from_extracted_data` with the extracted JSON.
   - The document is created in ERPNext as a Draft.
   - The AI responds with the new document name and a link (e.g., "Created Sales Invoice `ACC-SINV-2026-00001`").

#### 7.6.3 Verify Created Record

1. Open the created record in ERPNext (click the link or navigate to `/app/sales-invoice/<name>`).
2. Verify:
   - Header fields (customer, posting_date, due_date, currency) match the extracted data.
   - Items table rows match (item_code, qty, rate, description).
   - The document is in Draft status (docstatus = 0).
3. **Expected**: All extracted fields are correctly populated in the ERPNext record.

#### 7.6.4 Write Operations Disabled

1. Uncheck **Enable Write Operations** in Chatbot Settings. Save.
2. Upload a document and ask the AI to extract and create a record.
3. **Expected**: Extraction succeeds, but when the AI attempts to create the record, it receives an error: "Write operations are disabled in Chatbot Settings."

---

### 7.7 Compare Document with Existing Record

This tests the reconciliation use case — comparing an uploaded document against an existing ERPNext record.

#### 7.7.1 Create a Reference Record

1. Create a Sales Order in ERPNext with known values:
   - Customer: an existing customer
   - A few items with specific quantities and rates
   - Note the Sales Order name (e.g., `SAL-ORD-2026-00001`).

#### 7.7.2 Upload a Matching Document

1. Prepare or generate a PDF/image that matches the Sales Order (same customer, same items, same amounts).
2. Upload and send:
   > "Compare this document with Sales Order SAL-ORD-2026-00001."
3. **Expected**:
   - The AI calls `compare_document_with_record`.
   - The comparison report shows:
     - **Matches**: Fields that are identical.
     - **Discrepancies**: Fields that differ (with extracted vs existing values).
     - **Missing in document**: Fields present in the record but not in the uploaded document.
     - **Missing in record**: Fields in the document but not in the record.
     - **Items comparison**: Per-item matching by item_code or position.
     - **Summary**: e.g., "5 of 7 header fields match. 2 discrepancies found."

#### 7.7.3 Upload a Document with Differences

1. Modify the document (change a quantity, a rate, or a date) so it differs from the Sales Order.
2. Upload and compare again.
3. **Expected**: The comparison report highlights the specific discrepancies:
   - e.g., "Field 'qty' — extracted: 15, existing: 10"
   - e.g., "Field 'posting_date' — extracted: 2026-02-01, existing: 2026-01-15"

#### 7.7.4 Compare Against Non-Existent Record

1. Send:
   > "Compare this document with Sales Order DOES-NOT-EXIST."
2. **Expected**: The AI reports an error: "Sales Order 'DOES-NOT-EXIST' does not exist."

---

### 7.8 Validation and Error Handling

#### 7.8.1 Missing Required Fields

1. Upload a minimal document that is missing key fields (e.g., an image with only item descriptions but no customer name or dates).
2. Send:
   > "Extract data from this as a Sales Invoice."
3. **Expected**: Extraction succeeds but the validation section shows errors:
   - "Required field 'Customer' (customer) is missing"
   - "Required field 'Posting Date' (posting_date) is missing"
4. The AI should present these errors and NOT attempt to create a record.

#### 7.8.2 Unresolved Link Fields

1. Upload a document with a customer name that does NOT exist in ERPNext (e.g., "Nonexistent Corp Ltd").
2. Extract as Sales Invoice.
3. **Expected**: The warnings list includes: "Could not find Customer matching 'Nonexistent Corp Ltd' for field 'Customer'. You may need to create it first or correct the name."

#### 7.8.3 Link Field Fuzzy Resolution

1. Create a Customer in ERPNext named "Acme International Trading Co." (with `customer_name` = "Acme International Trading Co.").
2. Upload an invoice with customer listed as "Acme International" or "Acme Intl Trading".
3. Extract as Sales Invoice.
4. **Expected**: The fuzzy resolver matches via LIKE search on `customer_name` and resolves to the existing Customer. The `resolved_links` section shows: `{"customer": "CUST-00001"}` (or whatever the Customer `name` is).

#### 7.8.4 Business Rule Validation

1. Upload a document where the posting date is AFTER the due date (e.g., posting: 2026-03-15, due: 2026-03-01).
2. Extract.
3. **Expected**: Warnings include: "Posting date (2026-03-15) is after due date (2026-03-01)."

#### 7.8.5 Invalid File Type

1. Upload a file type that is not supported (e.g., a `.zip` or `.mp4`).
2. Ask the AI to extract data.
3. **Expected**: An error is returned indicating the file type is not supported for IDP extraction.

---

### 7.9 Supported DocTypes

The IDP system supports these ERPNext DocTypes. Verify extraction works for at least 2-3 of them:

| DocType | Test Prompt |
|---------|-------------|
| Sales Invoice | "Extract this invoice as a Sales Invoice" |
| Purchase Invoice | "Extract this vendor invoice as a Purchase Invoice" |
| Quotation | "Extract this quote as a Quotation" |
| Sales Order | "Extract this order as a Sales Order" |
| Purchase Order | "Extract this PO as a Purchase Order" |
| Delivery Note | "Extract this delivery note as a Delivery Note" |
| Purchase Receipt | "Extract this receipt as a Purchase Receipt" |

---

### 7.10 Console Verification

#### 7.10.1 Verify IDP Module Structure

```bash
# Check all IDP files exist
ls -la apps/ai_chatbot/ai_chatbot/idp/
ls -la apps/ai_chatbot/ai_chatbot/idp/extractors/
ls -la apps/ai_chatbot/ai_chatbot/tools/idp.py
```

**Expected**: Files present:
- `idp/__init__.py`, `schema.py`, `mapper.py`, `validators.py`, `comparison.py`
- `idp/extractors/__init__.py`, `base.py`, `pdf_extractor.py`, `excel_extractor.py`, `docx_extractor.py`, `image_extractor.py`
- `tools/idp.py`

#### 7.10.2 Verify Schema Discovery

```bash
bench --site <SITE> execute "from ai_chatbot.idp.schema import get_doctype_schema; import json; s = get_doctype_schema('Sales Invoice'); print(json.dumps({'doctype': s['doctype'], 'field_count': len(s['fields']), 'child_tables': list(s['child_tables'].keys())}, indent=2))"
```

**Expected**: Output shows the Sales Invoice schema with fields and child tables (e.g., `"items"`).

#### 7.10.3 Verify Schema Prompt Generation

```bash
bench --site <SITE> execute "from ai_chatbot.idp.schema import build_schema_prompt; print(build_schema_prompt('Sales Invoice')[:500])"
```

**Expected**: A human-readable description of the Sales Invoice fields with labels, types, and requirements.

#### 7.10.4 Verify Content Extraction (PDF)

```bash
# Upload a test PDF to the site first, then:
bench --site <SITE> execute "from ai_chatbot.idp.extractors.base import extract_content; r = extract_content('/private/files/test-invoice.pdf'); print(r['content_type'], len(r.get('text', '')))"
```

**Expected**: `text <character_count>` — confirming PDF text was extracted.

#### 7.10.5 Check IDP Settings Field

```bash
bench --site <SITE> execute "s = frappe.get_single('Chatbot Settings'); print('enable_idp_tools:', s.enable_idp_tools)"
```

**Expected**: `enable_idp_tools: 1` (if enabled).

---

### Troubleshooting Phase 7

#### IDP tools not appearing in tool list

1. Verify `enable_idp_tools` is checked in Chatbot Settings.
2. Ensure the import exists in `registry.py`:
   ```bash
   grep -n "idp" apps/ai_chatbot/ai_chatbot/tools/registry.py
   ```
3. Check that the `"idp"` category is in `TOOL_CATEGORIES`:
   ```bash
   bench --site <SITE> execute "from ai_chatbot.core.constants import TOOL_CATEGORIES; print(TOOL_CATEGORIES)"
   ```
4. Expected output includes `'idp': 'enable_idp_tools'`.

#### ImportError for pypdf / openpyxl / python-docx

1. Install the optional dependencies:
   ```bash
   cd apps/ai_chatbot && pip install ".[idp]"
   ```
2. If using a virtual environment, ensure you're in the correct env:
   ```bash
   which python
   # Should be: /path/to/frappe-bench/env/bin/python
   ```

#### Extraction returns empty or incorrect data

1. Check that the AI provider API key is valid and the model supports tool calling.
2. For image-based extraction, ensure the model supports Vision (GPT-4o, Claude Sonnet/Opus, Gemini).
3. Check the Error Log in ERPNext (`/app/error-log`) for "AI Chatbot IDP" entries.
4. Verify the extracted content is not empty:
   ```bash
   bench --site <SITE> execute "from ai_chatbot.idp.extractors.base import extract_content; r = extract_content('/private/files/<YOUR_FILE>'); print(r['content_type'], len(r.get('text', '') or r.get('base64', '')))"
   ```

#### "Write operations are disabled" when creating records

1. Go to Chatbot Settings → Tools tab → Data Operations section.
2. Check **Enable Write Operations**.
3. Save and retry.

#### Link field resolution not finding matches

1. Ensure the referenced customer/supplier/item exists in ERPNext.
2. The fuzzy resolver searches by: exact `name` → exact display name → LIKE display name → LIKE name.
3. If the customer naming series uses IDs (e.g., `CUST-00001`), the document's customer name (e.g., "Acme Corp") resolves via the `customer_name` field.
4. For company-scoped DocTypes, ensure the correct company is set.

---

### 7.11 Pre-Extraction User Preferences

Tests that the LLM asks for missing preferences before extraction.

#### 7.11.1 All Preferences Missing

1. Upload a document (PDF or image).
2. Send:
   > "Extract data from this invoice and map it to a Purchase Invoice."
3. **Expected**: The AI asks for ALL four preferences in a single message:
   - Output Language (default: English)
   - Is Stock Item? (yes/no)
   - Is Fixed Asset? (yes/no)
   - Item Group
4. Reply with your choices (e.g., "English, stock items, not fixed assets, Item Group: Consumable").
5. **Expected**: The AI proceeds to call `extract_document_data`.

#### 7.11.2 Partial Preferences in Initial Message

1. Upload a document.
2. Send:
   > "Extract data from this invoice and map it to a Purchase Invoice. Items are stock items, Item Group: Consumable."
3. **Expected**: The AI asks ONLY for the missing preferences:
   - Output Language
   - Is Fixed Asset?
4. It does NOT re-ask about Stock Item or Item Group (already provided).

#### 7.11.3 All Preferences in Initial Message

1. Upload a document.
2. Send:
   > "Extract data from this invoice in English and map it to a Purchase Invoice. Items are stock items, not fixed assets, Item Group: Consumable."
3. **Expected**: The AI proceeds directly to extraction without asking any questions.

#### 7.11.4 Language Specified Inline

1. Upload a document.
2. Send:
   > "Extract this invoice in Spanish as a Sales Invoice."
3. **Expected**: The AI recognizes "in Spanish" as the output language and asks only for Is Stock Item, Is Fixed Asset, and Item Group.

---

### 7.12 Output Language Translation

Tests that extracted data is translated to the specified output language.

#### 7.12.1 Non-English Document with English Output

1. Upload an invoice in a non-English language (e.g., Polish, Spanish, Arabic).
2. When asked for preferences, specify "English" as output language.
3. **Expected**: All extracted text values (item descriptions, terms, remarks, party names) are translated to English. Numbers, dates, currency codes, and proper nouns remain unchanged.

#### 7.12.2 Default Language is English

1. Upload a non-English invoice.
2. When asked for output language, reply "skip" or "use defaults".
3. **Expected**: The AI uses English as the default output language.

---

### 7.13 Image Attachments with file_url

Tests that image attachments pass the file_url to the LLM so it can call IDP tools.

#### 7.13.1 Image File with Spaces in Filename

1. Upload an image file with spaces in the filename (e.g., "WhatsApp Image 2025-03-13 at 11.47.07_21b1bac3.jpg").
2. Send:
   > "Extract data from this image and map it to a Purchase Invoice. Items are stock items, Item Group: Consumable."
3. **Expected**:
   - The AI asks for missing preferences (Output Language, Is Fixed Asset).
   - After providing preferences, the AI calls `extract_document_data` with the correct `file_url` (e.g., `/private/files/WhatsApp Image 2025-03-13 at 11.47.07_21b1bac3.jpg`).
   - Extraction succeeds and the AI presents extracted fields.

#### 7.13.2 Image File without Spaces

1. Upload an image file without spaces in the filename (e.g., "invoice.jpg").
2. Send:
   > "Extract data from this image and map it to a Sales Invoice."
3. **Expected**: Same flow — preferences asked, extraction succeeds.

#### 7.13.3 Verify LLM Receives file_url

If extraction fails with a "file not found" error, check the Error Log (`/app/error-log`) for "AI Chatbot - Tool Execution" entries. The `file_url` in the arguments should match the actual uploaded file URL, not a guessed path like `/private/files/image.jpg`.

---

### 7.14 Auto-Create Missing Masters

Tests that the system can auto-create missing Customer, Supplier, Item, and UOM records.

#### 7.14.1 Missing Customer/Supplier

1. Upload an invoice with a customer/supplier name that does NOT exist in ERPNext.
2. Extract and confirm creation.
3. **Expected**: The AI reports missing masters and asks:
   - "Should I create the missing Customer/Supplier?"
   - "For Items: Is Stock Item? Is Fixed Asset? Item Group?"
4. Confirm. The AI calls `create_from_extracted_data` with `create_missing_masters='true'` and `item_defaults_json`.
5. **Expected**: Masters are auto-created and the document is saved successfully.

#### 7.14.2 Missing Items

1. Upload an invoice with item codes that don't exist in ERPNext.
2. Follow the flow — confirm auto-creation with item defaults.
3. **Expected**: Items are created with the specified `is_stock_item`, `is_fixed_asset`, and `item_group`. The document is created with the new items.

---

### 7.15 Terms and Remarks Saving

#### 7.15.1 Invoice with Terms and Conditions

1. Upload an invoice that contains terms and conditions text.
2. Extract and create as a Sales Invoice or Purchase Invoice.
3. Open the created record in ERPNext.
4. **Expected**: The `terms` field (Text Editor) contains the extracted terms text. The `tc_name` (Link to Terms and Conditions template) is NOT set (unless it matches an actual template).

#### 7.15.2 Invoice with Remarks/Notes

1. Upload an invoice that contains remarks, notes, or bank details.
2. Extract and create.
3. **Expected**: The `remarks` field contains the extracted remarks text.

---

## Phase 8: Multi-Agent Orchestration

Multi-agent orchestration adds a planner → analyst → synthesis pipeline for complex, multi-step queries. Simple queries continue to use the existing single-pass tool-calling flow unchanged.

### Prerequisites

```bash
cd ~/frappe-bench
bench --site $SITE migrate
cd apps/ai_chatbot/frontend && npm run build
bench --site $SITE clear-cache
```

---

### 8.1 Enable Agent Orchestration

1. Navigate to **Chatbot Settings** (`/app/chatbot-settings`).
2. Scroll to the **Tools** tab.
3. Find the **Agent Orchestration** section (below "Enable Write Operations").
4. Check **Enable Agent Orchestration**.
5. Click **Save**.
6. **Expected**: The checkbox saves without errors. The setting is visible under the Tools tab.

---

### 8.2 Simple Query Bypass

Verifies that simple queries do NOT trigger orchestration and use the normal flow.

#### 8.2.1 Short Query

1. Open the chatbot.
2. Send:
   > "Show me sales this month"
3. **Expected**: The response appears normally — no "Analyzing your query..." panel, no step-by-step breakdown. The AI uses the standard tool-calling flow (you may see the usual tool call indicators).

#### 8.2.2 Single-Tool Query

1. Send:
   > "What is the receivable aging?"
2. **Expected**: Normal single-pass response. No orchestration panel visible.

#### 8.2.3 Non-Data Query

1. Send:
   > "Hello, how are you?"
2. **Expected**: Normal conversational response with no orchestration.

---

### 8.3 Complex Query — Orchestration Triggered

Verifies that complex, multi-step queries trigger the multi-agent pipeline.

#### 8.3.1 Comparison Query

1. Send:
   > "Compare this quarter's sales across all regions and suggest improvements based on the trends"
2. **Expected**:
   - An **"Analyzing your query..."** panel appears (brain icon with collapsible header).
   - The panel shows a numbered list of 2–6 steps (e.g., "Fetch quarterly sales data", "Analyze regional trends", etc.).
   - Each step shows a spinner while running, then a checkmark (✓) when completed.
   - After all steps complete, the panel auto-collapses and the AI streams a synthesized response that references data from multiple steps.

#### 8.3.2 Analysis Query

1. Send:
   > "Give me a comprehensive analysis of our financial health including revenue trends, expense breakdown, and profitability ratios"
2. **Expected**: Same orchestration behavior — plan appears, steps execute with progress indicators, synthesized response follows.

#### 8.3.3 Root Cause Query

1. Send:
   > "What's causing the decline in profitability this quarter compared to last quarter and what actions should we take?"
2. **Expected**: Orchestration triggers. The plan should include data-gathering steps (fetching profit data for both quarters) and an analysis step.

---

### 8.4 AgentThinking Panel — UI Verification

#### 8.4.1 Panel Visibility

1. Trigger a complex query (e.g., from 8.3.1).
2. **Expected**:
   - The panel header shows a brain icon and "Analyzing your query..." text.
   - A chevron (▼) on the right allows collapsing/expanding the panel.
   - Steps are listed with their descriptions and status icons.

#### 8.4.2 Step Status Icons

1. While a complex query is running, observe the panel.
2. **Expected**:
   - **Pending steps**: Show a step number (1, 2, 3...) in a grey circle.
   - **Running step**: Shows an animated spinner in indigo/blue.
   - **Completed step**: Shows a green checkmark (✓).
   - **Failed step**: Shows a red X.
   - **Skipped step**: Shows a grey dash (—).

#### 8.4.3 Auto-Collapse on Synthesis

1. Watch the panel during a complex query.
2. **Expected**: When the AI starts streaming the final synthesized response, the panel automatically collapses (steps hidden, header still visible). You can click to re-expand it.

#### 8.4.4 Manual Collapse/Expand

1. While the panel is visible, click the chevron to collapse.
2. Click again to expand.
3. **Expected**: Panel toggles smoothly between collapsed and expanded states.

---

### 8.5 Streaming Verification

#### 8.5.1 Streamed Synthesis

1. Ensure streaming is enabled in Chatbot Settings.
2. Send a complex query.
3. **Expected**:
   - Step execution happens first (visible in the AgentThinking panel).
   - After steps complete, the "Synthesizing results..." process step briefly appears.
   - The final response streams token-by-token (same streaming behavior as normal responses).

#### 8.5.2 Tool Call Events During Steps

1. Open the browser DevTools → Console.
2. Send a complex query.
3. **Expected**: You should see realtime events in the socket traffic:
   - `ai_chat_agent_plan` — Contains the plan array with step_id, description, tool_hint.
   - `ai_chat_agent_step_start` — For each step, with step_id, step_number, total_steps.
   - `ai_chat_tool_call` / `ai_chat_tool_result` — For each tool executed within a step.
   - `ai_chat_agent_step_result` — After each step, with status and summary.
   - `ai_chat_token` — During synthesis streaming.

---

### 8.6 Error Resilience

#### 8.6.1 Partial Step Failure

1. Send a complex query that references both valid and potentially problematic data (e.g., a DocType that may not have data).
2. **Expected**: If one step fails:
   - The failed step shows a red X in the panel.
   - The remaining steps continue to execute.
   - The synthesis response is produced using the data from the successful steps and mentions any gaps.

#### 8.6.2 Graceful Fallback

1. If orchestration fails entirely (e.g., planner returns invalid JSON, or >50% of steps fail):
2. **Expected**: The system falls back to the standard single-pass tool-calling flow. The user still gets a response (possibly less detailed), not an error.

#### 8.6.3 Check Error Logs

1. After any failure scenario, navigate to **Error Log** (`/app/error-log`).
2. Filter for "AI Chatbot Agent".
3. **Expected**: Errors are logged with descriptive messages (e.g., "Agent classifier error", "Agent analyst error (step 1)", "Agent planner error").

---

### 8.7 Toggle Test — Disable Orchestration

1. Navigate to **Chatbot Settings** → **Tools** tab.
2. Uncheck **Enable Agent Orchestration** and save.
3. Send the same complex query from 8.3.1:
   > "Compare this quarter's sales across all regions and suggest improvements based on the trends"
4. **Expected**: No orchestration panel appears. The query is handled by the standard tool-calling flow (may produce a simpler response with fewer tool calls).
5. Re-enable the setting for further testing.

---

### 8.8 Non-Streaming Mode

1. Disable streaming in Chatbot Settings (if applicable).
2. Send a complex query.
3. **Expected**: The response appears all at once (no token-by-token streaming) but still uses orchestration — the final message includes data from multiple tool calls. The AgentThinking panel may not appear (non-streaming doesn't publish realtime events for step progress), but the response quality should match streaming mode.

---

### 8.9 Edge Cases

#### 8.9.1 Empty/Whitespace Message

1. Try to send an empty message or one with only spaces.
2. **Expected**: Handled gracefully — no orchestration triggered, no errors.

#### 8.9.2 Very Long Query

1. Send a very long complex query (100+ words with multiple analysis requests).
2. **Expected**: Orchestration triggers. The planner produces a plan with up to 6 steps (max cap). No steps are duplicated.

#### 8.9.3 Query in Non-English Language

1. If you have language selection enabled, switch to another language.
2. Send a complex query in that language (e.g., Hindi: "इस तिमाही की बिक्री की तुलना पिछली तिमाही से करें और सुधार सुझाएं").
3. **Expected**: Orchestration can still trigger (the classifier checks for complexity patterns). The response should be in the selected language.

#### 8.9.4 No Tools Available

1. Temporarily disable all tool categories in Chatbot Settings.
2. Send a complex query.
3. **Expected**: Orchestration is NOT triggered (no tools to work with). The AI responds conversationally without tool calls.

---

### 8.10 Verify Token Tracking

1. Send a complex query that triggers orchestration.
2. After the response appears, check the conversation in the database or via the admin panel.
3. **Expected**: The `tokens_used` on the Chatbot Message and `total_tokens` on the Chatbot Conversation reflect the combined usage across classification + planning + analyst steps + synthesis.
4. Navigate to **Token Usage** (`/app/token-usage`).
5. **Expected**: A token usage record is created for the orchestrated response.
