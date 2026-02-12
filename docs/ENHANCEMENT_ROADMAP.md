# AI Chatbot — Phase-wise Enhancement Roadmap

## Current State Summary

The AI Chatbot is a functional Frappe app with:

- **3 DocTypes:** Chatbot Settings (Single), Chatbot Conversation, Chatbot Message
- **10 tools** across 6 modules: CRM (2), Selling (2), Buying (2), Stock (2), Account (2), HRMS (0 — placeholder)
- **2 AI providers:** OpenAI (GPT-4o) and Claude (Sonnet 4.5)
- **Vue 3 frontend:** 5 components, 1 page (ChatView), Tailwind CSS
- **No multi-company support** — all tools query across companies
- **No multi-currency support** — monetary values summed without conversion
- **No streaming** — placeholder only, falls back to non-streaming
- **SQL injection vulnerabilities** in selling.py and stock.py (raw string interpolation)

---

## Design Principles (All Phases)

1. **Multi-Company by default:** Every tool that queries financial/transactional data MUST accept a `company` parameter. Default to the user's default company (`frappe.defaults.get_user_default("Company")`).
2. **Multi-Currency aware:** Monetary aggregations must use `base_grand_total` (company currency) or explicitly convert using ERPNext's currency exchange rates. Tool responses should include the currency code.
3. **Backward compatible:** Each phase must leave the app fully functional. No half-finished features merged.
4. **Incremental dependencies:** Only add Python/npm packages when the phase that needs them is being implemented.
5. **Frappe-native patterns:** Use Frappe ORM (`frappe.get_all`, `frappe.get_list`) instead of raw SQL. Use `frappe.qb` (Query Builder) for complex queries.

---

## Phase 1: Foundation — Core Framework, Data Layer & Security Fixes

**Goal:** Fix existing issues, add multi-company/multi-currency support, create a clean data layer that all future tools build on.

### 1.1 Core Framework (`ai_chatbot/core/`)

Create shared infrastructure used by all subsequent phases.

```
ai_chatbot/core/
├── __init__.py
├── config.py          # Centralized app configuration
├── constants.py       # App-wide constants (default limits, date formats, etc.)
├── exceptions.py      # Custom exception classes
└── logger.py          # Structured logging wrapper around frappe.log_error
```

**config.py** — Reads from Chatbot Settings DocType and provides typed access:
- `get_default_company()` → returns user's default company
- `get_company_currency(company)` → returns company's default currency
- `get_enabled_tools()` → returns list of enabled tool categories
- `get_ai_provider()` → returns configured provider name and settings

**exceptions.py** — Custom exceptions for clear error handling:
- `ChatbotError` (base)
- `ToolExecutionError`
- `ProviderError`
- `ValidationError`
- `PermissionError`

### 1.2 Data Layer (`ai_chatbot/data/`)

A centralized data access layer that all tools use. This eliminates raw SQL and enforces multi-company/multi-currency patterns.

```
ai_chatbot/data/
├── __init__.py
├── queries.py         # Read-only data provider (frappe.get_all / frappe.qb)
├── operations.py      # Create, update, delete operations (Phase 3)
├── analytics.py       # Aggregation queries (SUM, COUNT, GROUP BY)
└── currency.py        # Currency conversion utilities
```

**queries.py** — Generic read helpers:
- `get_documents(doctype, filters, fields, company=None, order_by=None, limit=None)` — wrapper around `frappe.get_all` that auto-injects company filter
- `get_document(doctype, name)` — single document fetch with permission check
- `get_count(doctype, filters, company=None)` — count with company filter

**analytics.py** — Aggregation helpers using `frappe.qb`:
- `get_sum(doctype, field, filters, company=None)` — SUM with company filter
- `get_grouped_sum(doctype, sum_field, group_field, filters, company=None)` — GROUP BY
- `get_time_series(doctype, value_field, date_field, filters, company=None, granularity="monthly")` — time-bucketed aggregation
- `get_top_n(doctype, value_field, group_field, filters, company=None, limit=10)` — top N by value

**currency.py** — Multi-currency utilities:
- `get_exchange_rate(from_currency, to_currency, date=None)` — uses ERPNext's Currency Exchange doctype
- `convert_to_company_currency(amount, from_currency, company, date=None)` — converts to base currency
- `get_base_amount_field(doctype)` — returns the base currency field name (e.g., `base_grand_total` for Sales Invoice)
- `format_currency(amount, currency)` — format with symbol

### 1.3 Security Fixes

**Eliminate SQL injection vulnerabilities:**
- `selling.py: get_top_customers()` — rewrite using `frappe.qb` or `frappe.get_all` with GROUP BY
- `stock.py: get_inventory_summary()` — rewrite using `frappe.qb`
- `stock.py: get_low_stock_items()` — rewrite using `frappe.qb`, fix unused `threshold_days` parameter

### 1.4 Refactor Existing Tools for Multi-Company & Multi-Currency

Every existing tool gets updated:

| Tool | Add `company` param | Use `base_grand_total` | Return currency |
|------|---------------------|----------------------|-----------------|
| get_lead_statistics | Yes (Lead has company) | N/A | N/A |
| get_opportunity_pipeline | Yes | Yes (`opportunity_amount` → base) | Yes |
| get_sales_analytics | Yes | Yes (`base_grand_total`) | Yes |
| get_top_customers | Yes | Yes (`base_grand_total`) | Yes |
| get_purchase_analytics | Yes | Yes (`base_grand_total`) | Yes |
| get_supplier_performance | Yes | Yes (`base_grand_total`) | Yes |
| get_inventory_summary | Yes (via warehouse→company) | Yes (`stock_value` is base) | Yes |
| get_low_stock_items | Yes (via warehouse→company) | N/A (quantities) | N/A |
| get_financial_summary | Yes | Yes (`base_grand_total`) | Yes |
| get_cash_flow_analysis | Yes | Yes (`base_paid_amount`) | Yes |

**Tool schema update pattern:**
```python
# Every monetary tool adds these parameters:
{
    "company": {
        "type": "string",
        "description": "Company name. Defaults to user's default company."
    },
    "currency": {
        "type": "string",
        "description": "Display currency. Defaults to company currency."
    }
}
```

**Tool response update pattern:**
```python
# Every monetary tool returns currency info:
{
    "total_revenue": 150000.00,
    "currency": "USD",
    "company": "My Company LLC",
    # ... rest of data
}
```

### 1.5 Tool Registry (`ai_chatbot/tools/registry.py`)

Replace the current `hasattr()` lookup in `base.py` with a proper registry:

```python
# Tools self-register with metadata
@register_tool(
    name="get_sales_analytics",
    category="selling",
    requires=["enable_sales_tools"],
    description="Get sales analytics including revenue, orders, and growth trends"
)
def get_sales_analytics(from_date=None, to_date=None, customer=None, company=None):
    ...
```

Benefits:
- Tool discovery without dynamic import scanning
- Metadata for categorization, permissions, and feature flags
- Easier to add new tools in later phases

### 1.6 Deliverables

| Item | Files |
|------|-------|
| Core framework | `core/__init__.py`, `config.py`, `constants.py`, `exceptions.py`, `logger.py` |
| Data layer | `data/__init__.py`, `queries.py`, `analytics.py`, `currency.py` |
| Tool registry | `tools/registry.py`, updated `tools/base.py` |
| Refactored tools | Updated `crm.py`, `selling.py`, `buying.py`, `stock.py`, `account.py` |
| Security fixes | SQL injection eliminated in `selling.py`, `stock.py` |

**New dependencies:** None (uses only Frappe built-ins).

---

## Phase 2: Streaming (SSE) & Enhanced Chat Experience

**Goal:** Implement real-time token streaming for AI responses. Improve chat UX.

### 2.1 Backend Streaming (`ai_chatbot/api/streaming.py`)

```
ai_chatbot/api/
├── chat.py            # Existing (updated for streaming flag)
└── streaming.py       # NEW: SSE endpoint
```

**SSE endpoint:**
- `stream_response(conversation_id, message)` — returns `text/event-stream` response
- Uses Frappe's response object to send SSE events
- Event types: `token` (partial text), `tool_call` (tool invocation), `tool_result` (tool output), `done` (completion), `error`
- Handles tool calling mid-stream: pauses streaming → executes tool → resumes with tool result

**Provider updates (`ai_chatbot/utils/ai_providers.py`):**
- `OpenAIProvider.chat_completion_stream()` — yield tokens from OpenAI streaming API
- `ClaudeProvider.chat_completion_stream()` — yield tokens from Claude streaming API
- Both yield structured events: `{"type": "token", "content": "..."}`

### 2.2 Frontend Streaming (`frontend/src/utils/streaming.js`)

```
frontend/src/
├── utils/
│   ├── api.js          # Existing
│   └── streaming.js    # NEW: EventSource client
├── components/
│   ├── ChatMessage.vue # Updated for streaming state
│   └── StreamingMessage.vue  # NEW: renders partial content
```

**streaming.js:**
- `StreamingClient` class wrapping `EventSource` API
- Handles reconnection, error recovery
- Emits events to Vue components via callback

**StreamingMessage.vue:**
- Renders tokens as they arrive
- Shows tool call execution inline (tool name, arguments, result)
- Transitions to final `ChatMessage.vue` when stream completes

### 2.3 Enhanced Chat Features

- **Auto-scroll with smart behavior:** Don't force-scroll if user has scrolled up to read history
- **Message retry:** Re-send failed messages
- **Stop generation:** Abort in-progress streaming response
- **Copy message:** Copy assistant response to clipboard

### 2.4 Deliverables

| Item | Files |
|------|-------|
| SSE backend | `api/streaming.py`, updated `utils/ai_providers.py` |
| Frontend streaming | `utils/streaming.js`, `components/StreamingMessage.vue` |
| Chat UX | Updated `ChatMessage.vue`, `ChatView.vue`, `ChatInput.vue` |

**New dependencies:** None (SSE uses native browser EventSource, backend uses Frappe response).

---

## Phase 3: Data Operations (CRUD) via Chat

**Goal:** Let users create, update, and delete ERPNext documents through natural language.

### 3.1 Data Operations Layer (`ai_chatbot/data/operations.py`)

```
ai_chatbot/data/
├── operations.py      # Create, update, delete with validation
└── validators.py      # Input validation and permission checks
```

**operations.py:**
- `create_document(doctype, values, company=None)` — creates document with validation
- `update_document(doctype, name, values)` — updates fields with permission check
- `delete_document(doctype, name)` — soft-delete with confirmation pattern

**validators.py:**
- `validate_mandatory_fields(doctype, values)` — checks required fields
- `validate_link_fields(doctype, values)` — validates linked document existence
- `check_permission(doctype, name, perm_type)` — Frappe permission check wrapper

### 3.2 Operation Tools (`ai_chatbot/tools/operations/`)

```
ai_chatbot/tools/operations/
├── __init__.py
├── create.py          # Document creation tools
├── update.py          # Document update tools
└── search.py          # Document search/lookup tools
```

**Create tools:**
- `create_lead(first_name, company_name, email, phone, source, company=None)`
- `create_opportunity(party_name, opportunity_amount, currency, company=None)`
- `create_todo(description, assigned_to, date, priority)`
- `create_sales_order(customer, items, delivery_date, company=None)`

**Update tools:**
- `update_lead_status(lead_name, status)`
- `update_opportunity_status(opportunity_name, status)`

**Search tools:**
- `search_customers(query, limit=10, company=None)` — fuzzy search
- `search_items(query, limit=10, company=None)` — item lookup
- `search_documents(doctype, query, filters=None, company=None)` — generic search

### 3.3 Confirmation Pattern

For write operations, implement a two-step confirmation:

1. AI prepares the operation and presents it to the user:
   ```
   I'll create a Lead with these details:
   - Name: John Smith
   - Company: Acme Corp
   - Email: john@acme.com

   Shall I proceed?
   ```

2. User confirms → tool executes the write operation.

This is handled via a `confirmation_required` flag in the tool schema and a frontend confirmation dialog.

### 3.4 Deliverables

| Item | Files |
|------|-------|
| Data operations | `data/operations.py`, `data/validators.py` |
| Operation tools | `tools/operations/create.py`, `update.py`, `search.py` |
| Confirmation UI | Updated `ChatMessage.vue` with confirm/cancel buttons |
| Settings | Updated Chatbot Settings DocType with `enable_write_operations` flag |

**New dependencies:** None.

---

## Phase 4: Finance Tools & Business Intelligence

**Goal:** Add comprehensive financial analysis tools. This is the highest business-value phase.

### 4.1 Finance Tools (`ai_chatbot/tools/finance/`)

```
ai_chatbot/tools/finance/
├── __init__.py
├── budget.py              # Budget vs actual analysis
├── ratios.py              # Financial ratio analysis
├── profitability.py       # Profitability analysis (by customer, item, territory)
├── working_capital.py     # Working capital analysis
├── receivables.py         # Accounts receivable aging
├── payables.py            # Accounts payable aging
└── cash_flow.py           # Enhanced cash flow (replaces current account.py version)
```

**Budget tools (`budget.py`):**
- `get_budget_vs_actual(fiscal_year, company, cost_center=None)` — budget variance by account
- `get_budget_variance(fiscal_year, company, account=None)` — detailed variance with % deviation

**Financial ratios (`ratios.py`):**
- `get_liquidity_ratios(company, date=None)` — current ratio, quick ratio
- `get_profitability_ratios(company, from_date, to_date)` — gross margin, net margin, ROA
- `get_efficiency_ratios(company, from_date, to_date)` — inventory turnover, receivable days, payable days

**Profitability analysis (`profitability.py`):**
- `get_profitability_by_customer(company, from_date, to_date, limit=10)` — most/least profitable customers
- `get_profitability_by_item(company, from_date, to_date, limit=10)` — product-level margin
- `get_profitability_by_territory(company, from_date, to_date)` — geographic profitability

**Working capital (`working_capital.py`):**
- `get_working_capital_summary(company, date=None)` — receivables, payables, inventory, net WC
- `get_cash_conversion_cycle(company, from_date, to_date)` — DSO + DIO - DPO

**Receivables & payables:**
- `get_receivable_aging(company, ageing_based_on="Due Date")` — aging buckets (0-30, 31-60, 61-90, 90+)
- `get_payable_aging(company, ageing_based_on="Due Date")` — same for payables
- `get_top_debtors(company, limit=10)` — highest outstanding receivables
- `get_top_creditors(company, limit=10)` — highest outstanding payables

**Enhanced cash flow (`cash_flow.py`):**
- `get_cash_flow_statement(company, from_date, to_date)` — operating, investing, financing activities
- `get_cash_flow_trend(company, months=12)` — monthly cash flow with trend
- `get_bank_balance(company, account=None)` — current bank/cash balances

All tools:
- Accept `company` parameter (default: user's default company)
- Return `currency` field with company's base currency
- Use `base_*` fields for amounts (multi-currency safe)
- Use `frappe.qb` or `frappe.get_all` for queries (no raw SQL)

### 4.2 Enhanced Analytics Tools

Upgrade existing modules with new capabilities:

**Selling (`tools/analytics/selling.py` — replaces current `selling.py`):**
- `get_sales_trend(company, months=12, granularity="monthly")` — time series with chart data
- `get_sales_by_territory(company, from_date, to_date)` — geographic breakdown
- `get_sales_by_item_group(company, from_date, to_date)` — product category analysis
- Existing tools retained with multi-company/currency fixes

**Buying (`tools/analytics/buying.py` — replaces current `buying.py`):**
- `get_purchase_trend(company, months=12, granularity="monthly")` — time series
- `get_purchase_by_item_group(company, from_date, to_date)` — category breakdown
- Existing tools retained with fixes

**Stock (`tools/analytics/stock.py` — replaces current `stock.py`):**
- `get_stock_movement(item_code=None, warehouse=None, from_date=None, to_date=None, company=None)` — in/out movement
- `get_stock_ageing(warehouse=None, company=None)` — age of stock in warehouse
- Existing tools retained with fixes

### 4.3 Chart Data Format

Tools that return time series or categorical data include an `echart_option` field that the frontend can pass directly to ECharts:

```python
{
    "data": { ... },  # Raw data
    "echart_option": {
        "title": {"text": "Monthly Sales Revenue"},
        "xAxis": {"type": "category", "data": ["Jan", "Feb", "Mar", ...]},
        "yAxis": {"type": "value", "name": "USD"},
        "series": [{"type": "bar", "data": [12000, 15000, 13000, ...]}],
        "tooltip": {"trigger": "axis"}
    },
    "currency": "USD",
    "company": "My Company LLC"
}
```

### 4.4 Frontend Chart Rendering

```
frontend/src/components/
├── charts/
│   ├── EChartRenderer.vue     # Generic ECharts wrapper
│   └── ChartMessage.vue       # Chat message with embedded chart
```

**EChartRenderer.vue:**
- Accepts ECharts option object as prop
- Handles resize, theme, and responsive layout
- Lazy-loads ECharts library

**ChatMessage.vue update:**
- Detects `echart_option` in tool results
- Renders inline chart within the chat message

### 4.5 Deliverables

| Item | Files |
|------|-------|
| Finance tools | `tools/finance/budget.py`, `ratios.py`, `profitability.py`, `working_capital.py`, `receivables.py`, `payables.py`, `cash_flow.py` |
| Enhanced analytics | Updated `tools/analytics/selling.py`, `buying.py`, `stock.py` |
| Chart rendering | `components/charts/EChartRenderer.vue`, `ChartMessage.vue` |
| Settings | Updated DocType with `enable_finance_tools` flag |

**New dependencies:**
- **Frontend:** `echarts` (npm)
- **Backend:** None (uses Frappe ORM and ERPNext data)

---

## Phase 5: HRMS Tools & Enhanced CRM

**Goal:** Complete the HRMS placeholder and expand CRM capabilities.

### 5.1 HRMS Tools (`ai_chatbot/tools/analytics/hrms.py`)

Requires ERPNext HRMS module to be installed.

- `get_employee_count(company, department=None, status="Active")` — headcount
- `get_attendance_summary(company, from_date, to_date, department=None)` — attendance stats
- `get_leave_balance(employee=None, leave_type=None, company=None)` — leave balances
- `get_payroll_summary(company, from_date, to_date)` — total salary, deductions, net pay
- `get_department_wise_salary(company, month=None)` — salary by department
- `get_employee_turnover(company, from_date, to_date)` — joining vs leaving rate

All tools:
- Check if HRMS module is installed before executing
- Respect `company` parameter
- Payroll tools use `base_*` amounts for multi-currency

### 5.2 Enhanced CRM Tools (`ai_chatbot/tools/analytics/crm.py`)

Expand the existing 2 tools:

- `get_lead_conversion_rate(company, from_date, to_date)` — lead-to-opportunity rate
- `get_lead_source_analysis(company, from_date, to_date)` — leads by source
- `get_sales_funnel(company, from_date, to_date)` — lead → opportunity → quotation → order
- `get_customer_acquisition_cost(company, from_date, to_date)` — if campaign data available
- Existing tools updated with multi-company support

### 5.3 Deliverables

| Item | Files |
|------|-------|
| HRMS tools | `tools/analytics/hrms.py` (full implementation) |
| CRM tools | Updated `tools/analytics/crm.py` |
| Settings | HRMS feature flag, conditional on module installation |

**New dependencies:** None (queries HRMS doctypes if installed).

---

## Phase 6: Basic RAG — Document Knowledge Base

**Goal:** Let the chatbot answer questions from uploaded documents and ERPNext records using vector search.

### 6.1 RAG Backend (`ai_chatbot/ai/rag/`)

```
ai_chatbot/ai/rag/
├── __init__.py
├── embeddings.py      # Embedding generation (OpenAI/local)
├── vector_store.py    # ChromaDB interface
├── chunker.py         # Document chunking strategies
└── retriever.py       # Query → retrieve → inject into prompt
```

**embeddings.py:**
- `generate_embedding(text)` — uses OpenAI `text-embedding-3-small` or local model
- Batch embedding support for document indexing

**vector_store.py:**
- ChromaDB as the default vector store (runs locally, no external service needed)
- `add_documents(chunks, embeddings, metadata)` — index documents
- `search(query_embedding, n_results=5, filters=None)` — similarity search
- `delete_documents(source_id)` — remove indexed documents
- Collection per company (multi-company isolation)

**chunker.py:**
- `chunk_text(text, chunk_size=500, overlap=50)` — simple text chunking
- `chunk_document(file_path)` — PDF, DOCX, TXT extraction + chunking
- Metadata preservation (source document, page number, section)

**retriever.py:**
- `retrieve_context(query, company=None, n_results=5)` — end-to-end: embed query → search → return chunks
- `augment_prompt(system_prompt, query, context_chunks)` — inject retrieved context into LLM prompt

### 6.2 Knowledge Base DocType

**Chatbot Knowledge Base** (new DocType):
- Fields: `title`, `source_type` (File/ERPNext Record/URL), `source_reference`, `company`, `status` (Indexed/Pending/Failed), `chunk_count`, `last_indexed`
- Tracks what has been indexed into the vector store

### 6.3 Indexing Pipeline

- **Manual:** Upload PDF/DOCX via a "Knowledge Base" page in the frontend
- **Automatic:** Index key ERPNext records (Items, Customers, Suppliers, policies) via scheduled task
- **Incremental:** Only re-index documents that have changed since last indexing

### 6.4 Integration with Chat

The chat flow becomes:

1. User sends message
2. System checks if RAG context would help (based on query type)
3. If yes: retrieve relevant chunks from vector store
4. Inject chunks into system prompt as context
5. Send to LLM with both tools and RAG context available
6. LLM can use both tool results AND document context in its response

### 6.5 Frontend

```
frontend/src/
├── pages/
│   └── KnowledgeBaseView.vue   # Document upload and management
├── components/
│   └── documents/
│       ├── DocumentUploader.vue # File upload with drag-and-drop
│       └── DocumentList.vue     # List of indexed documents
```

### 6.6 Deliverables

| Item | Files |
|------|-------|
| RAG engine | `ai/rag/embeddings.py`, `vector_store.py`, `chunker.py`, `retriever.py` |
| Knowledge Base DocType | `chatbot/doctype/chatbot_knowledge_base/` |
| Indexing pipeline | Scheduled task in `hooks.py` |
| Frontend | `KnowledgeBaseView.vue`, `DocumentUploader.vue`, `DocumentList.vue` |
| Chat integration | Updated `api/chat.py` to call retriever |

**New dependencies:**
- **Backend:** `chromadb`, `openai` (for embeddings), `pypdf` (PDF extraction), `python-docx` (DOCX extraction)
- **Frontend:** None

---

## Phase 7: Agentic RAG — Multi-Agent Orchestration

**Goal:** Upgrade from single-pass RAG to an agentic system that plans, retrieves, evaluates, and iterates.

### 7.1 Agent Framework (`ai_chatbot/ai/agents/`)

```
ai_chatbot/ai/agents/
├── __init__.py
├── base_agent.py          # Abstract agent interface
├── orchestrator.py        # Routes queries to appropriate agent(s)
├── planner_agent.py       # Decomposes complex queries into steps
├── analyst_agent.py       # Data analysis with tool calling
└── document_agent.py      # Document retrieval and synthesis
```

**orchestrator.py:**
- Classifies incoming query: simple (generative) vs. data (tool-based) vs. knowledge (RAG) vs. complex (multi-step)
- Routes to appropriate agent or combination
- Manages agent execution loop with max iterations

**planner_agent.py:**
- Breaks complex queries into sub-tasks
- Example: "Compare Q3 vs Q4 sales and check if we're on track for budget" →
  1. Get Q3 sales (tool call)
  2. Get Q4 sales (tool call)
  3. Get budget for current year (tool call)
  4. Synthesize comparison (generation)

**analyst_agent.py:**
- Specialized for data queries
- Can chain multiple tool calls
- Evaluates whether results are sufficient or needs more data

**document_agent.py:**
- Retrieves from vector store
- Evaluates relevance of retrieved chunks
- Can re-query with refined search terms if initial results are poor

### 7.2 Memory System (`ai_chatbot/ai/memory/`)

```
ai_chatbot/ai/memory/
├── __init__.py
├── conversation_memory.py    # Short-term: current conversation context
├── knowledge_memory.py       # Long-term: persistent knowledge from RAG
└── memory_manager.py         # Manages context window allocation
```

**memory_manager.py:**
- Allocates token budget across: system prompt, memory, RAG context, conversation history, tool results
- Prunes oldest messages when context limit approached
- Prioritizes recent and relevant context

### 7.3 Deliverables

| Item | Files |
|------|-------|
| Agent framework | `ai/agents/base_agent.py`, `orchestrator.py`, `planner_agent.py`, `analyst_agent.py`, `document_agent.py` |
| Memory system | `ai/memory/conversation_memory.py`, `knowledge_memory.py`, `memory_manager.py` |
| Chat integration | Updated `api/chat.py` to use orchestrator |
| Frontend | `components/chat/AgentThinking.vue` — shows agent reasoning steps |

**New dependencies:** None beyond Phase 6 (uses same LLM providers and vector store).

---

## Phase 8: Intelligent Document Processing (IDP)

**Goal:** Extract data from uploaded documents (invoices, receipts, POs) and create ERPNext records.

### 8.1 Document Extraction (`ai_chatbot/idp/`)

```
ai_chatbot/idp/
├── __init__.py
├── extractors/
│   ├── base_extractor.py      # Abstract extractor interface
│   ├── invoice_extractor.py   # Invoice data extraction (via LLM vision)
│   ├── receipt_extractor.py   # Receipt processing
│   └── generic_extractor.py   # Generic document extraction
├── validators/
│   ├── schema_validator.py    # Validates extracted data against DocType schema
│   └── business_rules.py      # Business rule validation
└── mappers/
    ├── base_mapper.py         # Abstract mapper
    ├── invoice_mapper.py      # Maps extracted data → Purchase Invoice
    ├── supplier_mapper.py     # Maps extracted data → Supplier
    └── item_mapper.py         # Maps extracted data → Item
```

**Extraction approach:**
- Use GPT-4 Vision or Claude Vision to extract structured data from document images
- No OCR dependency for initial version (LLM vision is more accurate)
- Fallback to OCR (pytesseract) for high-volume, lower-cost processing

**Mapping flow:**
1. User uploads document (PDF/image)
2. LLM Vision extracts structured data (supplier, items, amounts, dates)
3. Validator checks against ERPNext schema and business rules
4. Mapper creates draft ERPNext document
5. User reviews and confirms (reuses Phase 3 confirmation pattern)
6. Document is submitted

**Multi-company:** Extracted documents are created in the user's default company.
**Multi-currency:** Extracted currency is preserved; ERPNext handles conversion via exchange rate on the document.

### 8.2 Frontend

```
frontend/src/
├── pages/
│   └── DocumentProcessingView.vue
├── components/
│   └── idp/
│       ├── DocumentUploader.vue    # Upload with preview
│       ├── ExtractionResult.vue    # Show extracted fields, allow editing
│       └── MappingPreview.vue      # Preview ERPNext document before creation
```

### 8.3 Deliverables

| Item | Files |
|------|-------|
| Extractors | `idp/extractors/invoice_extractor.py`, `receipt_extractor.py`, `generic_extractor.py` |
| Validators | `idp/validators/schema_validator.py`, `business_rules.py` |
| Mappers | `idp/mappers/invoice_mapper.py`, `supplier_mapper.py`, `item_mapper.py` |
| API | `api/documents.py` — upload, extract, map, create endpoints |
| Frontend | `DocumentProcessingView.vue`, extraction/mapping components |
| DocType | `chatbot_document_queue` — tracks processing status |

**New dependencies:**
- **Backend:** `pypdf` (if not added in Phase 6), `Pillow`, optionally `pytesseract` + `pdf2image`
- **Frontend:** None

---

## Phase 9: Predictive Analytics & ML

**Goal:** Add forecasting and prediction capabilities using statistical and ML models.

### 9.1 Predictive Tools (`ai_chatbot/tools/predictive/`)

```
ai_chatbot/tools/predictive/
├── __init__.py
├── demand_forecast.py         # Item demand forecasting
├── sales_forecast.py          # Revenue forecasting
├── cash_flow_forecast.py      # Cash flow projections
└── anomaly_detection.py       # Detect unusual patterns
```

**Approach:** Start with statistical models (moving averages, exponential smoothing) before adding ML. This avoids heavy dependencies initially.

**demand_forecast.py:**
- `forecast_demand(item_code, months_ahead=3, company=None)` — projects future demand based on historical sales
- Uses: time series decomposition, moving average, or Prophet (if installed)
- Returns forecast with confidence intervals + ECharts option

**sales_forecast.py:**
- `forecast_revenue(company, months_ahead=3, granularity="monthly")` — revenue projection
- `forecast_by_territory(company, months_ahead=3)` — geographic forecast

**cash_flow_forecast.py:**
- `forecast_cash_flow(company, months_ahead=3)` — projected inflows/outflows based on receivables, payables, and historical patterns

**anomaly_detection.py:**
- `detect_anomalies(company, from_date, to_date)` — flags unusual transactions (large amounts, unusual frequency, new suppliers with large orders)
- Uses: statistical thresholds (z-score, IQR) — no ML needed for initial version

### 9.2 Deliverables

| Item | Files |
|------|-------|
| Forecast tools | `tools/predictive/demand_forecast.py`, `sales_forecast.py`, `cash_flow_forecast.py` |
| Anomaly detection | `tools/predictive/anomaly_detection.py` |
| Chart support | ECharts options in all forecast responses |
| Settings | `enable_predictive_tools` flag |

**New dependencies (optional, phased):**
- **Minimal:** `pandas`, `numpy` (likely already available in Frappe environment)
- **Enhanced:** `prophet` (Facebook's time series forecasting — optional, heavier install)
- **Advanced (future):** `scikit-learn`, `xgboost` — only when needed

---

## Phase 10: Automation & Notifications

**Goal:** Scheduled reports, alerts, and automated workflows triggered by chat or conditions.

### 10.1 Notification System (`ai_chatbot/automation/notifications/`)

```
ai_chatbot/automation/notifications/
├── __init__.py
├── channels/
│   ├── email.py               # Email notifications via Frappe
│   ├── whatsapp.py            # WhatsApp via Twilio (already a dependency)
│   └── slack.py               # Slack webhook integration
└── alerts.py                  # Alert rule engine
```

**alerts.py:**
- `ChatbotAlert` DocType — defines conditions and actions
- Example alerts:
  - "Notify me when receivables exceed 500,000"
  - "Send weekly sales summary every Monday"
  - "Alert when stock of Item X falls below reorder level"
- Uses Frappe's scheduled tasks (`hooks.py`) for periodic checks

### 10.2 Scheduled Reports

- `generate_scheduled_report(report_type, company, recipients)` — generates report and sends via email/WhatsApp
- Report types: daily sales summary, weekly financial summary, monthly P&L
- Uses existing tool functions to gather data, formats as HTML email or PDF

### 10.3 Deliverables

| Item | Files |
|------|-------|
| Notifications | `automation/notifications/channels/email.py`, `whatsapp.py`, `slack.py` |
| Alert engine | `automation/notifications/alerts.py`, `ChatbotAlert` DocType |
| Scheduled reports | Hooks in `hooks.py`, report templates |
| Settings | Alert configuration in Chatbot Settings |

**New dependencies:** `slack_sdk` (optional, for Slack integration). Twilio already present.

---

## Phase Summary

| Phase | Focus | Key Deliverable | Dependencies Added |
|-------|-------|------------------|--------------------|
| **1** | Foundation | Data layer, multi-company/currency, security fixes | None |
| **2** | Streaming | SSE token streaming, enhanced chat UX | None |
| **3** | CRUD | Create/update/delete ERPNext records via chat | None |
| **4** | Finance | 20+ finance tools, ECharts integration | echarts (npm) |
| **5** | HRMS & CRM | Complete HRMS tools, expanded CRM | None |
| **6** | Basic RAG | ChromaDB vector search, knowledge base | chromadb, pypdf |
| **7** | Agentic RAG | Multi-agent orchestration, memory system | None |
| **8** | IDP | Document extraction → ERPNext records | Pillow, pytesseract (optional) |
| **9** | Predictive | Forecasting, anomaly detection | pandas, numpy, prophet (optional) |
| **10** | Automation | Alerts, scheduled reports, notifications | slack_sdk (optional) |

---

## Multi-Company & Multi-Currency Reference

### Multi-Company Pattern

Every tool that queries transactional data follows this pattern:

```python
def get_sales_analytics(from_date=None, to_date=None, company=None):
    """Get sales analytics for a specific company."""
    if not company:
        company = frappe.defaults.get_user_default("Company")

    if not company:
        frappe.throw("Please specify a company or set a default company.")

    filters = {"docstatus": 1, "company": company}
    if from_date:
        filters["posting_date"] = [">=", from_date]
    if to_date:
        filters["posting_date"] = ["<=", to_date]

    # ... query with filters

    return {
        "company": company,
        "currency": frappe.get_cached_value("Company", company, "default_currency"),
        # ... data
    }
```

### Multi-Currency Pattern

For monetary aggregations, always use base currency fields:

| DocType | Transaction Amount | Base Amount (use this) |
|---------|-------------------|----------------------|
| Sales Invoice | `grand_total` | `base_grand_total` |
| Purchase Invoice | `grand_total` | `base_grand_total` |
| Sales Order | `grand_total` | `base_grand_total` |
| Purchase Order | `grand_total` | `base_grand_total` |
| Payment Entry | `paid_amount` | `base_paid_amount` |
| Opportunity | `opportunity_amount` | (convert manually using party currency) |
| Journal Entry | `debit` / `credit` | `debit_in_account_currency` is the foreign; `debit` is base |

When a user asks for data in a specific currency (e.g., "Show sales in EUR"):
1. Query using `base_*` fields (company currency)
2. Convert to requested currency using `currency.get_exchange_rate()`
3. Return both the amount and currency code

### Company Isolation for RAG (Phase 6+)

Vector store collections are namespaced by company:
- Collection name: `knowledge_{company_name_slug}`
- Queries only search the current user's company collection
- Cross-company search requires explicit permission

---

## File Structure After All Phases

```
ai_chatbot/
├── core/                          # Phase 1
│   ├── config.py
│   ├── constants.py
│   ├── exceptions.py
│   └── logger.py
│
├── data/                          # Phase 1, 3
│   ├── queries.py
│   ├── analytics.py
│   ├── currency.py
│   ├── operations.py              # Phase 3
│   └── validators.py              # Phase 3
│
├── api/                           # Phase 1, 2, 3, 8
│   ├── chat.py
│   ├── streaming.py               # Phase 2
│   └── documents.py               # Phase 8
│
├── utils/
│   └── ai_providers.py
│
├── tools/                         # Phase 1, 3, 4, 5, 9
│   ├── registry.py                # Phase 1
│   ├── base.py
│   ├── operations/                # Phase 3
│   │   ├── create.py
│   │   ├── update.py
│   │   └── search.py
│   ├── analytics/                 # Phase 1 (refactored), 4, 5
│   │   ├── crm.py
│   │   ├── selling.py
│   │   ├── buying.py
│   │   ├── stock.py
│   │   ├── accounts.py
│   │   └── hrms.py               # Phase 5
│   ├── finance/                   # Phase 4
│   │   ├── budget.py
│   │   ├── ratios.py
│   │   ├── profitability.py
│   │   ├── working_capital.py
│   │   ├── receivables.py
│   │   ├── payables.py
│   │   └── cash_flow.py
│   └── predictive/                # Phase 9
│       ├── demand_forecast.py
│       ├── sales_forecast.py
│       ├── cash_flow_forecast.py
│       └── anomaly_detection.py
│
├── ai/                            # Phase 6, 7
│   ├── rag/                       # Phase 6
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   ├── chunker.py
│   │   └── retriever.py
│   ├── agents/                    # Phase 7
│   │   ├── base_agent.py
│   │   ├── orchestrator.py
│   │   ├── planner_agent.py
│   │   ├── analyst_agent.py
│   │   └── document_agent.py
│   └── memory/                    # Phase 7
│       ├── conversation_memory.py
│       ├── knowledge_memory.py
│       └── memory_manager.py
│
├── idp/                           # Phase 8
│   ├── extractors/
│   ├── validators/
│   └── mappers/
│
├── automation/                    # Phase 10
│   └── notifications/
│       ├── channels/
│       └── alerts.py
│
├── chatbot/                       # Frappe DocTypes (expanded across phases)
│   └── doctype/
│       ├── chatbot_settings/
│       ├── chatbot_conversation/
│       ├── chatbot_message/
│       ├── chatbot_knowledge_base/    # Phase 6
│       ├── chatbot_document_queue/    # Phase 8
│       └── chatbot_alert/             # Phase 10
│
└── tests/                         # All phases
    ├── unit/
    ├── integration/
    └── fixtures/

frontend/src/
├── components/
│   ├── chat/                      # Phase 2
│   │   ├── ChatHeader.vue
│   │   ├── ChatMessage.vue
│   │   ├── ChatInput.vue
│   │   ├── StreamingMessage.vue   # Phase 2
│   │   └── AgentThinking.vue      # Phase 7
│   ├── charts/                    # Phase 4
│   │   ├── EChartRenderer.vue
│   │   └── ChartMessage.vue
│   ├── documents/                 # Phase 6
│   │   ├── DocumentUploader.vue
│   │   └── DocumentList.vue
│   └── idp/                       # Phase 8
│       ├── ExtractionResult.vue
│       └── MappingPreview.vue
├── pages/
│   ├── ChatView.vue
│   ├── KnowledgeBaseView.vue      # Phase 6
│   └── DocumentProcessingView.vue # Phase 8
├── composables/                   # Phase 2+
│   ├── useChat.js
│   └── useStreaming.js
└── utils/
    ├── api.js
    └── streaming.js               # Phase 2
```
