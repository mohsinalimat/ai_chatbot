# AI Chatbot — Phase-wise Enhancement Roadmap

## Current State Summary (Post Phase 4)

The AI Chatbot is a functional Frappe app with:

- **3 DocTypes:** Chatbot Settings (Single), Chatbot Conversation, Chatbot Message
- **34 tools** across 8 categories: CRM (2), Selling (5), Buying (4), Stock (4), Account (2), Finance (17), HRMS (0 — placeholder), Operations (3 — create/update/search)
- **2 AI providers:** OpenAI (GPT-4o) and Claude (Sonnet 4.5)
- **Streaming:** Real-time token streaming via Frappe Realtime (Socket.IO/WebSocket)
- **CRUD:** Create, update, search ERPNext records via chat with confirmation pattern
- **ECharts:** Inline chart rendering (bar, line, pie, horizontal bar, multi-series) with multi-color palette
- **Multi-company & multi-currency:** All tools use `company` parameter and `base_*` fields
- **Data layer:** `frappe.qb` Query Builder throughout — no raw SQL
- **Vue 3 frontend:** Components for chat, streaming, charts, tool calls

---

## Design Principles (All Phases)

1. **Multi-Company by default:** Every tool that queries financial/transactional data MUST accept a `company` parameter. Default to the user's default company (`frappe.defaults.get_user_default("Company")`).
2. **Multi-Currency aware:** Monetary aggregations must use `base_grand_total` (company currency) or explicitly convert using ERPNext's currency exchange rates. Tool responses should include the currency code.
3. **Backward compatible:** Each phase must leave the app fully functional. No half-finished features merged.
4. **Incremental dependencies:** Only add Python/npm packages when the phase that needs them is being implemented.
5. **Frappe-native patterns:** Use Frappe ORM (`frappe.get_all`, `frappe.get_list`) instead of raw SQL. Use `frappe.qb` (Query Builder) for complex queries.
6. **Permission-aware:** Respect Frappe's permission model. Users should only access data they are authorized to see.

---

## Completed Phases

### Phase 1: Foundation ✅

Core framework (`core/config.py`, `constants.py`, `exceptions.py`, `logger.py`), data layer (`data/queries.py`, `analytics.py`, `currency.py`), tool registry (`tools/registry.py`), multi-company/currency refactor of all tools, SQL injection fixes.

### Phase 2: Streaming ✅

Token-by-token streaming via `frappe.publish_realtime` (Socket.IO/WebSocket through Redis Pub/Sub). Provider streaming for OpenAI and Claude. Frontend composable (`useStreaming.js`), streaming message rendering, auto-scroll, tool call display during stream.

### Phase 3: Data Operations (CRUD) ✅

Create/update/search tools (`tools/operations/`). Document creation (Lead, Opportunity, ToDo, Sales Order), status updates, fuzzy search. Two-step confirmation pattern for write operations. `enable_write_operations` settings flag.

### Phase 4: Finance Tools & Business Intelligence ✅

17 finance tools across 7 modules (receivables, payables, cash flow, budget, profitability, working capital, ratios). Enhanced selling (3), buying (2), stock (2) tools with charts. ECharts frontend integration (`EChartRenderer.vue`, `ChartMessage.vue`). Tool results persistence. Multi-color chart palette.

---

## Phase 5: HRMS Tools & Enhanced CRM

**Goal:** Complete the HRMS placeholder and expand CRM capabilities.

### 5.1 HRMS Tools (`ai_chatbot/tools/hrms.py`)

Requires ERPNext HRMS module to be installed.

- `get_employee_count(company, department=None, status="Active")` — headcount with department breakdown
- `get_attendance_summary(company, from_date, to_date, department=None)` — attendance stats (present, absent, leave, half-day)
- `get_leave_balance(employee=None, leave_type=None, company=None)` — leave balances by type
- `get_payroll_summary(company, from_date, to_date)` — total salary, deductions, net pay with chart
- `get_department_wise_salary(company, month=None)` — salary by department with pie chart
- `get_employee_turnover(company, from_date, to_date)` — joining vs leaving rate with trend chart

All tools:
- Check if HRMS module is installed before executing (`frappe.get_installed_apps()`)
- Respect `company` parameter
- Payroll tools use `base_*` amounts for multi-currency
- Return ECharts options where applicable

### 5.2 Enhanced CRM Tools (`ai_chatbot/tools/crm.py`)

Expand the existing 2 tools:

- `get_lead_conversion_rate(company, from_date, to_date)` — lead-to-opportunity conversion rate with funnel chart
- `get_lead_source_analysis(company, from_date, to_date)` — leads by source with pie chart
- `get_sales_funnel(company, from_date, to_date)` — lead → opportunity → quotation → order pipeline with funnel visualization
- `get_customer_acquisition_cost(company, from_date, to_date)` — CAC if campaign data available
- Existing tools (`get_lead_statistics`, `get_opportunity_pipeline`) updated with ECharts

### 5.3 Settings

- Add `enable_hrms_tools` flag to Chatbot Settings
- Conditional on HRMS module installation (graceful fallback)

### 5.4 Deliverables

| Item | Files |
|------|-------|
| HRMS tools | `tools/hrms.py` (full implementation) |
| CRM tools | Updated `tools/crm.py` with 4 new tools + charts |
| Settings | `enable_hrms_tools` flag, conditional on module installation |

**New dependencies:** None (queries HRMS doctypes if installed).

---

## Phase 5A: UX & Accessibility

**Goal:** Enhance the chat interface with usability features — sidebar toggle, voice input, prompt suggestions, and improved chart/table rendering. All changes are frontend-only or frontend-heavy.

### 5A.1 Sidebar Toggle

**Files:** `frontend/src/pages/ChatView.vue`, `frontend/src/components/Sidebar.vue`

- Add `sidebarCollapsed` ref in ChatView.vue
- Toggle button (hamburger icon) in ChatHeader
- When collapsed: sidebar width → 0 or narrow icon strip, chat area → full width
- Persist preference in `localStorage`
- Smooth CSS transition (width animation)
- Mobile responsive: sidebar as overlay on small screens

```
┌──────┬──────────────────────────┐     ┌──────────────────────────────────┐
│      │                          │     │ ≡                                │
│ Side │    Chat Area             │ →   │         Chat Area (full)         │
│ bar  │                          │     │                                  │
└──────┴──────────────────────────┘     └──────────────────────────────────┘
```

### 5A.2 Voice Communication

**Files:** `frontend/src/components/ChatInput.vue`, `frontend/src/composables/useVoiceInput.js`

**Speech-to-Text (input):**
- New composable `useVoiceInput.js` using Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`)
- Microphone button in ChatInput (icon: `Mic` from lucide-vue-next)
- Visual feedback: pulsing animation when recording, waveform indicator
- Auto-insert transcribed text into input field
- Language auto-detection from browser locale
- Graceful fallback message for unsupported browsers

**Text-to-Speech (output — optional):**
- Speaker button on assistant messages using `SpeechSynthesis` API
- Read aloud the response text (strip markdown formatting first)
- Play/pause/stop controls

```javascript
// useVoiceInput.js — composable
export function useVoiceInput() {
    const isListening = ref(false)
    const transcript = ref("")
    const isSupported = ref('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

    function startListening() { ... }
    function stopListening() { ... }

    return { isListening, transcript, isSupported, startListening, stopListening }
}
```

### 5A.3 User Prompt Help (@mentions & Suggestions)

**Files:** `frontend/src/components/ChatInput.vue`, `frontend/src/components/PromptSuggestions.vue`, `frontend/src/composables/usePromptHelp.js`

**@Mention Autocomplete:**
- When user types `@`, show dropdown with context helpers:
  - `@company` → inserts user's default company name
  - `@period` → shows sub-menu: "This Month", "Last Month", "This Quarter", "This FY", "Last FY"
  - `@cost_center` → lists available cost centers
  - `@department` → lists departments
  - `@warehouse` → lists warehouses
  - `@customer` → searches customers
  - `@item` → searches items
- Dropdown positioned above the input (like Discord/Slack mentions)
- Fetch options via lightweight Frappe API calls (`frappe.call` with `frappe.get_list`)
- Search/filter as user types after `@`
- On selection, replace `@token` with actual value in the input

**Prompt Suggestions:**
- Show suggestion chips above the input for new conversations:
  - "Show me this month's sales summary"
  - "What are the top 10 customers by revenue?"
  - "Show accounts receivable aging"
  - "What is the current cash flow?"
- Configurable suggestions stored in Chatbot Settings (JSON field `prompt_suggestions`)
- Fade out after first message is sent

### 5A.4 Multi Charts & Styled Tables

**Files:** `frontend/src/components/charts/ChartMessage.vue`, `frontend/src/components/charts/DataTable.vue`

**Multiple Charts per Response:**
- Tools can return a `charts` array (list of ECharts option objects) instead of single `echart_option`
- Frontend iterates and renders each chart in sequence
- Backend `build_dashboard_charts()` helper for composite responses (e.g., CFO dashboard returns 4 charts)
- Horizontal layout for 2 small charts side-by-side, vertical stack for more

**Styled Data Tables:**
- New `DataTable.vue` component for structured tabular data
- Tools return `table_data` object: `{"headers": [...], "rows": [...], "footer": [...]}`
- Renders as styled HTML table with:
  - Alternating row colors
  - Right-aligned numbers with currency formatting
  - Sortable columns (click header)
  - Compact vs expanded view toggle
- Falls back to AI-generated markdown tables when `table_data` is not present

### 5A.5 Deliverables

| Item | Files |
|------|-------|
| Sidebar toggle | Updated `ChatView.vue`, `Sidebar.vue`, `ChatHeader.vue` |
| Voice input | `composables/useVoiceInput.js`, updated `ChatInput.vue` |
| Prompt help | `composables/usePromptHelp.js`, `PromptSuggestions.vue`, updated `ChatInput.vue` |
| Multi charts | Updated `ChartMessage.vue`, `charts.py` (`build_dashboard_charts`) |
| Data tables | `components/charts/DataTable.vue`, updated `ChatMessage.vue` |

**New dependencies:** None (Web Speech API is a browser built-in).

---

## Phase 5B: Enterprise Analytics & Configuration

**Goal:** Make the chatbot enterprise-ready with Frappe permissions, accounting dimensions, report integration, CFO-level reporting, parent company consolidation, configurable prompts, configurable constants, and plugin extensibility.

### 5B.1 User Permission Enforcement

**Files:** `ai_chatbot/tools/registry.py`, tool module files

**Architecture:**
- Each `@register_tool` decorator declares which DocTypes the tool accesses:
  ```python
  @register_tool(
      name="get_sales_analytics",
      category="selling",
      description="...",
      parameters={...},
      doctypes=["Sales Invoice"],  # NEW: declares accessed doctypes
  )
  ```
- `registry.py`'s `execute_tool()` checks permission before calling the function:
  ```python
  from frappe.permissions import has_permission

  for dt in tool_info.get("doctypes", []):
      if not has_permission(dt, "read", user=frappe.session.user):
          return {"success": False, "error": f"No permission to read {dt}"}
  ```
- For report-based tools (Phase 5B.3), check `has_permission(report_name, "report")`
- Permission errors return a clear message the AI can relay to the user
- The system prompt dynamically lists only the tools the current user has permission to use

**Reference:** `from frappe.permissions import has_permission` — [Frappe Permission Docs](https://docs.frappe.io/framework/user/en/basics/users-and-permissions)

### 5B.2 Accounting Dimensions

**Files:** `ai_chatbot/core/dimensions.py` (new), updated finance tools, updated `prompts.py`

**Discovery:**
```python
# ai_chatbot/core/dimensions.py
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
    get_dimension_with_children,
)

def get_available_dimensions():
    """Get all active accounting dimensions for the current site."""
    dimensions = get_accounting_dimensions()
    return [{"fieldname": d.fieldname, "label": d.label, "document_type": d.document_type}
            for d in dimensions]

def get_dimension_values(dimension_doctype, company=None):
    """Get all valid values for a dimension (e.g., all Cost Centers)."""
    filters = {"company": company} if company else {}
    return frappe.get_all(dimension_doctype, filters=filters, pluck="name")

def get_dimension_with_children_safe(dimension_doctype, value):
    """Get dimension value including all children (for tree structures like Cost Center)."""
    return get_dimension_with_children(dimension_doctype, value)
```

**Tool Integration:**
- Finance tools (`receivables.py`, `payables.py`, `profitability.py`, `budget.py`, etc.) accept dynamic dimension parameters
- Common pattern:
  ```python
  @register_tool(
      name="get_receivable_aging",
      ...
      parameters={
          ...,
          "cost_center": {"type": "string", "description": "Filter by Cost Center"},
          "department": {"type": "string", "description": "Filter by Department"},
          "project": {"type": "string", "description": "Filter by Project"},
      },
  )
  def get_receivable_aging(..., cost_center=None, department=None, project=None):
      ...
      # Apply dimension filters dynamically
      for dim_field, dim_value in [("cost_center", cost_center), ("department", department), ("project", project)]:
          if dim_value:
              query = query.where(table[dim_field] == dim_value)
  ```
- A shared helper `apply_dimension_filters(query, table, **dimensions)` avoids repetition
- System prompt includes available dimensions so the AI knows to ask or suggest them

**Reference:** `from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions` — [ERPNext Accounting Dimensions](https://docs.frappe.io/erpnext/user/manual/en/accounting-dimensions)

### 5B.3 Report Data for Analysis

**Files:** `ai_chatbot/tools/reports.py` (new), `ai_chatbot/core/constants.py` (updated)

**Architecture:**
- Generic tool that executes any Frappe/ERPNext report and returns the result:
  ```python
  @register_tool(
      name="get_report_data",
      category="reports",
      description="Fetch data from any ERPNext report for analysis",
      parameters={
          "report_name": {"type": "string", "description": "Name of the report (e.g., 'General Ledger', 'Accounts Receivable')"},
          "filters": {"type": "object", "description": "Report filters as key-value pairs"},
      },
      doctypes=[],  # Permission checked per-report
  )
  def get_report_data(report_name, filters=None):
      # Check report permission
      if not frappe.has_permission("Report", report_name, "read"):
          return {"error": "No permission to access this report"}

      result = frappe.get_report_result(report_name, filters=filters or {})
      return {
          "columns": result.get("columns", []),
          "data": result.get("result", [])[:100],  # Limit rows for context window
          "report_name": report_name,
          "filters_used": filters,
      }
  ```
- Pre-configured report shortcuts for common analyses:
  - `get_general_ledger(from_date, to_date, account=None, company=None)`
  - `get_trial_balance(from_date, to_date, company=None)`
  - `get_profit_and_loss(from_date, to_date, company=None)`
  - `get_balance_sheet(date, company=None)`
  - `get_accounts_receivable_report(company=None, ageing_based_on="Due Date")`
- **Data consistency guarantee:** AI analysis is based on the same data the user sees in ERPNext reports
- Add `enable_report_tools` to TOOL_CATEGORIES in constants.py

### 5B.4 CFO Reporting (Composite Analysis)

**Files:** `ai_chatbot/tools/finance/cfo.py` (new)

**Architecture:**
- Composite tools that call multiple existing tools and aggregate results:
  ```python
  @register_tool(
      name="get_cfo_dashboard",
      category="finance",
      description="Comprehensive financial dashboard with P&L, cash flow, ratios, and receivables/payables overview",
      parameters={
          "from_date": {"type": "string", "description": "Start date. Defaults to fiscal year start."},
          "to_date": {"type": "string", "description": "End date. Defaults to fiscal year end."},
          "company": {"type": "string", "description": "Company. Defaults to user's default company."},
      },
  )
  def get_cfo_dashboard(from_date=None, to_date=None, company=None):
      """Aggregates: P&L summary, cash flow, key ratios, AR/AP aging, budget variance."""
      ...
      return {
          "summary": { ... },
          "charts": [pl_chart, cashflow_chart, aging_chart, budget_chart],
          "tables": [ratios_table, top_debtors_table],
          ...
      }
  ```
- Additional CFO-level tools:
  - `get_financial_overview(company, period)` — high-level KPIs: revenue, expenses, net profit, cash position, AR, AP
  - `get_monthly_comparison(company, months=3)` — month-over-month comparison with variance
  - `get_year_over_year(company)` — YoY comparison of key metrics
- All return multiple charts via `charts` array (rendered by Phase 5A.4's multi-chart frontend)

### 5B.5 Parent Company / Multi-Company Consolidation

**Files:** `ai_chatbot/core/config.py` (updated), `ai_chatbot/core/consolidation.py` (new), updated `prompts.py`

**Discovery:**
```python
# ai_chatbot/core/consolidation.py
def is_parent_company(company):
    """Check if a company has child companies."""
    return bool(frappe.db.get_descendants("Company", company))

def get_child_companies(parent_company):
    """Get all descendant companies."""
    return frappe.db.get_descendants("Company", parent_company)

def get_consolidated_data(tool_func, companies, target_currency, **kwargs):
    """Execute a tool across multiple companies and consolidate results.

    Converts all amounts to target_currency using exchange rates.
    """
    from ai_chatbot.data.currency import get_exchange_rate

    consolidated = []
    for company in companies:
        result = tool_func(company=company, **kwargs)
        company_currency = frappe.get_cached_value("Company", company, "default_currency")
        if company_currency != target_currency:
            rate = get_exchange_rate(company_currency, target_currency)
            result = _convert_amounts(result, rate)
        consolidated.append({"company": company, "data": result})

    return consolidated
```

**System Prompt Integration:**
- Detect if user's default company is a parent company
- Include in system prompt:
  ```
  ## Multi-Company Context
  - Your company "{company}" is a parent company with subsidiaries: {child_list}
  - When the user asks for consolidated data, ask them:
    1. Whether to include child companies
    2. Which currency to display (parent company currency or specific currency)
  - Use consolidation tools to aggregate across companies
  ```

**Flow:**
1. User asks "Show total sales" → AI sees parent company context in system prompt
2. AI asks: "Your company has subsidiaries: X, Y, Z. Would you like consolidated data or just {parent_company}?"
3. If consolidated → "In which currency? {parent_currency} or another?"
4. AI calls tool with `consolidated=True, currency=target_currency`
5. Tool iterates child companies, converts, aggregates

### 5B.6 Configurable System & User Prompts

**Files:** `ai_chatbot/chatbot/doctype/chatbot_settings/chatbot_settings.json` (updated), `ai_chatbot/core/prompts.py` (updated)

**Chatbot Settings additions:**
- `custom_system_prompt` (Text Editor) — admin-defined system prompt additions
- `ai_persona` (Small Text) — customizable persona description (default: "intelligent ERPNext business assistant")
- `response_language` (Select) — preferred response language (English, Hindi, etc.)
- `custom_instructions` (Text Editor) — additional behavioral instructions appended to system prompt

**Prompt Builder update:**
```python
def build_system_prompt():
    settings = frappe.get_single("Chatbot Settings")

    # Use custom persona or default
    persona = settings.ai_persona or "an intelligent ERPNext business assistant"
    parts.append(f"You are {persona}. ...")

    # Append custom system prompt if configured
    if settings.custom_system_prompt:
        parts.append(f"\n## Custom Instructions\n{settings.custom_system_prompt}")

    # Response language
    if settings.response_language and settings.response_language != "English":
        parts.append(f"\n## Language\nRespond in {settings.response_language}.")

    ...
```

### 5B.7 Configurable Constants

**Files:** `ai_chatbot/chatbot/doctype/chatbot_settings/chatbot_settings.json` (updated), `ai_chatbot/core/constants.py` (updated), `ai_chatbot/core/config.py` (updated)

**Move user-facing constants to Chatbot Settings:**

| Constant | Current Location | Move To |
|---|---|---|
| `DEFAULT_QUERY_LIMIT` (20) | `constants.py` | Settings: `default_query_limit` (Int) |
| `DEFAULT_TOP_N_LIMIT` (10) | `constants.py` | Settings: `default_top_n_limit` (Int) |
| `MAX_QUERY_LIMIT` (100) | `constants.py` | Settings: `max_query_limit` (Int) |
| Aging buckets | `constants.py` | Settings: `aging_buckets` (JSON) |
| Prompt suggestions | — | Settings: `prompt_suggestions` (JSON) |

**Keep in code (not user-configurable):**
- `BASE_AMOUNT_FIELDS` — technical field mapping
- `TRANSACTION_AMOUNT_FIELDS` — technical field mapping
- `TOOL_CATEGORIES` — tied to settings flags
- `LOG_TITLE` — internal logging
- `DATE_FORMAT` — standardized format

**Config helpers:**
```python
# ai_chatbot/core/config.py
def get_query_limit(requested=None):
    """Get query limit, capped at max."""
    settings = get_chatbot_settings()
    max_limit = settings.max_query_limit or 100
    default = settings.default_query_limit or 20
    return min(requested or default, max_limit)
```

### 5B.8 Tools as Plugins (External App Registration)

**Files:** `ai_chatbot/hooks.py` (updated), `ai_chatbot/tools/registry.py` (updated)

**Hook-based tool registration:**
```python
# In hooks.py — define the hook
ai_chatbot_tool_modules = []  # Default empty, other apps extend this

# In registry.py — load external tools
def _ensure_tools_loaded():
    if _TOOL_REGISTRY:
        return

    # Load built-in tools
    import ai_chatbot.tools.crm
    import ai_chatbot.tools.selling
    ...

    # Load external plugin tools via Frappe hooks
    for module_path in frappe.get_hooks("ai_chatbot_tool_modules"):
        try:
            frappe.get_module(module_path)
        except Exception as e:
            frappe.log_error(f"Failed to load tool plugin: {module_path}: {e}", "AI Chatbot")
```

**How external apps register tools:**
```python
# In another_app/hooks.py
ai_chatbot_tool_modules = [
    "another_app.chatbot_tools.manufacturing",
    "another_app.chatbot_tools.quality",
]

# In another_app/chatbot_tools/manufacturing.py
from ai_chatbot.tools.registry import register_tool

@register_tool(
    name="get_production_summary",
    category="manufacturing",
    description="Get production order summary",
    parameters={...},
    doctypes=["Work Order"],
)
def get_production_summary(company=None):
    ...
```

**TOOL_CATEGORIES update:**
- Dynamic category registration: external apps can declare new categories
- `TOOL_CATEGORIES` becomes a function that merges built-in + hook-defined categories

### 5B.9 Deliverables

| Item | Files |
|------|-------|
| Permissions | Updated `tools/registry.py`, all tool decorators |
| Dimensions | `core/dimensions.py`, updated finance tools, updated `prompts.py` |
| Reports | `tools/reports.py` (new) |
| CFO reporting | `tools/finance/cfo.py` (new) |
| Consolidation | `core/consolidation.py` (new), updated `config.py`, `prompts.py` |
| Configurable prompts | Updated Chatbot Settings DocType, updated `prompts.py` |
| Configurable constants | Updated Chatbot Settings DocType, updated `config.py`, `constants.py` |
| Plugin system | Updated `hooks.py`, updated `registry.py` |

**New dependencies:** None (uses Frappe built-ins and ERPNext APIs).

---

## Phase 6: Agentic RAG — Vector Search + Multi-Agent Orchestration

**Goal:** Implement a full Agentic RAG system — combining vector-based document retrieval with multi-agent orchestration, planning, and iterative refinement.

### 6.1 RAG Foundation (`ai_chatbot/ai/rag/`)

```
ai_chatbot/ai/rag/
├── __init__.py
├── embeddings.py      # Embedding generation (OpenAI/local)
├── vector_store.py    # ChromaDB interface
├── chunker.py         # Document chunking strategies
└── retriever.py       # Query → retrieve → rank → return
```

**embeddings.py:**
- `generate_embedding(text)` — uses OpenAI `text-embedding-3-small` or local model
- Batch embedding support for document indexing

**vector_store.py:**
- ChromaDB as the default vector store (runs locally, no external service needed)
- `add_documents(chunks, embeddings, metadata)` — index documents
- `search(query_embedding, n_results=5, filters=None)` — similarity search
- `delete_documents(source_id)` — remove indexed documents
- Collection per company (multi-company isolation): `knowledge_{company_slug}`

**chunker.py:**
- `chunk_text(text, chunk_size=500, overlap=50)` — simple text chunking
- `chunk_document(file_path)` — PDF, DOCX, TXT extraction + chunking
- Metadata preservation (source document, page number, section)

**retriever.py:**
- `retrieve_context(query, company=None, n_results=5)` — embed query → search → return ranked chunks
- `evaluate_relevance(query, chunks)` — scores retrieved chunks for relevance (used by agents)
- `requery(original_query, feedback)` — refine search terms based on agent feedback

### 6.2 Agent Framework (`ai_chatbot/ai/agents/`)

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
- Combines tool results with RAG context when both are needed

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
- Retrieves from vector store via `retriever.py`
- Evaluates relevance of retrieved chunks
- Can re-query with refined search terms if initial results are poor
- Synthesizes answers from multiple document sources

### 6.3 Memory System (`ai_chatbot/ai/memory/`)

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

### 6.4 Knowledge Base DocType & Indexing

**Chatbot Knowledge Base** (new DocType):
- Fields: `title`, `source_type` (File/ERPNext Record/URL), `source_reference`, `company`, `status` (Indexed/Pending/Failed), `chunk_count`, `last_indexed`
- Tracks what has been indexed into the vector store

**Indexing pipeline:**
- **Manual:** Upload PDF/DOCX via a "Knowledge Base" page in the frontend
- **Automatic:** Index key ERPNext records (Items, Customers, Suppliers, policies) via scheduled task
- **Incremental:** Only re-index documents that have changed since last indexing

### 6.5 Frontend

```
frontend/src/
├── pages/
│   └── KnowledgeBaseView.vue   # Document upload and management
├── components/
│   ├── chat/
│   │   └── AgentThinking.vue   # Shows agent reasoning steps
│   └── documents/
│       ├── DocumentUploader.vue # File upload with drag-and-drop
│       └── DocumentList.vue     # List of indexed documents
```

### 6.6 Deliverables

| Item | Files |
|------|-------|
| RAG engine | `ai/rag/embeddings.py`, `vector_store.py`, `chunker.py`, `retriever.py` |
| Agent framework | `ai/agents/base_agent.py`, `orchestrator.py`, `planner_agent.py`, `analyst_agent.py`, `document_agent.py` |
| Memory system | `ai/memory/conversation_memory.py`, `knowledge_memory.py`, `memory_manager.py` |
| Knowledge Base DocType | `chatbot/doctype/chatbot_knowledge_base/` |
| Indexing pipeline | Scheduled task in `hooks.py` |
| Frontend | `KnowledgeBaseView.vue`, `DocumentUploader.vue`, `DocumentList.vue`, `AgentThinking.vue` |
| Chat integration | Updated `api/chat.py` to use orchestrator |

**New dependencies:**
- **Backend:** `chromadb`, `openai` (for embeddings), `pypdf` (PDF extraction), `python-docx` (DOCX extraction)
- **Frontend:** None

---

## Phase 7: Intelligent Document Processing (IDP)

**Goal:** Extract data from uploaded documents (invoices, receipts, POs) and create ERPNext records. Includes file upload capability, data comparison, and reconciliation.

### 7.1 File Upload Infrastructure

**Files:** `ai_chatbot/api/files.py` (new), updated `ChatInput.vue`, updated `chatbot_message.json`

- Frontend: file picker + drag-and-drop in ChatInput (accept PDF, images, Excel, CSV)
- Upload via `frappe.handler.upload_file` API
- Store file reference on Chatbot Message (`attachments` JSON field — already exists)
- Pass file context to the AI: file name, type, size, and extracted text preview
- For images: pass to LLM Vision API for analysis
- For PDFs/Excel: extract text/tables and include in the prompt context

### 7.2 Document Extraction (`ai_chatbot/idp/`)

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
1. User uploads document (PDF/image) in chat
2. LLM Vision extracts structured data (supplier, items, amounts, dates)
3. Validator checks against ERPNext schema and business rules
4. Mapper creates draft ERPNext document
5. User reviews and confirms (reuses Phase 3 confirmation pattern)
6. Document is submitted

### 7.3 Data Comparison & Reconciliation

**Files:** `ai_chatbot/idp/comparison.py` (new), `ai_chatbot/tools/operations/reconcile.py` (new)

**Use case:** User attaches a client's Purchase Order PDF to a Sales Order → system compares and highlights discrepancies.

**Architecture:**
- `extract_document_data(file_url)` — extract structured data from attached file (PDF/Excel)
- `compare_documents(extracted_data, erpnext_doc)` — field-by-field comparison
- `generate_reconciliation_report(comparison_result)` — formatted diff report

**Reconciliation tool:**
```python
@register_tool(
    name="compare_document_with_record",
    category="operations",
    description="Compare an uploaded document with an ERPNext record and highlight differences",
    parameters={
        "file_url": {"type": "string", "description": "URL of the uploaded file to compare"},
        "doctype": {"type": "string", "description": "ERPNext DocType to compare against"},
        "docname": {"type": "string", "description": "Document name to compare against"},
    },
)
def compare_document_with_record(file_url, doctype, docname):
    ...
```

**Output format:**
```
| Field           | Uploaded Document | ERPNext Record | Match |
|-----------------|-------------------|----------------|-------|
| Supplier        | Acme Corp         | Acme Corp      | ✓     |
| PO Number       | PO-2026-001       | PO-2026-001    | ✓     |
| Item: Widget A  | Qty: 100          | Qty: 90        | ✗     |
| Total Amount    | $15,000           | $13,500        | ✗     |
```

### 7.4 Frontend

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

### 7.5 Deliverables

| Item | Files |
|------|-------|
| File upload | `api/files.py`, updated `ChatInput.vue`, updated `chatbot_message.json` |
| Extractors | `idp/extractors/invoice_extractor.py`, `receipt_extractor.py`, `generic_extractor.py` |
| Validators | `idp/validators/schema_validator.py`, `business_rules.py` |
| Mappers | `idp/mappers/invoice_mapper.py`, `supplier_mapper.py`, `item_mapper.py` |
| Comparison | `idp/comparison.py`, `tools/operations/reconcile.py` |
| Frontend | `DocumentProcessingView.vue`, extraction/mapping components |
| DocType | `chatbot_document_queue` — tracks processing status |

**New dependencies:**
- **Backend:** `pypdf` (if not added in Phase 6), `Pillow`, optionally `pytesseract` + `pdf2image`, `openpyxl` (Excel parsing)
- **Frontend:** None

---

## Phase 8: Predictive Analytics & ML

**Goal:** Add forecasting and prediction capabilities using statistical and ML models.

### 8.1 Predictive Tools (`ai_chatbot/tools/predictive/`)

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

### 8.2 Deliverables

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

## Phase 9: Automation & Notifications

**Goal:** Scheduled reports, alerts, automated workflows, and auto-email triggered by chat or conditions.

### 9.1 Auto Email & Scheduled Reports

**Files:** `ai_chatbot/automation/scheduled_reports.py`, new DocType: `Chatbot Scheduled Report`

**Chatbot Scheduled Report** DocType:
- `report_name` (Data) — user-defined name
- `prompt` (Text) — the prompt to execute (e.g., "Generate a weekly sales summary with top customers and revenue trend")
- `recipients` (Table — child: email, user) — who receives the report
- `schedule` (Select) — Daily / Weekly / Monthly / Custom Cron
- `day_of_week` (Select) — for weekly (Monday–Sunday)
- `day_of_month` (Int) — for monthly
- `cron_expression` (Data) — for custom cron
- `company` (Link: Company) — company context for the report
- `ai_provider` (Select) — which AI to use
- `format` (Select) — Email HTML / PDF attachment / Both
- `enabled` (Check) — active/inactive toggle
- `last_run` (Datetime) — last execution timestamp

**Execution flow:**
1. Scheduler triggers based on schedule
2. System builds conversation context (system prompt + company + user)
3. Sends prompt to AI with tools enabled
4. Captures response (text + charts + tool results)
5. Formats as HTML email (renders markdown, embeds chart images)
6. Sends via `frappe.sendmail()`

**Chart embedding in email:**
- ECharts renders to PNG on the server side (use `echarts` npm with `node-canvas` or save chart snapshots)
- Alternative: include chart data as inline HTML tables for email clients that don't render images

### 9.2 Alert System

**Files:** `ai_chatbot/automation/alerts.py`, new DocType: `Chatbot Alert`

**Chatbot Alert** DocType:
- `alert_name` (Data)
- `condition_type` (Select) — Threshold / Schedule / Event
- `condition_prompt` (Text) — natural language condition (e.g., "When accounts receivable exceeds 500,000")
- `threshold_tool` (Data) — tool to call for threshold checks
- `threshold_field` (Data) — field to check in tool result
- `threshold_operator` (Select) — `>`, `<`, `>=`, `<=`, `=`
- `threshold_value` (Float)
- `notification_channels` (Table) — Email / WhatsApp / Slack / In-App
- `recipients` (Table) — users/emails
- `company` (Link: Company)
- `enabled` (Check)

**Example alerts:**
- "Notify me when receivables exceed 500,000" → calls `get_receivable_aging`, checks `total_outstanding > 500000`
- "Alert when stock of Camera falls below 10" → calls `get_inventory_summary` with item filter
- "Send weekly sales summary every Monday" → scheduled report (see 9.1)

### 9.3 Notification Channels

```
ai_chatbot/automation/notifications/
├── __init__.py
├── channels/
│   ├── email.py               # Email via frappe.sendmail
│   ├── whatsapp.py            # WhatsApp via Twilio (already a dependency)
│   └── slack.py               # Slack webhook integration
└── dispatcher.py              # Routes alerts to appropriate channels
```

### 9.4 Deliverables

| Item | Files |
|------|-------|
| Scheduled reports | `automation/scheduled_reports.py`, `Chatbot Scheduled Report` DocType |
| Alert engine | `automation/alerts.py`, `Chatbot Alert` DocType |
| Notifications | `automation/notifications/channels/email.py`, `whatsapp.py`, `slack.py` |
| Dispatcher | `automation/notifications/dispatcher.py` |
| Hooks | Updated `hooks.py` with scheduler_events |
| Settings | Alert/report configuration in Chatbot Settings |

**New dependencies:** `slack_sdk` (optional, for Slack integration). Twilio already present.

---

## Phase Summary

| Phase | Focus | Status | Key Deliverable | Dependencies Added |
|-------|-------|--------|------------------|--------------------|
| **1** | Foundation | ✅ Done | Data layer, multi-company/currency, security fixes | None |
| **2** | Streaming | ✅ Done | Frappe Realtime token streaming, enhanced chat UX | None |
| **3** | CRUD | ✅ Done | Create/update/delete ERPNext records via chat | None |
| **4** | Finance | ✅ Done | 17 finance tools, ECharts integration, multi-color charts | echarts (npm) |
| **5** | HRMS & CRM | Planned | HRMS tools, expanded CRM with charts | None |
| **5A** | UX & Accessibility | Planned | Sidebar toggle, voice input, prompt help, multi-charts, data tables | None |
| **5B** | Enterprise Analytics | Planned | Permissions, dimensions, reports, CFO dashboard, consolidation, config, plugins | None |
| **6** | Agentic RAG | Planned | Vector search + multi-agent orchestration + memory | chromadb, pypdf, python-docx |
| **7** | IDP | Planned | File upload, document extraction, data comparison/reconciliation | Pillow, pytesseract (opt), openpyxl |
| **8** | Predictive | Planned | Forecasting, anomaly detection | pandas, numpy, prophet (opt) |
| **9** | Automation | Planned | Auto-email, scheduled reports, alerts, notifications | slack_sdk (opt) |

---

## Multi-Company & Multi-Currency Reference

### Multi-Company Pattern

Every tool that queries transactional data follows this pattern:

```python
def get_sales_analytics(from_date=None, to_date=None, company=None):
    """Get sales analytics for a specific company."""
    company = get_default_company(company)  # Resolves: passed → user default → global default

    filters = {"docstatus": 1, "company": company}
    ...

    return build_currency_response(result, company)
    # Adds: {"company": company, "currency": "USD"}
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

### Parent Company Consolidation (Phase 5B)

When a company is a parent company:
1. Detect child companies via `frappe.db.get_descendants("Company", parent_company)`
2. Ask user: include subsidiaries? In which currency?
3. Execute tool across all companies
4. Convert to target currency using `get_exchange_rate()`
5. Aggregate and present consolidated view

### Company Isolation for RAG (Phase 6)

Vector store collections are namespaced by company:
- Collection name: `knowledge_{company_name_slug}`
- Queries only search the current user's company collection
- Cross-company search requires explicit permission

---

## File Structure After All Phases

```
ai_chatbot/
├── core/                          # Phase 1
│   ├── config.py                  # Updated: Phase 5B (configurable constants)
│   ├── constants.py               # Updated: Phase 5B (dynamic categories)
│   ├── exceptions.py
│   ├── logger.py
│   ├── prompts.py                 # Updated: Phase 5B (configurable prompts, dimensions, consolidation)
│   ├── dimensions.py              # Phase 5B (accounting dimension helpers)
│   └── consolidation.py           # Phase 5B (parent company consolidation)
│
├── data/                          # Phase 1, 3, 4
│   ├── queries.py
│   ├── analytics.py
│   ├── currency.py
│   ├── charts.py                  # Phase 4 (ECharts builders)
│   ├── operations.py              # Phase 3
│   └── validators.py              # Phase 3
│
├── api/                           # Phase 1, 2, 3, 7
│   ├── chat.py
│   ├── streaming.py               # Phase 2
│   ├── files.py                   # Phase 7 (file upload)
│   └── documents.py               # Phase 7 (IDP)
│
├── utils/
│   └── ai_providers.py
│
├── tools/                         # Phase 1, 3, 4, 5, 5B, 8
│   ├── registry.py                # Phase 1, updated: 5B (permissions, plugins)
│   ├── base.py
│   ├── crm.py                     # Phase 1, updated: 5
│   ├── selling.py                 # Phase 1, updated: 4
│   ├── buying.py                  # Phase 1, updated: 4
│   ├── stock.py                   # Phase 1, updated: 4
│   ├── account.py                 # Phase 1
│   ├── hrms.py                    # Phase 5
│   ├── reports.py                 # Phase 5B (report data tools)
│   ├── operations/                # Phase 3
│   │   ├── create.py
│   │   ├── update.py
│   │   ├── search.py
│   │   └── reconcile.py           # Phase 7
│   ├── finance/                   # Phase 4, 5B
│   │   ├── budget.py
│   │   ├── ratios.py
│   │   ├── profitability.py
│   │   ├── working_capital.py
│   │   ├── receivables.py
│   │   ├── payables.py
│   │   ├── cash_flow.py
│   │   └── cfo.py                 # Phase 5B (CFO composite reports)
│   └── predictive/                # Phase 8
│       ├── demand_forecast.py
│       ├── sales_forecast.py
│       ├── cash_flow_forecast.py
│       └── anomaly_detection.py
│
├── ai/                            # Phase 6 (Agentic RAG)
│   ├── rag/
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   ├── chunker.py
│   │   └── retriever.py
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── orchestrator.py
│   │   ├── planner_agent.py
│   │   ├── analyst_agent.py
│   │   └── document_agent.py
│   └── memory/
│       ├── conversation_memory.py
│       ├── knowledge_memory.py
│       └── memory_manager.py
│
├── idp/                           # Phase 7
│   ├── extractors/
│   │   ├── base_extractor.py
│   │   ├── invoice_extractor.py
│   │   ├── receipt_extractor.py
│   │   └── generic_extractor.py
│   ├── validators/
│   │   ├── schema_validator.py
│   │   └── business_rules.py
│   ├── mappers/
│   │   ├── base_mapper.py
│   │   ├── invoice_mapper.py
│   │   ├── supplier_mapper.py
│   │   └── item_mapper.py
│   └── comparison.py              # Phase 7 (data comparison/reconciliation)
│
├── automation/                    # Phase 9
│   ├── scheduled_reports.py
│   ├── alerts.py
│   └── notifications/
│       ├── channels/
│       │   ├── email.py
│       │   ├── whatsapp.py
│       │   └── slack.py
│       └── dispatcher.py
│
├── chatbot/                       # Frappe DocTypes (expanded across phases)
│   └── doctype/
│       ├── chatbot_settings/      # Updated: 5A, 5B (prompts, constants, suggestions)
│       ├── chatbot_conversation/
│       ├── chatbot_message/       # Updated: 4 (tool_results), 7 (attachments)
│       ├── chatbot_knowledge_base/    # Phase 6
│       ├── chatbot_document_queue/    # Phase 7
│       ├── chatbot_scheduled_report/  # Phase 9
│       └── chatbot_alert/             # Phase 9
│
└── tests/                         # All phases
    ├── unit/
    ├── integration/
    └── fixtures/

frontend/src/
├── components/
│   ├── Sidebar.vue                # Updated: 5A (collapsible)
│   ├── ChatHeader.vue             # Updated: 5A (sidebar toggle button)
│   ├── ChatMessage.vue            # Updated: 4 (charts), 5A (data tables)
│   ├── ChatInput.vue              # Updated: 5A (voice, @mentions), 7 (file upload)
│   ├── TypingIndicator.vue
│   ├── PromptSuggestions.vue      # Phase 5A (prompt chips)
│   ├── charts/                    # Phase 4, 5A
│   │   ├── EChartRenderer.vue
│   │   ├── ChartMessage.vue       # Updated: 5A (multi-chart)
│   │   └── DataTable.vue          # Phase 5A (styled tables)
│   ├── documents/                 # Phase 6
│   │   ├── DocumentUploader.vue
│   │   └── DocumentList.vue
│   ├── idp/                       # Phase 7
│   │   ├── ExtractionResult.vue
│   │   └── MappingPreview.vue
│   └── chat/
│       └── AgentThinking.vue      # Phase 6
├── pages/
│   ├── ChatView.vue               # Updated: 5A (sidebar toggle, scroll fix)
│   ├── KnowledgeBaseView.vue      # Phase 6
│   └── DocumentProcessingView.vue # Phase 7
├── composables/
│   ├── useStreaming.js             # Phase 2
│   ├── useVoiceInput.js           # Phase 5A
│   └── usePromptHelp.js           # Phase 5A
└── utils/
    └── api.js
```
