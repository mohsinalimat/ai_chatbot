# AI Chatbot — Phase-wise Enhancement Roadmap

## Current State Summary (Post Phase 6A)

The AI Chatbot is a functional Frappe app with:

- **4 DocTypes:** Chatbot Settings (Single), Chatbot Conversation, Chatbot Message, Chatbot Token Usage
- **47+ tools** across 10 categories: CRM (5), Selling (8), Buying (6), Stock (6), Account (2), Finance (20 incl. CFO), HRMS (6), Operations (3), Consolidation (1)
- **3 AI providers:** OpenAI (GPT-4o), Claude (Sonnet 4.5), and Gemini (2.5 Flash) — unified single-provider configuration
- **Streaming:** Real-time token streaming via Frappe Realtime (Socket.IO/WebSocket) with process step indicators
- **CRUD:** Create, update, search ERPNext records via chat with confirmation pattern
- **ECharts:** Inline chart rendering (bar, line, pie, horizontal bar, multi-series) with multi-color palette
- **Multi-company & multi-currency:** All tools use `company` parameter and `base_*` fields
- **Consolidation:** Parent company detection, cross-subsidiary aggregation with currency conversion
- **Permissions:** DocType-based tool filtering — users only see tools they have access to
- **Accounting Dimensions:** Finance tools support cost_center, department, project filtering
- **Configurable prompts:** Custom persona, response language, custom instructions via settings
- **Financial analyst behaviour:** CFO-grade analysis behaviour when finance tools are enabled
- **Plugin system:** External apps register tools via `ai_chatbot_tool_modules` Frappe hook
- **Data layer:** `frappe.qb` Query Builder throughout — no raw SQL
- **Token optimization:** Conversation history trimming (configurable `max_context_messages`), tool result compression (strip echart_option, truncate large datasets)
- **Cost monitoring:** Per-request token usage tracking with estimated cost (Chatbot Token Usage DocType)
- **Vue 3 frontend:** Claude.AI-inspired sidebar (collapsible, date-grouped, search), wider AI messages, icon-only buttons
- **Dark mode:** OS-level `prefers-color-scheme` detection, Tailwind `dark:` classes across all components
- **Chat search:** Backend `search_conversations` endpoint + sidebar search UI with debounced input
- **Process indicators:** Real-time pipeline steps ("Preparing context...", "Executing Tool...", "Saving response...")
- **Personalized greeting:** Centered logo + "Hello, {name}!" on new conversations; input moves to bottom after first message
- **File upload:** Image/PDF/document upload with Vision API support (OpenAI, Claude & Gemini)
- **Voice I/O:** Speech-to-text input (Web Speech API) and text-to-speech output (SpeechSynthesis)
- **@Mention autocomplete:** `@company`, `@period`, `@cost_center`, `@department`, `@warehouse`, `@customer`, `@item`, `@accounting_dimension`
- **Favicon & Logo:** Custom orbital SVG (violet gradient, RGB dots) as favicon and AI assistant avatar
- **User Avatar:** User's profile image on right side of message bubbles; initials fallback
- **Settings tabs:** Chatbot Settings organized into tabs (API Configuration, Tools, Query Configuration, Prompts, Streaming)

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

## Phase 5: HRMS Tools & Enhanced CRM ✅

**Goal:** Complete the HRMS placeholder and expand CRM capabilities.

### 5.1 HRMS Tools (`ai_chatbot/tools/hrms.py`) ✅

6 HRMS tools implemented, all with HRMS module detection and ECharts:

- `get_employee_count(company, department=None, status="Active")` — headcount with department breakdown
- `get_attendance_summary(company, from_date, to_date, department=None)` — attendance stats (present, absent, leave, half-day)
- `get_leave_balance(employee=None, leave_type=None, company=None)` — leave balances by type
- `get_payroll_summary(company, from_date, to_date)` — total salary, deductions, net pay with chart
- `get_department_wise_salary(company, month=None)` — salary by department with pie chart
- `get_employee_turnover(company, from_date, to_date)` — joining vs leaving rate with trend chart

### 5.2 Enhanced CRM Tools (`ai_chatbot/tools/crm.py`) ✅

5 CRM tools (3 new + 2 updated with ECharts):

- `get_lead_conversion_rate(company, from_date, to_date)` — lead-to-opportunity conversion rate with funnel chart
- `get_lead_source_analysis(company, from_date, to_date)` — leads by source with pie chart
- `get_sales_funnel(company, from_date, to_date)` — lead → opportunity → quotation → order pipeline
- Existing tools (`get_lead_statistics`, `get_opportunity_pipeline`) updated with ECharts

### 5.3 Settings ✅

- `enable_hrms_tools` flag in Chatbot Settings, conditional on HRMS module installation

---

## Phase 5A: UX & Accessibility ✅

**Goal:** Enhance the chat interface with file upload, voice communication, @mention autocomplete, prompt suggestions, and collapsible sidebar. Mix of backend and frontend changes.

### 5A.1 File Upload & Vision API ✅

**New file:** `ai_chatbot/api/files.py`
**Modified:** `api/chat.py`, `api/streaming.py`, `utils/ai_providers.py`, `frontend/src/utils/api.js`

- **Upload endpoint:** `upload_chat_file()` — validates ownership, MIME type (images, PDF, DOCX, CSV, XLSX, TXT), 10MB limit, saves to Frappe File DocType
- **Vision API support:** Image attachments sent to OpenAI/Claude Vision for analysis
  - OpenAI format as canonical internal representation (`image_url` content parts)
  - Claude provider converts to Claude's `image` + `base64` source format in `_convert_messages_to_claude()`
- **Upload-then-send (two-phase):** Files uploaded first to Frappe, metadata (not binary) passed with message — works with streaming's `frappe.enqueue`
- **Frontend composable:** `useFileUpload.js` — file selection, validation, preview URLs, pending file management
- **ChatInput UI:** Paperclip button, file chips with preview thumbnails, drag-and-drop overlay, max 5 files

### 5A.2 Voice Communication ✅

**New files:** `frontend/src/composables/useVoiceInput.js`, `frontend/src/composables/useVoiceOutput.js`
**Modified:** `frontend/src/components/ChatInput.vue`, `frontend/src/pages/ChatView.vue`, `frontend/src/components/ChatMessage.vue`

**Speech-to-Text (input):**
- `useVoiceInput.js` composable using Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`)
- `continuous=true`, `interimResults=true`, `lang=navigator.language`
- Microphone button with pulsing red animation when recording (`animate-recording`)
- Interim transcript displayed in real-time below input text
- Graceful degradation: mic button hidden in unsupported browsers (Firefox)

**Text-to-Speech (output):**
- `useVoiceOutput.js` composable using `SpeechSynthesis` API
- Markdown stripped before speaking (headers, bold, code, images, links, tables)
- **Auto-speak:** When user submits via voice, AI response auto-speaks after streaming completes
- **Manual "Listen" button** on all assistant messages (Volume2/VolumeX icons)

### 5A.3 @Mention Autocomplete & Prompt Suggestions ✅

**Backend:** `get_mention_values()` endpoint in `api/chat.py`
**Frontend:** Built into `ChatInput.vue` (no separate component needed)

**@Mention Autocomplete (8 categories):**
- `@company` → inserts user's default company name
- `@period` → sub-menu: "This Week", "This Month", "Last Month", "This Quarter", "This FY", "Last FY"
- `@cost_center` → searches cost centers (company-scoped)
- `@department` → searches departments (company-scoped)
- `@warehouse` → searches warehouses (company-scoped)
- `@customer` → searches customers
- `@item` → searches items
- `@accounting_dimension` → dynamically discovers active accounting dimensions via ERPNext's `get_accounting_dimensions()` API

**Implementation details:**
- Two-level drill-down: categories → values (fetched from backend)
- Keyboard navigation (arrow keys, Enter to select, Escape to close)
- Dropdown positioned above textarea
- Triggered on `@` at start of input or after whitespace

**Prompt Suggestions:**
- 4 default suggestion chips shown for new conversations (no messages)
- Click auto-inserts and sends
- Hidden after first message

### 5A.4 Collapsible Sidebar ✅

**Modified:** `ChatView.vue`, `ChatHeader.vue`

- `PanelLeftClose`/`PanelLeftOpen` toggle button in ChatHeader
- `sidebarCollapsed` state persisted in `localStorage` (`ai_chatbot_sidebar`)
- Vue `<transition>` with width + opacity animation
- Chat area expands to full width when sidebar collapsed

### 5A.5 Deliverables

| Item | Files | Status |
|------|-------|--------|
| File upload API | `api/files.py` (new) | ✅ |
| Attachments in chat/streaming | Updated `api/chat.py`, `api/streaming.py` | ✅ |
| Multimodal AI providers | Updated `utils/ai_providers.py` | ✅ |
| File upload composable | `composables/useFileUpload.js` (new) | ✅ |
| Voice input composable | `composables/useVoiceInput.js` (new) | ✅ |
| Voice output composable | `composables/useVoiceOutput.js` (new) | ✅ |
| API client updates | Updated `utils/api.js` (uploadFile, getMentionValues) | ✅ |
| ChatInput rewrite | Updated `components/ChatInput.vue` (file, voice, @mentions, suggestions) | ✅ |
| @Mention backend | `get_mention_values()` in `api/chat.py` | ✅ |
| ChatView orchestrator | Updated `pages/ChatView.vue` (payload, upload, voice, sidebar) | ✅ |
| ChatMessage updates | Updated `components/ChatMessage.vue` (attachments, speaker) | ✅ |
| Sidebar toggle | Updated `components/ChatHeader.vue` | ✅ |
| Tailwind animations | Updated `tailwind.config.js` (recording pulse) | ✅ |

**New dependencies:** None (Web Speech API, File API, SpeechSynthesis are browser-native).

---

## Phase 5B: Enterprise Analytics & Configuration ✅

**Goal:** Make the chatbot enterprise-ready with Frappe permissions, accounting dimensions, report integration, CFO-level reporting, parent company consolidation, configurable prompts, configurable constants, and plugin extensibility.

### 5B.1 User Permission Enforcement ✅

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

### 5B.2 Accounting Dimensions ✅

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

### 5B.4 CFO Reporting (Composite Analysis) ✅

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

### 5B.5 Parent Company / Multi-Company Consolidation ✅

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

### 5B.6 Configurable System & User Prompts ✅

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

### 5B.7 Configurable Constants ✅

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

### 5B.8 Tools as Plugins (External App Registration) ✅

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

## Phase 6: Settings Overhaul, Gemini Provider & Token Optimization ✅

**Goal:** Simplify AI provider configuration with a single-provider dropdown (OpenAI/Claude/Gemini), add Gemini as a third provider, implement token/cost tracking, optimize token usage, tailor financial analysis behaviour, add source file headers, and reorganize Chatbot Settings into tabs.

### 6.1 Chatbot Settings Overhaul ✅

**Files:** `chatbot_settings.json`, `ai_providers.py`, `api/chat.py`, `api/streaming.py`

**Current state:** Separate "OpenAI Configuration" and "Claude Configuration" sections with independent enabled flags, API keys, models, temperature, and max tokens.

**Target state:** Single provider selection with dynamic fields:

```
┌─────────────────────────────────────────────────────┐
│ Tab: API Configuration                              │
├─────────────────────────────────────────────────────┤
│ AI Provider: [OpenAI ▼]  [Claude]  [Gemini]         │
│                                                     │
│ API Key:       [••••••••••••••••••]                  │
│ Model:         [claude-opus-4-5-20251101 ▼]         │
│ Temperature:   [0.7]                                │
│ Max Tokens:    [4000]                               │
├─────────────────────────────────────────────────────┤
│ Tab: Tools                                          │
├─────────────────────────────────────────────────────┤
│ ☑ CRM Tools  ☑ Sales Tools  ☑ Purchase Tools       │
│ ☑ Finance Tools  ☑ Inventory Tools  ☑ HRMS Tools   │
│ ☑ Write Operations                                  │
├─────────────────────────────────────────────────────┤
│ Tab: Query Configuration                            │
├─────────────────────────────────────────────────────┤
│ Default Query Limit: [20]  Max Query Limit: [100]   │
│ Default Top-N Limit: [10]                           │
├─────────────────────────────────────────────────────┤
│ Tab: Prompts                                        │
├─────────────────────────────────────────────────────┤
│ AI Persona:        [...]                            │
│ Response Language:  [English ▼]                     │
│ Custom System Prompt: [...]                         │
│ Custom Instructions:  [...]                         │
├─────────────────────────────────────────────────────┤
│ Tab: Streaming                                      │
├─────────────────────────────────────────────────────┤
│ ☑ Enable Streaming                                  │
└─────────────────────────────────────────────────────┘
```

**Fields to add/change:**
- Replace `openai_enabled`, `claude_enabled` with single `ai_provider` (Select: OpenAI/Claude/Gemini)
- Replace provider-specific API key, model, temperature, max_tokens with unified fields: `api_key` (Password), `model` (Data), `temperature` (Float, default 0.7), `max_tokens` (Int, default 4000)
- Add `max_chat_history` (Int, default 10) — limits sidebar conversation list
- Add Tab Breaks: "API Configuration", "Tools", "Query Configuration", "Prompts", "Streaming"
- Model defaults per provider: OpenAI → `gpt-4o`, Claude → `claude-opus-4-5-20251101`, Gemini → `gemini-2.5-flash`

**Migration:** Data migration script to move existing OpenAI/Claude settings to the unified fields.

### 6.2 Gemini Provider ✅

**Files:** `utils/ai_providers.py`

**Approach:** Use Google's OpenAI-compatible endpoint — the existing `OpenAIProvider` class can be extended with minimal changes since Gemini's OpenAI-compat endpoint uses the same request/response format for chat completions, tool calling, and streaming.

```python
class GeminiProvider(OpenAIProvider):
    """Google Gemini provider via OpenAI-compatible endpoint."""

    def __init__(self, settings):
        self.api_key = settings.api_key
        self.model = settings.model or "gemini-2.5-flash"
        self.temperature = settings.temperature or 1.0
        self.max_tokens = settings.max_tokens or 8192
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
```

**Available models:**
- `gemini-2.5-flash` (default — fast, cost-effective)
- `gemini-2.5-pro` (premium reasoning)
- `gemini-2.5-flash-lite` (budget)

**Multimodal:** Gemini supports vision natively via the OpenAI-compat endpoint — image_url format works as-is.

**No new Python dependency required** — uses existing `requests` library via the OpenAI-compatible REST API.

### 6.3 AI Behaviour for Finance Prompts ✅

**Files:** `core/prompts.py`

Add a dedicated "Financial Analyst / CFO" behaviour section to the system prompt when finance tools are enabled:

```python
if is_tool_category_enabled("enable_finance_tools"):
    parts.append(
        "\n## Financial Analysis Behaviour\n"
        "When answering financial questions, act as a seasoned Financial Analyst / CFO:\n"
        "- Provide context for numbers (YoY change, % of revenue, industry benchmarks)\n"
        "- Highlight key risks and opportunities in the data\n"
        "- Suggest actionable next steps when presenting financial metrics\n"
        "- Use professional financial terminology (EBITDA, DSO, working capital cycle)\n"
        "- Compare current metrics against previous periods when data is available\n"
        "- Flag anomalies or concerning trends proactively"
    )
```

### 6.4 Token Optimization ✅

**Files:** `core/token_optimizer.py` (new), updated `api/chat.py`, `api/streaming.py`

**Strategies:**
1. **Conversation history trimming** — keep only the last N messages in context (configurable via `max_context_messages` in settings, default 20)
2. **Tool result compression** — strip verbose metadata from tool responses before including in context; keep only the data the AI needs
3. **Structured data extraction** — when tool results contain large datasets, summarize to key metrics before including in context
4. **System prompt caching** — cache the system prompt per-user and only rebuild when settings change

```python
# ai_chatbot/core/token_optimizer.py
def trim_conversation_history(messages, max_messages=20):
    """Keep system prompt + last N messages."""
    system = [m for m in messages if m["role"] == "system"]
    history = [m for m in messages if m["role"] != "system"]
    return system + history[-max_messages:]

def compress_tool_result(result, max_rows=20):
    """Compress tool results to reduce token usage."""
    if isinstance(result.get("data"), list) and len(result["data"]) > max_rows:
        result["data"] = result["data"][:max_rows]
        result["_truncated"] = True
        result["_total_rows"] = len(result["data"])
    # Remove echart_option from context (frontend renders it, AI doesn't need it)
    result.pop("echart_option", None)
    return result
```

### 6.5 Cost Monitoring & Analytics ✅

**Files:** `chatbot/doctype/chatbot_token_usage/` (new DocType), `core/token_tracker.py` (new), updated `api/chat.py`

**Chatbot Token Usage** DocType:
- `user` (Link: User)
- `conversation` (Link: Chatbot Conversation)
- `provider` (Data) — OpenAI/Claude/Gemini
- `model` (Data) — specific model used
- `prompt_tokens` (Int)
- `completion_tokens` (Int)
- `total_tokens` (Int)
- `estimated_cost` (Currency) — calculated from token counts × model pricing
- `date` (Date)

**Token tracker middleware:**
```python
# ai_chatbot/core/token_tracker.py
def track_token_usage(provider, model, prompt_tokens, completion_tokens, user, conversation_id):
    """Record token usage for cost tracking."""
    cost = estimate_cost(provider, model, prompt_tokens, completion_tokens)
    frappe.get_doc({
        "doctype": "Chatbot Token Usage",
        "user": user,
        "conversation": conversation_id,
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated_cost": cost,
        "date": frappe.utils.today(),
    }).insert(ignore_permissions=True)

MODEL_PRICING = {
    # Per 1M tokens: (input, output)
    "gpt-4o": (2.50, 10.00),
    "claude-opus-4-5-20251101": (15.00, 75.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
}
```

**Monthly analytics tool** — registered as a chatbot tool so users can ask "How much have I spent on AI this month?":
```python
@register_tool(name="get_ai_usage_analytics", ...)
def get_ai_usage_analytics(from_date=None, to_date=None):
    """Get token usage and cost analytics."""
```

**Alerting:** Configurable monthly budget threshold in Chatbot Settings. When exceeded, log a warning and optionally notify the admin.

### 6.6 Source File Header Policy ✅

**Files:** All `.py`, `.js`, and `.vue` files in the project

Every Python, JavaScript, and Vue source file has been prepended with:
```python
# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
```
```javascript
// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt
```
```html
<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
```

65 files updated across Python, JavaScript, and Vue source files.

### 6.7 Deliverables ✅

| Item | Files |
|------|-------|
| Settings overhaul | Updated `chatbot_settings.json` (tabs, unified provider) |
| Gemini provider | Updated `ai_providers.py` (GeminiProvider class) |
| Finance AI behaviour | Updated `prompts.py` |
| Token optimization | `core/token_optimizer.py` (new) |
| Cost monitoring | `chatbot/doctype/chatbot_token_usage/` (new), `core/token_tracker.py` (new) |
| Source headers | All `.py` and `.js` files |

**New dependencies:** None (Gemini uses OpenAI-compatible REST API via `requests`).

---

## Phase 6A: UI Overhaul ✅

**Goal:** Redesign the chatbot UI for a cleaner, more professional look — remove header, redesign sidebar (Claude.AI-style), add real-time process indicators, greeting, search, proper alignment, and OS dark mode support.

### 6A.1 Header Removal & Sidebar Redesign ✅

**Files:** `ChatView.vue` (major rewrite), `Sidebar.vue` (complete rewrite), `ChatHeader.vue` (deleted)

- **Header removed entirely** — provider selector, settings gear, and sidebar toggle all moved to sidebar
- **Sidebar redesigned** (Claude.AI-inspired):
  - **Expanded mode (w-72):** Header row (hamburger toggle + logo + settings gear), grey "New Chat" button, search input with debounce, date-grouped conversations (Today/Yesterday/Last 7 Days/Older), provider selector dropdown at bottom
  - **Collapsed mode (w-14):** Icon-only strip — expand button, new chat (+), search icon
  - Sidebar always visible (collapse = icon strip, expand = full panel) — no more hide/show
  - `sidebarCollapsed` state persisted in `localStorage`
- **ChatView wiring:** Sidebar receives `:selected-provider`, `:sidebar-collapsed`, `:search-results`, `:is-searching` props; emits `@toggle-sidebar`, `@change-provider`, `@search`

### 6A.2 Remove Prompt Suggestions ✅

**Files:** `ChatInput.vue`

- Removed `suggestions` array, `handleSuggestionClick`, suggestion template block, `showSuggestions` prop
- Removed `Zap` icon import (was only used in hints bar)

### 6A.3 Send/Stop Button & Input Cleanup ✅

**Files:** `ChatInput.vue`

- **Send button:** Icon-only (`<Send :size="18" />`), 52×52px square, blue, `title="Send message"`
- **Stop button:** Icon-only (`<Square :size="16" />`), 52×52px square, red, `title="Stop generating"`
- **Hints bar removed** — no more "ERPNext tools enabled", "Voice input", "Press Enter to send"
- Layout: paperclip | textarea | mic | send/stop

### 6A.4 Personalized Greeting ✅ (Pre-Phase 6A)

**Files:** `ChatView.vue`

- When `hasNoMessages`: centered logo + "Hello, {UserFullName}!" + "How can I help you today?" + centered ChatInput
- Once a message is sent: normal bottom-pinned layout

### 6A.5 Chat Search ✅

**Files:** `api/chat.py` (new endpoint), `utils/api.js`, `Sidebar.vue`, `ChatView.vue`

- **Backend:** `search_conversations(query, limit=20)` — searches `Chatbot Conversation.title` and `Chatbot Message.content` using `LIKE %query%`, filters by current user, returns deduplicated results ordered by `updated_at desc`
- **Frontend API:** `chatAPI.searchConversations(query, limit)` method
- **Sidebar:** When search query is active, results replace grouped conversation list; "No results" empty state; clicking a result loads conversation and clears search
- **Debounce:** 300ms in Sidebar before emitting `@search` to ChatView

### 6A.6 Response Panel Width ✅

**Files:** `ChatMessage.vue`, `ChatView.vue`

- **Assistant messages:** `max-w-[85%] lg:max-w-5xl` (was `max-w-3xl`)
- **User messages:** `max-w-3xl` (unchanged)
- **Streaming bubble:** Same wider width as assistant messages
- Tables, charts, and code blocks now use the full available response width

### 6A.7 Dark Mode ✅

**Files:** `tailwind.config.js`, `App.vue`, `ChatMessage.vue`, `ChatInput.vue`, `Sidebar.vue`, `TypingIndicator.vue`, `ChatView.vue`

- **Tailwind:** `darkMode: 'class'` configuration
- **App.vue:** Detects `prefers-color-scheme: dark` on mount, toggles `dark` class on `<html>`, listens for OS theme changes; background changed from gradient to `bg-white dark:bg-gray-900`
- **Dark scrollbars:** Custom scrollbar colors for dark mode
- **Dark markdown:** Global CSS overrides for `.dark .markdown-body` (text, code, links, blockquotes, tables)
- **All components:** `dark:` variant classes on backgrounds, borders, text colors, hover states
- **Scoped styles:** ChatMessage.vue has dark mode overrides for `.markdown-body` elements

### 6A.8 Real-Time Process Indicators ✅

**Files:** `api/streaming.py`, `composables/useStreaming.js`, `TypingIndicator.vue`, `ChatView.vue`

**Backend (`streaming.py`):**
- New `_publish_process_step(conversation_id, stream_id, step, user)` helper
- Process steps published at 5 pipeline points:
  1. After stream start: `"Preparing context..."`
  2. Before provider call: `"Communicating with LLM..."`
  3. Before each tool execution: `"Executing {Tool Name}..."`
  4. After tool results: `"Processing results..."`
  5. Before saving: `"Saving response..."`

**Frontend (`useStreaming.js`):**
- New `processStep` ref (readonly)
- `ai_chat_process_step` event handler updates `processStep.value`
- Cleared in `reset()` and `startListening()`

**TypingIndicator.vue:**
- Accepts `processStep` prop
- Displays `{{ processStep || 'AI is thinking...' }}`
- Logo SVG replaces hardcoded "AI" text avatar
- Dark mode text color

**ChatView.vue:**
- Destructures `processStep` from `useStreaming()`
- Passes `:process-step="processStep"` to TypingIndicator
- Shows process step during streaming above content

### 6A.9 Logo, Favicon & User Avatar ✅

**Files:** `frontend/src/assets/logo.svg`, `frontend/public/favicon.svg`, `ChatMessage.vue`, `ChatView.vue`, `Sidebar.vue`, `TypingIndicator.vue`

- Custom orbital SVG (violet gradient, RGB dots, chat bubble tail) as favicon and logo
- Logo displayed in sidebar header, AI messages, streaming messages, and typing indicator
- User avatar on right side of user message bubbles with initials fallback

### 6A.10 Deliverables ✅

| Item | Files | Status |
|------|-------|--------|
| Header removal | Deleted `ChatHeader.vue` | ✅ |
| Sidebar redesign | Complete rewrite of `Sidebar.vue` (Claude.AI style, search, collapse, date groups, provider) | ✅ |
| Layout | Major rewrite of `ChatView.vue` (no header, greeting, wider messages, process steps) | ✅ |
| Process indicators | Updated `TypingIndicator.vue` + `streaming.py` + `useStreaming.js` | ✅ |
| Send/Stop icons | Updated `ChatInput.vue` (icon-only, no suggestions, no hints) | ✅ |
| Chat search | `search_conversations()` endpoint + `searchConversations()` API + sidebar search UI | ✅ |
| Dark mode | `tailwind.config.js`, `App.vue`, all components with `dark:` variants | ✅ |
| Response width | `ChatMessage.vue` wider assistant messages (`max-w-[85%] lg:max-w-5xl`) | ✅ |

**New dependencies:** None.

---

## Phase 6B: Multi-Dimensional Analytics & GL-Based Finance

**Goal:** Support multi-dimensional/hierarchical data grouping (Company → Vertical → Segment × Period) and enhance finance tools with GL Entry-based queries for authoritative accounting data.

**Priority:** Medium

### 6B.1 Multi-Dimensional Data Grouping Tool

**Files:** `tools/finance/analytics.py` (new), `data/grouping.py` (new)

**Architecture:**
A generic multi-dimensional grouping tool that accepts user-specified dimensions and periods:

```python
@register_tool(
    name="get_multidimensional_summary",
    category="finance",
    description="Generate a multi-dimensional summary grouped by any combination of Company, Business Vertical, Business Segment, Cost Center, Department, Territory, and time period (Monthly/Quarterly/Yearly)",
    parameters={
        "metric": {"type": "string", "description": "What to measure: 'revenue', 'expenses', 'profit', 'orders'"},
        "group_by": {"type": "array", "items": {"type": "string"}, "description": "Dimensions to group by, in order (e.g. ['company', 'business_vertical', 'business_segment'])"},
        "period": {"type": "string", "description": "Time grouping: 'monthly', 'quarterly', 'yearly'"},
        "from_date": {"type": "string"},
        "to_date": {"type": "string"},
        "company": {"type": "string"},
    },
    doctypes=["Sales Invoice", "GL Entry"],
)
def get_multidimensional_summary(metric, group_by, period="quarterly", ...):
    ...
```

**Output format:**
Hierarchical data with parent/child relationships and period columns:
```json
{
    "headers": ["Description", "Total", "Q4", "Q3", "Q2", "Q1"],
    "rows": [
        {"description": "Company I", "level": 0, "is_group": true, "values": [218.50, 65.00, 57.50, 51.00, 45.00]},
        {"description": "Vertical I", "level": 1, "is_group": true, "values": [149.50, 45.00, 39.50, 35.00, 30.00]},
        {"description": "Segment I", "level": 2, "is_group": false, "values": [60.00, 18.00, 16.00, 14.00, 12.00]},
        ...
    ]
}
```

**Frontend rendering:**
- Parent rows in **bold** with different background colour
- Child rows indented by level
- Period total column
- Appropriate chart (stacked bar or grouped bar by top-level dimension)

### 6B.2 GL Entry-Based Finance Queries

**Files:** `tools/finance/gl_analytics.py` (new)

Use `tabGL Entry` joined with `tabAccount` and `tabCompany` for authoritative accounting data:

```python
@register_tool(
    name="get_gl_summary",
    category="finance",
    description="Get General Ledger summary with flexible grouping by account type, root type, party, and time period. Uses GL entries for authoritative accounting data.",
    parameters={
        "group_by": {"type": "string", "description": "Group by: 'account_type', 'root_type', 'party_type', 'voucher_type', 'account_name'"},
        "root_type": {"type": "string", "description": "Filter by root type: 'Asset', 'Liability', 'Equity', 'Income', 'Expense'"},
        "account_type": {"type": "string", "description": "Filter by account type: 'Bank', 'Cash', 'Receivable', 'Payable', etc."},
        "from_date": {"type": "string"},
        "to_date": {"type": "string"},
        "company": {"type": "string"},
    },
    doctypes=["GL Entry", "Account"],
)
def get_gl_summary(...):
    """Query GL entries with Account and Company joins.

    Key fields: posting_date, fiscal_year, account_name, root_type, report_type,
    account_type, party_type, party, company, debit, credit,
    debit_in_account_currency, credit_in_account_currency, voucher_type
    """
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    query = (
        frappe.qb.from_(gl)
        .join(acc).on(gl.account == acc.name)
        .where(gl.is_cancelled == 0)
        .where(gl.company == company)
    )
    ...
```

**Specific GL-based shortcuts:**
- Cash & bank position: `root_type='Asset'` + `account_type` in ('Bank', 'Cash')
- Bank liabilities: `root_type='Liability'` + `account_type='Bank'`
- Accounts Payable: `account_type='Payable'`
- Accounts Receivable: `account_type='Receivable'`

### 6B.3 Enhanced CFO Dashboard with BI Cards

**Files:** `tools/finance/cfo.py` (updated)

Add BI-style cards to the CFO dashboard response:
```json
{
    "cards": [
        {"label": "Revenue", "value": 1250000, "change": 12.5, "change_period": "YoY", "icon": "trending-up"},
        {"label": "Net Profit", "value": 187500, "change": -3.2, "change_period": "YoY", "icon": "trending-down"},
        {"label": "Cash Position", "value": 450000, "icon": "wallet"},
        {"label": "AR Outstanding", "value": 320000, "change": 8.1, "change_period": "MoM", "icon": "alert"}
    ]
}
```

Frontend renders these as styled metric cards above the charts.

### 6B.4 Deliverables

| Item | Files |
|------|-------|
| Multi-dimensional grouping | `tools/finance/analytics.py`, `data/grouping.py` |
| GL Entry analytics | `tools/finance/gl_analytics.py` |
| Enhanced CFO dashboard | Updated `tools/finance/cfo.py` |
| Frontend rendering | Updated `ChatMessage.vue` (hierarchical tables, BI cards) |

**New dependencies:** None.

---

## Phase 6C: Workspace, Help & Language Selection

**Goal:** Create a Frappe workspace for desk access, add user help with sample prompts, move response language to the chat UI.

**Priority:** Low

### 6C.1 Workspace

**Files:** `chatbot/workspace/ai_chatbot/ai_chatbot.json` (new)

Create a workspace similar to CRM's pattern — a landing page with:
- Shortcut to the chatbot (`/ai-chatbot`)
- Shortcuts to Chatbot Settings, Conversations, Messages (for admin)
- Number cards: total conversations, messages today, token usage
- Custom block with quick-access link

### 6C.2 User Help Button

**Files:** `ChatInput.vue` (or new `HelpModal.vue`), `SAMPLE_USER_PROMPT.md` (new)

- Add a help icon button alongside the send button
- On click, show a modal with sample prompts and expected results
- Prompts organized by category (Sales, Finance, HR, etc.)
- Each prompt shows the expected output format (table, chart, number)

### 6C.3 Response Language Selection in Chat UI

**Files:** `Sidebar.vue` or `ChatView.vue`, `api/chat.py`

- Move "Response Language" from Chatbot Settings to the chat UI
- Add a language selector dropdown below "New Chat" in the sidebar
- Per-conversation language preference (stored in conversation metadata)
- Remove `response_language` from Chatbot Settings (or keep as default fallback)

### 6C.4 Deliverables

| Item | Files |
|------|-------|
| Workspace | `chatbot/workspace/ai_chatbot/ai_chatbot.json` |
| Help button | Updated `ChatInput.vue`, `HelpModal.vue`, `SAMPLE_USER_PROMPT.md` |
| Language selector | Updated `Sidebar.vue`, `api/chat.py` |

**New dependencies:** None.

---

## Phase 7: Agentic RAG — Vector Search + Multi-Agent Orchestration

**Goal:** Implement a full Agentic RAG system — combining vector-based document retrieval with multi-agent orchestration, planning, and iterative refinement.

### 7.1 RAG Foundation (`ai_chatbot/ai/rag/`)

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

### 7.2 Agent Framework (`ai_chatbot/ai/agents/`)

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

### 7.3 Memory System (`ai_chatbot/ai/memory/`)

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

### 7.4 Knowledge Base DocType & Indexing

**Chatbot Knowledge Base** (new DocType):
- Fields: `title`, `source_type` (File/ERPNext Record/URL), `source_reference`, `company`, `status` (Indexed/Pending/Failed), `chunk_count`, `last_indexed`
- Tracks what has been indexed into the vector store

**Indexing pipeline:**
- **Manual:** Upload PDF/DOCX via a "Knowledge Base" page in the frontend
- **Automatic:** Index key ERPNext records (Items, Customers, Suppliers, policies) via scheduled task
- **Incremental:** Only re-index documents that have changed since last indexing

### 7.5 Frontend

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

### 7.6 Deliverables

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

## Phase 8: Intelligent Document Processing (IDP)

**Goal:** Extract data from uploaded documents (invoices, receipts, POs) and create ERPNext records. Includes file upload capability, data comparison, and reconciliation.

### 8.1 File Upload Infrastructure (Completed in Phase 5A)

File upload and Vision API support was implemented in Phase 5A:
- `api/files.py` — upload endpoint, base64 encoding, vision content builder
- Frontend: file picker + drag-and-drop in ChatInput (accept PDF, images, Excel, CSV, DOCX, TXT)
- Frappe File DocType storage with `is_private=True`
- Image attachments sent to LLM Vision API (OpenAI & Claude)
- Non-image attachments annotated as text in message context

**Phase 7 extends this with:**
- PDF/Excel text extraction for prompt context
- Structured data extraction from documents

### 8.2 Document Extraction (`ai_chatbot/idp/`)

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

### 8.3 Data Comparison & Reconciliation

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

### 8.4 Frontend

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

### 8.5 Deliverables

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

**Goal:** Scheduled reports, alerts, automated workflows, and auto-email triggered by chat or conditions.

### 10.1 Auto Email & Scheduled Reports

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

### 10.2 Alert System

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

### 10.3 Notification Channels

```
ai_chatbot/automation/notifications/
├── __init__.py
├── channels/
│   ├── email.py               # Email via frappe.sendmail
│   ├── whatsapp.py            # WhatsApp via Twilio (already a dependency)
│   └── slack.py               # Slack webhook integration
└── dispatcher.py              # Routes alerts to appropriate channels
```

### 10.4 Deliverables

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

| Phase | Focus | Priority | Status | Key Deliverable | Dependencies Added |
|-------|-------|----------|--------|------------------|--------------------|
| **1** | Foundation | — | ✅ Done | Data layer, multi-company/currency, security fixes | None |
| **2** | Streaming | — | ✅ Done | Frappe Realtime token streaming, enhanced chat UX | None |
| **3** | CRUD | — | ✅ Done | Create/update/delete ERPNext records via chat | None |
| **4** | Finance | — | ✅ Done | 17 finance tools, ECharts integration, multi-color charts | echarts (npm) |
| **5** | HRMS & CRM | — | ✅ Done | 6 HRMS tools, 5 CRM tools with charts | None |
| **5A** | UX & Accessibility | — | ✅ Done | File upload + Vision API, voice I/O, @mentions, sidebar toggle | None |
| **5B** | Enterprise Analytics | — | ✅ Done | Permissions, dimensions, CFO dashboard, consolidation, config, plugins | None |
| **6** | Settings & Gemini | High | ✅ Done | Unified provider config, Gemini, token/cost tracking, file headers | None |
| **6A** | UI Overhaul | High | ✅ Done | Claude-style sidebar, process indicators, greeting, search, dark mode | None |
| **6B** | Multi-Dim Analytics | Medium | Planned | Hierarchical grouping, GL Entry finance, BI cards | None |
| **6C** | Workspace & Help | Low | Planned | Frappe workspace, help button, language selector | None |
| **7** | Agentic RAG | Medium | Planned | Vector search + multi-agent orchestration + memory | chromadb, pypdf, python-docx |
| **8** | IDP | Medium | Planned | Document extraction, data comparison/reconciliation | Pillow, pytesseract (opt), openpyxl |
| **9** | Predictive | Low | Planned | Forecasting, anomaly detection | pandas, numpy, prophet (opt) |
| **10** | Automation | Low | Planned | Auto-email, scheduled reports, alerts, notifications | slack_sdk (opt) |

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

### Company Isolation for RAG (Phase 7)

Vector store collections are namespaced by company:
- Collection name: `knowledge_{company_name_slug}`
- Queries only search the current user's company collection
- Cross-company search requires explicit permission

---

## Architectural Queries & Recommendations

### Q: pandas, numpy for data analysis — will it make a difference?

**Recommendation: Not needed now. Consider for Phase 9 (Predictive) only.**

For the current tool-based analytics (Phases 1–6B), `frappe.qb` (Query Builder) handles all aggregation, grouping, and filtering at the database level — which is more efficient than pulling raw data into Python for processing. pandas/numpy would add ~200MB to the install footprint and introduce memory concerns for large datasets.

**When they become useful:**
- **Phase 9 (Predictive Analytics):** Time series decomposition, moving averages, trend analysis — pandas is the right tool here
- **Phase 6B (Multi-Dimensional Grouping):** If pivot-table-like operations become complex, pandas `pivot_table()` could simplify the code — but SQL GROUP BY with ROLLUP can handle most cases

**Recommendation per library:**
| Library | Verdict | When |
|---------|---------|------|
| `pandas` | Use in Phase 9 | Time series, forecasting, pivot tables |
| `numpy` | Use with pandas | Comes as pandas dependency |
| `matplotlib/seaborn` | Skip | ECharts handles all visualization (client-side) |
| `pydantic` | Skip | Frappe's DocType validation is sufficient; tools use simple dicts |
| `scipy/sklearn` | Phase 9+ only | Only if ML-based anomaly detection or forecasting is needed |

### Q: How to show tools added by other applications?

**Already implemented (Phase 5B.8).** External apps register tools via the `ai_chatbot_tool_modules` Frappe hook in their `hooks.py`. The registry dynamically loads and exposes these tools. See Phase 5B.8 in this roadmap for details.

### Q: Desk Page — can we create ai-chatbot as a Frappe desk page?

**Current approach is correct and better.** The app already uses Frappe's portal page pattern (`www/ai-chatbot.html` + `www/ai_chatbot.py`), which is the same pattern used by Frappe CRM. This gives full control over the layout (no Frappe desk chrome/sidebar interfering with the chat UI).

**For desk integration:** Phase 6C adds a Frappe Workspace with a shortcut link to `/ai-chatbot`. This gives users a desk-accessible entry point while keeping the full-screen chat experience. The workspace also shows admin shortcuts (Settings, Conversations, Token Usage).

### Q: Smart Compose & Autocomplete — predictive text suggestions?

**Feasible but not recommended for current scope.** This would require:
- Client-side text prediction model (large JS bundle) or server-round-trip per keystroke (latency)
- The @mention system (Phase 5A) already provides structured autocomplete for common parameters
- Low ROI: users type free-form natural language — predicting the next word in "Show me sales for..." is less useful than in structured search

**If desired later:** Could be implemented as a lightweight Phase 11 using the browser's built-in `<datalist>` element with a curated list of common prompt fragments.

### Q: Artifact Streaming — what is it?

**Artifact streaming** (as implemented by Claude.ai and similar) is a pattern where the AI generates a distinct, self-contained artifact (code file, document, diagram) separately from the conversational response. The artifact streams into a dedicated side panel while the conversation continues in the main panel.

**How it differs from normal streaming:**
- Normal streaming: tokens flow sequentially into one output area
- Artifact streaming: the AI signals "I'm creating an artifact" and tokens route to a separate panel

**Relevance to this project:** Low. The chatbot's outputs are conversational responses with inline charts/tables — not standalone artifacts. The ECharts rendering already handles the "rich output" use case. Artifact streaming would add complexity without clear benefit for ERP analytics. Skip.

### Q: Chatbot Audit Log — is it needed?

**Partially implemented, sufficient for now.** The current system already tracks:
- All messages (Chatbot Message DocType) with timestamps, user, tokens used
- Tool calls and results (stored as JSON in message records)
- Conversation metadata (total tokens, message count)

**Phase 6 adds:** Per-request token usage tracking with cost estimates (Chatbot Token Usage DocType).

**What's not tracked (and probably not needed):**
- Prompt injection attempts — the AI is read-only by default (write ops require explicit enable)
- Detailed latency metrics — can be added later as a Phase 2.2 tool performance monitor (see todo_II item 2.2)
- A separate "audit log" DocType would be redundant with the existing message/token tracking

### Q: Agentic RAG + Memory — is it necessary given the limited scope?

**Re-evaluation based on your clarified scope** (no document search, only extract structured data from documents for creating ERPNext records or comparing with existing records):

**Agentic RAG is NOT needed.** Your use case is **Intelligent Document Processing (IDP)**, which is already planned as Phase 8. The IDP approach (LLM Vision → structured extraction → ERPNext mapping) does not require vector stores, embeddings, or retrieval.

**Memory system is partially useful:**
- **Conversation memory** — already implemented (messages stored in DB, context window managed)
- **Knowledge memory** (long-term) — not needed without document search
- **Memory manager** (context allocation) — addressed by Phase 6.4 token optimization

**Recommendation:** Simplify Phase 7 (Agentic RAG) to focus only on the multi-agent orchestration pattern (planner + analyst agents) for complex multi-step queries. Drop the RAG/vector store components unless a clear document search use case emerges.

### Q: Python Libraries recommendation

| Library | Recommendation | Rationale |
|---------|---------------|-----------|
| `pandas` | Phase 9 only | Overkill for SQL-based aggregations; valuable for time series and forecasting |
| `numpy` | Phase 9 only | Comes with pandas; needed for statistical operations |
| `matplotlib/seaborn` | Skip entirely | All visualization is ECharts (client-side); no server-side chart rendering needed |
| `pydantic` | Skip | Frappe DocTypes + simple dicts are sufficient; adding pydantic would be a parallel validation layer |
| `scipy` | Phase 9 only | Statistical tests, anomaly detection (z-score, IQR) |
| `sklearn` | Phase 9+ only | Only if ML-based forecasting or classification is needed |

**Memory considerations:** ERPNext datasets are moderate (thousands to low millions of records). SQL aggregations with proper indexes handle this efficiently. Pulling large datasets into pandas DataFrames would increase memory usage — keep processing at the DB level via `frappe.qb`.

### Q: Tool Performance Monitoring

**Planned as part of Phase 6.5 (Cost Monitoring).** The token tracker records per-request metrics. Adding LLM latency and prompt-to-response timing is a natural extension:
- Record `start_time` and `end_time` for each AI call
- Record tool execution time per tool call
- Expose via a `get_performance_metrics` tool so admins can ask "Which tools are slowest?"

---

## Future-Proofing Architecture

The current architecture already supports several future-proofing patterns:

| Pattern | Status | Implementation |
|---------|--------|----------------|
| **Modular AI provider abstraction** | ✅ Done | `AIProvider` base class in `ai_providers.py` — add new providers by subclassing |
| **Pluggable tool framework** | ✅ Done | `@register_tool` decorator + hooks-based plugin loading (Phase 5B.8) |
| **LLM-agnostic architecture** | ✅ Done | Unified provider config; all providers use the same tool schema format |
| **Event-driven processing** | ✅ Done | Streaming via `frappe.publish_realtime` (Redis Pub/Sub + Socket.IO) |
| **Agentic orchestration readiness** | Phase 7 | Multi-agent framework with planner + analyst agents |
| **Graph-based execution** | Phase 7+ | Could be added to the planner agent for complex query decomposition |

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
├── api/                           # Phase 1, 2, 3, 5A, 7
│   ├── chat.py                    # Updated: 5A (attachments, @mention endpoint)
│   ├── streaming.py               # Phase 2, updated: 5A (attachments, vision content)
│   ├── files.py                   # Phase 5A (file upload, vision content builder)
│   └── documents.py               # Phase 7 (IDP)
│
├── utils/
│   └── ai_providers.py            # Updated: 5A (Claude multimodal/vision content conversion)
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
│   ├── Sidebar.vue                # Updated: 5A (collapsible via parent CSS)
│   ├── ChatHeader.vue             # Updated: 5A (sidebar toggle button)
│   ├── ChatMessage.vue            # Updated: 4 (charts), 5A (attachments, speaker button)
│   ├── ChatInput.vue              # Updated: 5A (file upload, voice, @mentions, suggestions)
│   ├── TypingIndicator.vue
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
│   ├── ChatView.vue               # Updated: 5A (sidebar toggle, payload handling, voice output, suggestions)
│   ├── KnowledgeBaseView.vue      # Phase 6
│   └── DocumentProcessingView.vue # Phase 7
├── composables/
│   ├── useStreaming.js             # Phase 2
│   ├── useSocket.js               # Phase 2
│   ├── useVoiceInput.js           # Phase 5A (speech-to-text)
│   ├── useVoiceOutput.js          # Phase 5A (text-to-speech)
│   └── useFileUpload.js           # Phase 5A (file selection/validation/preview)
└── utils/
    ├── api.js                     # Updated: 5A (uploadFile, getMentionValues, attachments)
    └── markdown.js                # Phase 2
```
