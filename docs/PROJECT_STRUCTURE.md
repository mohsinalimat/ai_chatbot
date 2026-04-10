# AI Chatbot -- Project Structure (v1.0)

Comprehensive directory map and architecture reference for the AI Chatbot Frappe application. Every directory and significant file is documented with its purpose, key patterns, and how the pieces connect.

---

## Table of Contents

1. [Root Directory Overview](#root-directory-overview)
2. [Frontend -- Vue 3 SPA](#frontend----vue-3-spa)
3. [Backend -- Python Package](#backend----python-package)
   - [API Layer](#api-layer)
   - [Frappe Module and DocTypes](#frappe-module-and-doctypes)
   - [Core Business Logic](#core-business-logic)
   - [AI Agents (Multi-Agent Orchestration)](#ai-agents-multi-agent-orchestration)
   - [Tools (Business Intelligence)](#tools-business-intelligence)
   - [IDP (Intelligent Document Processing)](#idp-intelligent-document-processing)
   - [Data Processing Utilities](#data-processing-utilities)
   - [Automation](#automation)
   - [Utilities](#utilities)
   - [Static Assets and Templates](#static-assets-and-templates)
4. [Documentation](#documentation)
5. [Key Patterns](#key-patterns)
6. [Build Pipeline](#build-pipeline)
7. [Database Schema](#database-schema)
8. [Configuration Files](#configuration-files)
9. [Request Lifecycle](#request-lifecycle)

---

## Root Directory Overview

```
ai_chatbot/                                    # Root app directory (Git repository root)
|
+-- frontend/                                  # Vue 3 SPA (Vite + Tailwind CSS)
+-- ai_chatbot/                                # Python package (Frappe backend)
+-- docs/                                      # Project documentation
|
+-- pyproject.toml                             # Python project metadata, Ruff config
+-- setup.py / setup.cfg                       # Legacy package setup (Frappe compatibility)
+-- CLAUDE.md                                  # AI assistant instructions for contributors
+-- LICENSE                                    # MIT License
+-- .editorconfig                              # Editor settings (tabs, LF, UTF-8)
+-- .eslintrc                                  # ESLint config (Frappe globals)
+-- .pre-commit-config.yaml                    # Pre-commit hooks (ruff, prettier, eslint)
+-- .gitignore                                 # Git ignore rules
```

---

## Frontend -- Vue 3 SPA

The frontend is a standalone Vue 3 Single Page Application built with Vite, styled with Tailwind CSS, and served at `/ai-chatbot/`. It communicates with the Frappe backend exclusively through `@frappe.whitelist()` API endpoints. All chart rendering uses Apache ECharts.

### Directory Tree

```
frontend/
+-- src/
|   +-- components/
|   |   +-- Sidebar.vue                       # Conversation list, search, provider selector,
|   |   |                                       language selector, dark mode toggle
|   |   +-- ChatHeader.vue                    # Top bar: conversation title, controls,
|   |   |                                       PDF export buttons
|   |   +-- ChatMessage.vue                   # Message bubble: markdown, code blocks,
|   |   |                                       tables, charts, PDF export per message
|   |   +-- ChatInput.vue                     # Message input: @mention autocomplete,
|   |   |                                       file upload, voice input (mic button)
|   |   +-- TypingIndicator.vue               # Animated loading dots during AI response
|   |   +-- AgentThinking.vue                 # Multi-agent plan/step progress display
|   |   +-- HelpModal.vue                     # Help overlay with usage instructions
|   |   +-- charts/
|   |       +-- ChartMessage.vue              # Wrapper that detects and renders chart data
|   |       +-- EChartRenderer.vue            # ECharts instance manager (init, resize, dispose)
|   |       +-- BiCards.vue                   # Business Intelligence metric cards (KPI tiles)
|   |       +-- HierarchicalTable.vue         # Nested/grouped expandable data tables
|   |
|   +-- pages/
|   |   +-- ChatView.vue                      # Main chat interface; orchestrates Sidebar,
|   |                                           ChatHeader, message list, and ChatInput
|   |
|   +-- composables/
|   |   +-- useStreaming.js                   # Socket.IO streaming composable (token events,
|   |   |                                       tool call events, process steps)
|   |   +-- useSocket.js                      # Low-level Socket.IO connection manager
|   |   +-- useFileUpload.js                  # File upload composable (drag-drop, paste)
|   |   +-- useVoiceInput.js                  # Web Speech API for voice-to-text input
|   |   +-- useVoiceOutput.js                 # Text-to-speech for AI responses
|   |
|   +-- utils/
|   |   +-- api.js                            # ChatAPI singleton -- all backend communication,
|   |   |                                       CSRF token handling, error management
|   |   +-- markdown.js                       # Markdown rendering with marked + highlight.js
|   |
|   +-- assets/
|   |   +-- logo.svg                          # App logo (used in sidebar header)
|   |   +-- favicon.svg                       # Browser tab icon
|   |
|   +-- App.vue                               # Root component with <router-view>
|   +-- main.js                               # Entry point: creates Vue app, router, mounts
|   +-- style.css                             # Global styles: Tailwind directives + custom CSS
|
+-- public/
|   +-- logo.svg                              # Static logo (copied verbatim to build output)
|   +-- favicon.svg                           # Static favicon
|
+-- index.html                                # SPA entry HTML (Vite dev server / build input)
+-- vite.config.js                            # Vite build config (aliases, manual chunks, output)
+-- tailwind.config.js                        # Tailwind CSS config (dark mode: class, custom colors)
+-- postcss.config.js                         # PostCSS config (tailwindcss + autoprefixer)
+-- package.json                              # Frontend dependencies and npm scripts
```

### How the Frontend Pieces Connect

1. **Entry**: `main.js` creates the Vue app with `vue-router`, mounts `App.vue`.
2. **Routing**: A single route `/` renders `ChatView.vue`. The base path is `/ai-chatbot/`.
3. **ChatView** is the orchestrator -- it lays out `Sidebar` (left panel), `ChatHeader` (top), the scrollable message list of `ChatMessage` components, and `ChatInput` (bottom).
4. **API calls** go through the `ChatAPI` singleton in `utils/api.js`, which handles CSRF token injection and calls Frappe's `/api/method/ai_chatbot.api.*` endpoints.
5. **Streaming**: When streaming is enabled, `useStreaming.js` listens for Socket.IO events (`ai_chat_token`, `ai_chat_tool_call`, `ai_chat_stream_end`, etc.) published by the backend via `frappe.publish_realtime`.
6. **Charts**: When a message contains `tool_results` with `echart_option`, `ChartMessage.vue` detects it and delegates to `EChartRenderer.vue`, which calls `echarts.setOption()` with the server-provided configuration.
7. **Dark mode**: Toggled in `Sidebar.vue`, applies the `dark` class to `<html>`, which Tailwind picks up via `darkMode: 'class'`.

---

## Backend -- Python Package

The `ai_chatbot/` directory inside the repository root is the Frappe Python package. It follows Frappe's app structure conventions.

```
ai_chatbot/                                    # Python package root
+-- __init__.py                               # Package init: app metadata, version ("0.0.1"),
|                                               ai_chatbot_tool_modules hook list
+-- hooks.py                                  # App metadata, scheduled tasks (cron), hook list
+-- modules.txt                               # Frappe module list: "Chatbot"
+-- patches.txt                               # Database migration patches (empty initially)
|
+-- api/                                      # REST API endpoints
+-- chatbot/                                  # Frappe "Chatbot" module (DocTypes, workspace)
+-- core/                                     # Core business logic and shared utilities
+-- ai/                                       # Multi-agent orchestration system
+-- tools/                                    # Business intelligence tool registry + tools
+-- idp/                                      # Intelligent Document Processing pipeline
+-- data/                                     # Data aggregation, grouping, charting helpers
+-- automation/                               # Scheduled report runner and formatters
+-- utils/                                    # AI provider integrations
+-- public/                                   # Static assets served by Frappe
+-- templates/                                # Jinja HTML templates
+-- desktop_icon/                             # Frappe desktop icon config
+-- workspace_sidebar/                        # Workspace sidebar navigation config
```

---

### API Layer

All endpoints use the `@frappe.whitelist()` decorator. The frontend calls them via `/api/method/ai_chatbot.api.<module>.<function>`.

```
ai_chatbot/api/
+-- __init__.py
+-- chat.py                                   # Core chat API (12 endpoints):
|                                               create_conversation, get_conversations,
|                                               get_conversation_messages, send_message,
|                                               delete_conversation, update_conversation_title,
|                                               set_conversation_language, get_settings,
|                                               search_conversations, get_mention_values
|
+-- streaming.py                              # Streaming API:
|                                               send_message_streaming -- enqueues a background
|                                               job that streams tokens via
|                                               frappe.publish_realtime (Redis Pub/Sub ->
|                                               Socket.IO -> browser)
|
+-- files.py                                  # File upload API:
|                                               upload_chat_file -- stores via Frappe File
|                                               DocType; returns metadata + base64 for images.
|                                               build_vision_content -- constructs multimodal
|                                               content arrays for Vision API.
|
+-- export.py                                 # PDF export API:
                                                export_message_pdf -- single message to PDF.
                                                export_conversation_pdf -- full thread to PDF.
                                                Uses Frappe's get_pdf (wkhtmltopdf) and reuses
                                                HTML formatters from automation/formatters.py.
```

**Key behaviors in chat.py**:
- `send_message` routes to streaming or non-streaming based on the `stream` parameter.
- Non-streaming mode runs a multi-round tool call loop (up to 5 rounds).
- Before calling the AI, it checks `should_orchestrate()` to decide if the multi-agent pipeline should handle the query.
- Conversation titles are auto-generated from the first user message.
- `get_mention_values` powers the @mention autocomplete (companies, periods, cost centers, customers, items, accounting dimensions).

---

### Frappe Module and DocTypes

```
ai_chatbot/chatbot/
+-- doctype/
|   +-- chatbot_settings/                     # Single DocType (one global record)
|   |   +-- chatbot_settings.json             # Schema: provider config, tool toggles,
|   |   |                                       query limits, prompts, streaming, automation
|   |   +-- chatbot_settings.py               # Controller (minimal -- uses Frappe defaults)
|   |   +-- chatbot_settings.js               # Client-side form script
|   |
|   +-- chatbot_conversation/                 # Conversation records
|   |   +-- chatbot_conversation.json         # Schema: title, user, ai_provider, status,
|   |   |                                       message_count, total_tokens, session_context
|   |   +-- chatbot_conversation.py           # Controller
|   |
|   +-- chatbot_message/                      # Individual chat messages
|   |   +-- chatbot_message.json              # Schema: conversation (link), role, content,
|   |   |                                       timestamp, tokens_used, tool_calls (JSON),
|   |   |                                       tool_results (JSON), attachments (JSON)
|   |   +-- chatbot_message.py                # Controller
|   |
|   +-- chatbot_token_usage/                  # Per-request token and cost tracking
|   |   +-- chatbot_token_usage.json          # Schema: user, conversation, provider, model,
|   |   |                                       prompt_tokens, completion_tokens, total_tokens,
|   |   |                                       estimated_cost, date
|   |   +-- chatbot_token_usage.py            # Controller
|   |
|   +-- chatbot_scheduled_report/             # Automated report scheduling
|       +-- chatbot_scheduled_report.json     # Schema: report_name, prompt, company, format,
|       |                                       schedule, time_of_day, day_of_week/month,
|       |                                       cron_expression, recipients, last_run, status
|       +-- chatbot_scheduled_report.py       # Controller
|
+-- workspace/
    +-- chatbot/
        +-- chatbot.json                   # Frappe workspace definition (dashboard,
                                                shortcuts, number cards for token usage)
```

---

### Core Business Logic

Shared modules used across the API layer, tools, and automation.

```
ai_chatbot/core/
+-- config.py                                 # Company resolution (fuzzy match via LIKE),
|                                               fiscal year dates, currency lookup, query
|                                               limits, tool category enabled checks,
|                                               is_erpnext_installed(), is_hrms_installed()
|
+-- constants.py                              # App-wide constants: DATE_FORMAT, query limits,
|                                               aging buckets, TOOL_CATEGORIES map,
|                                               BASE_AMOUNT_FIELDS, forecast defaults
|
+-- prompts.py                                # System prompt builder: dynamically assembles
|                                               persona, user context, company/currency/FY,
|                                               multi-company consolidation context, enabled
|                                               tools, IDP workflow, predictive guidelines,
|                                               write operation rules, response language,
|                                               custom admin instructions, formatting rules
|
+-- session_context.py                        # Per-conversation session state (stored as JSON
|                                               in Chatbot Conversation.session_context):
|                                               include_subsidiaries, target_currency,
|                                               response_language. Provides get_company_filter()
|                                               which tools call for session-aware queries.
|
+-- consolidation.py                          # Parent/child company detection using
|                                               frappe.db.get_descendants(). Provides
|                                               get_consolidated_data() for cross-company
|                                               tool execution with exchange rates.
|
+-- token_optimizer.py                        # Context compression strategies:
|                                               1. Trim conversation to last N messages
|                                               2. Strip echart_option from tool results
|                                               3. Truncate large data arrays to max_rows
|
+-- token_tracker.py                          # Records per-request token usage to the
|                                               Chatbot Token Usage DocType. Includes
|                                               MODEL_PRICING table for cost estimation
|                                               (OpenAI, Claude, Gemini models).
|
+-- ai_utils.py                               # Provider-agnostic response parsing:
|                                               extract_response() and extract_tool_info()
|                                               handle both OpenAI/Gemini and Claude formats.
|
+-- exceptions.py                             # Custom exception hierarchy:
|                                               ChatbotError (base), ToolExecutionError,
|                                               ProviderError, CompanyRequiredError,
|                                               ToolNotFoundError, DocumentValidationError,
|                                               InsufficientDataError
|
+-- logger.py                                 # Structured logging wrappers around
                                                frappe.log_error with consistent formatting.
                                                log_error(), log_tool_error(),
                                                log_provider_error().
```

---

### AI Agents (Multi-Agent Orchestration)

The multi-agent system handles complex queries that require multiple data lookups, comparisons, or cross-domain analysis. It decomposes the user's question into a plan of steps, executes each step using the appropriate tools, then synthesizes a unified response.

```
ai_chatbot/ai/
+-- agents/
    +-- __init__.py
    +-- orchestrator.py                       # Main entry point: should_orchestrate() checks
    |                                           settings + classifier; run_orchestrated() and
    |                                           run_orchestrated_streaming() coordinate the
    |                                           planner -> analyst -> synthesis pipeline.
    |
    +-- classifier.py                         # Query complexity classifier: determines if a
    |                                           query needs multi-agent handling (comparison
    |                                           queries, cross-domain analysis, multi-step
    |                                           data gathering).
    |
    +-- planner.py                            # Plan generator: decomposes a complex query
    |                                           into ordered steps, each specifying which tool
    |                                           to call and with what arguments.
    |
    +-- analyst.py                            # Step executor: runs individual plan steps,
    |                                           executes tool calls, collects results. Supports
    |                                           both streaming and non-streaming execution.
    |
    +-- context.py                            # AgentContext dataclass: carries conversation
    |                                           state, accumulated results, and metadata
    |                                           across the orchestration pipeline.
    |
    +-- prompts.py                            # Specialized prompts for the classifier, planner,
                                                and synthesis stages.
```

---

### Tools (Business Intelligence)

Tools are Python functions that query ERPNext data and return structured results. They self-register via the `@register_tool` decorator at import time. The registry provides OpenAI-compatible function calling schemas to the AI provider and handles execution with permission checks.

```
ai_chatbot/tools/
+-- registry.py                               # Core registration system:
|                                               @register_tool decorator, _TOOL_REGISTRY dict,
|                                               get_all_tools_schema() (builds OpenAI schemas),
|                                               execute_tool() (with DocType permission checks),
|                                               register_tool_category() for external plugins.
|                                               Lazy-loads tool modules on first access.
|
+-- base.py                                   # Backward-compatible wrapper:
|                                               BaseTool.execute_tool() and
|                                               get_all_tools_schema() delegate to registry.
|
+-- common.py                                 # Shared helpers: primary() for company lists,
|                                               common utility functions used across tools
|
+-- selling.py                                # Sales analytics (5 tools):
|                                               get_sales_analytics, get_top_customers,
|                                               get_transaction_trend, get_sales_by_territory,
|                                               get_by_item_group
|
+-- buying.py                                 # Purchase analytics (2 tools):
|                                               get_purchase_analytics, get_supplier_performance
|
+-- stock.py                                  # Inventory tools (4 tools):
|                                               get_inventory_summary, get_low_stock_items,
|                                               get_stock_movement, get_stock_ageing
|
+-- crm.py                                    # CRM tools (5 tools):
|                                               get_lead_statistics, get_opportunity_analytics,
|                                               get_lead_conversion_rate, get_lead_source_analysis,
|                                               get_sales_funnel
|
+-- hrms.py                                   # HR tools (6 tools, requires HRMS app):
|                                               get_employee_count, get_attendance_summary,
|                                               get_leave_balance, get_payroll_summary,
|                                               get_department_wise_salary, get_employee_turnover
|
+-- idp.py                                    # Document processing tools (3 tools):
|                                               extract_document_data, create_from_extracted_data,
|                                               compare_document_with_record
|
+-- session.py                                # Session context tools (2 tools):
|                                               set_include_subsidiaries,
|                                               set_target_currency
|
+-- finance/                                  # Finance sub-package (5 modules, 8 tools)
|   +-- common.py                             # Shared finance helpers (primary, date utils)
|   +-- analytics.py                          # Multi-dimensional financial summary
|   +-- gl_analytics.py                       # GL summary with flexible grouping (1 tool)
|   +-- cfo.py                                # CFO dashboard, financial overview,
|   |                                           monthly comparison (3 tools)
|   +-- profitability.py                      # Profitability by customer/item/territory (1 tool)
|   +-- cash_flow.py                          # Payment Entry-based cash flow analysis,
|                                               bank balance (2 tools)
|
+-- reports/                                  # ERPNext Standard Report wrappers (Phase 12B)
|   +-- _base.py                              # Base utilities: run_report(), build_report_response(),
|   |                                           build_financial_filters(), get_fiscal_year_name()
|   +-- finance.py                            # 14 financial report tools:
|   |                                           report_general_ledger, report_accounts_receivable,
|   |                                           report_accounts_receivable_summary,
|   |                                           report_accounts_payable,
|   |                                           report_accounts_payable_summary,
|   |                                           report_trial_balance, report_profit_and_loss,
|   |                                           report_balance_sheet, report_cash_flow,
|   |                                           report_consolidated_financial_statement,
|   |                                           report_consolidated_trial_balance,
|   |                                           report_account_balance, report_financial_ratios,
|   |                                           report_budget_variance
|   +-- sales.py                              # 2 sales report tools:
|   |                                           report_sales_register,
|   |                                           report_item_wise_sales_register
|   +-- purchase.py                           # 2 purchase report tools:
|   |                                           report_purchase_register,
|   |                                           report_item_wise_purchase_register
|   +-- stock.py                              # 3 stock report tools:
|                                               report_stock_ledger, report_stock_balance,
|                                               report_stock_ageing
|
+-- operations/                               # CRUD operations (3 modules)
|   +-- create.py                             # Create ERPNext records (with confirmation)
|   +-- search.py                             # Search/find ERPNext records
|   +-- update.py                             # Update ERPNext records (with confirmation)
|
+-- predictive/                               # Forecasting and anomaly detection (5 modules, 6 tools)
    +-- sales_forecast.py                     # Revenue forecasting (Holt-Winters, exponential
    |                                           smoothing, trend analysis, confidence intervals)
    +-- demand_forecast.py                    # Item demand forecasting
    +-- cash_flow_forecast.py                 # Cash flow projection
    +-- anomaly_detection.py                  # Statistical anomaly detection (z-score, IQR)
    +-- trends.py                             # Trend analysis: linear regression, growth rates,
                                                moving averages, seasonality detection (1 tool)
```

**Tool loading order**: Tools are loaded lazily on first access via `_ensure_tools_loaded()` in `registry.py`. ERPNext tools load only if ERPNext is installed; HRMS tools load only if HRMS is installed. External plugin tools are discovered via the `ai_chatbot_tool_modules` Frappe hook.

---

### IDP (Intelligent Document Processing)

The IDP subsystem extracts structured data from uploaded documents (invoices, purchase orders, receipts) using LLM Vision and creates ERPNext records from the extracted data.

```
ai_chatbot/idp/
+-- __init__.py
+-- schema.py                                 # DocType field schema definitions for
|                                               extraction targets (Sales Invoice, Purchase
|                                               Invoice, etc.)
+-- validators.py                             # Extracted data validation: required fields,
|                                               link resolution, business rule checks
+-- mapper.py                                 # Maps extracted data to ERPNext document
|                                               structure; handles item defaults, missing
|                                               masters detection
+-- comparison.py                             # Compares extracted document data against
|                                               existing ERPNext records (line-by-line diff)
+-- extractors/
    +-- __init__.py
    +-- base.py                               # Base extractor: file reading, LLM Vision
    |                                           API calls, response parsing
    +-- pdf_extractor.py                      # PDF-specific extraction (requires pypdf)
    +-- excel_extractor.py                    # Excel extraction (requires openpyxl)
    +-- docx_extractor.py                     # Word document extraction (requires python-docx)
```

---

### Data Processing Utilities

Shared data manipulation, aggregation, and visualization helpers used across multiple tool modules.

```
ai_chatbot/data/
+-- __init__.py
+-- grouping.py                               # Multi-dimensional grouping engine:
|                                               7+ dimension support (company, territory,
|                                               customer_group, customer, item_group, item,
|                                               brand, project, cost_center, department,
|                                               time period). Uses frappe.qb exclusively.
|
+-- analytics.py                              # Generic aggregation helpers for common
|                                               patterns (sum, count, average, growth %)
|
+-- charts.py                                 # ECharts option builders: build_bar_chart,
|                                               build_line_chart, build_pie_chart, etc.
|                                               Returns complete option dicts that the
|                                               frontend passes to echarts.setOption().
|
+-- forecast_charts.py                        # Specialized chart builders: build_forecast_chart
|                                               (confidence bands), build_trend_analysis_chart
|                                               (regression + MA overlay),
|                                               build_cash_flow_forecast_chart (multi-series)
|
+-- currency.py                               # Multi-currency utilities: exchange rate
|                                               lookup via ERPNext, currency formatting,
|                                               amount conversion helpers
|
+-- forecasting.py                            # Statistical forecasting engine: SMA, EMA,
|                                               Holt's double exponential smoothing,
|                                               Holt-Winters triple exponential smoothing,
|                                               linear regression, trend analysis,
|                                               seasonality detection, confidence intervals
|
+-- operations.py                             # CRUD operation helpers: document creation,
|                                               validation, and update utilities
|
+-- queries.py                                # Reusable query fragments and query builder
|                                               helpers for common ERPNext patterns
|
+-- validators.py                             # Input validation: date ranges, company names,
                                                numeric bounds, parameter sanitization
```

---

### Automation

Scheduled report execution and output formatting.

```
ai_chatbot/automation/
+-- __init__.py
+-- scheduled_reports.py                      # Scheduler entry point (cron every 15 min):
|                                               run_scheduled_reports() checks the master
|                                               toggle, finds due reports, enqueues each
|                                               as a background job.
|
+-- executor.py                               # Single report executor: runs the AI prompt
|                                               against the configured company, collects
|                                               tool results, formats output.
|
+-- formatters.py                             # HTML/PDF formatters: markdown-to-HTML
                                                conversion, table styling, ECharts-to-SVG
                                                rendering (for PDF), email template assembly.
                                                Shared by both scheduled reports and the
                                                PDF export API.
```

---

### Utilities

```
ai_chatbot/utils/
+-- ai_providers.py                           # AI provider integration:
                                                OpenAIProvider, ClaudeProvider, GeminiProvider
                                                classes with chat_completion() and
                                                chat_completion_stream() methods.
                                                get_ai_provider() factory reads Chatbot
                                                Settings and returns the configured provider.
                                                Default models: OpenAI=gpt-4o,
                                                Claude=claude-sonnet-4-5-20250929,
                                                Gemini=gemini-2.5-flash.
                                                Includes error classification for rate limits,
                                                quota, and auth failures.
```

---

### Static Assets and Templates

```
ai_chatbot/public/
+-- frontend/                                 # Built Vue app output (generated by vite build).
|                                               Contains index.html, assets/*.js, assets/*.css.
|                                               Served by Frappe at /ai-chatbot/.
+-- images/
    +-- logo.svg                              # App logo for Frappe desktop icon

ai_chatbot/desktop_icon/
+-- chatbot.json                           # Desktop icon configuration

ai_chatbot/workspace_sidebar/
+-- chatbot.json                           # Workspace sidebar navigation entry

ai_chatbot/templates/                         # Jinja templates (reserved for future use)
```

---

## Documentation

```
docs/
+-- PROJECT_OVERVIEW.md                       # Technical overview with Mermaid diagrams
+-- PROJECT_STRUCTURE.md                      # This file
+-- API.md                                    # API endpoint reference (15 endpoints)
+-- TOOLS_REFERENCE.md                        # Complete reference for all 71 tools
+-- SAMPLE_USER_PROMPT.md                     # Sample prompts with expected output
+-- AT_MENTION_GUIDE.md                       # @mention system usage guide
+-- ENHANCEMENT_ROADMAP.md                    # Future phases roadmap
```

---

## Key Patterns

### Tool Registration Pattern

Every tool is a decorated Python function. The `@register_tool` decorator registers the function in the global `_TOOL_REGISTRY` dict at import time. The registry builds OpenAI function calling schemas and handles execution with DocType permission checks.

```python
from ai_chatbot.tools.registry import register_tool

@register_tool(
    name="get_sales_analytics",
    category="selling",
    description="Get sales revenue, orders, and growth trends",
    parameters={
        "from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
        "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
        "company": {"type": "string", "description": "Company name"},
    },
    doctypes=["Sales Invoice"],
)
def get_sales_analytics(from_date=None, to_date=None, company=None):
    """Query Sales Invoices and return analytics with chart data."""
    ...
```

- `name` must be unique across all tools.
- `category` maps to a toggle in Chatbot Settings (e.g., `"selling"` -> `enable_sales_tools`).
- `parameters` becomes the OpenAI function calling schema sent to the AI provider.
- `doctypes` triggers Frappe permission checks before execution.

### Multi-Company Query Pattern

Tools use `get_company_filter()` from `session_context.py` instead of raw `get_default_company()`. This function is session-aware: when `include_subsidiaries` is enabled, it returns a list of companies (parent + children); otherwise a single company string.

```python
from ai_chatbot.core.session_context import get_company_filter

company = get_company_filter(company)
if isinstance(company, list):
    query = query.where(dt.company.isin(company))
else:
    query = query.where(dt.company == company)
```

### ECharts Response Pattern

Tools return structured results with an optional `echart_option` dict. The frontend detects this field and renders the chart using Apache ECharts. The AI never sees the chart data (it is stripped by `token_optimizer.py` before sending to the LLM).

```python
return {
    "data": [...],
    "echart_option": {
        "title": {"text": "Monthly Revenue"},
        "xAxis": {"type": "category", "data": [...]},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [...]}],
    },
    "company": company,
    "currency": currency,
}
```

Additional optional response keys:
- `bi_cards` -- rendered as KPI metric tiles by `BiCards.vue`.
- `hierarchical_table` -- rendered as expandable grouped tables by `HierarchicalTable.vue`.

### Plugin System

External Frappe apps can register additional chatbot tools without modifying the AI Chatbot codebase. They declare tool modules via a Frappe hook:

```python
# In external app's hooks.py (or __init__.py):
ai_chatbot_tool_modules = ["my_app.chatbot_tools.manufacturing"]
```

The module is imported by `_ensure_tools_loaded()` in the registry, which triggers the `@register_tool` decorators in that module. External apps can also register new tool categories:

```python
from ai_chatbot.tools.registry import register_tool_category

register_tool_category("manufacturing", settings_field=None)  # Always enabled
```

### Streaming Pattern

The streaming flow uses Frappe's realtime infrastructure (Redis Pub/Sub -> Socket.IO):

1. Frontend calls `send_message(stream=True)`.
2. Backend saves the user message, generates a `stream_id`, enqueues a background job, and returns immediately.
3. The background job calls `provider.chat_completion_stream()` and publishes tokens via `frappe.publish_realtime("ai_chat_token", ...)`.
4. Frontend's `useStreaming.js` composable listens for these events and appends tokens to the message display in real time.
5. Tool call events (`ai_chat_tool_call`, `ai_chat_tool_result`) and process steps (`ai_chat_process_step`) are also published for UI feedback.
6. When complete, `ai_chat_stream_end` is published with the full content and token count.

### Multi-Agent Orchestration Pattern

For complex queries (comparisons, cross-domain analysis), the orchestrator pipeline runs:

1. **Classifier** (`classifier.py`): Determines if the query needs multi-agent handling.
2. **Planner** (`planner.py`): Decomposes the query into ordered steps.
3. **Analyst** (`analyst.py`): Executes each step, calling the appropriate tools.
4. **Synthesis**: The AI produces a unified response from all collected data.

If more than 50% of data steps fail, the system falls back to the standard single-pass flow.

---

## Build Pipeline

The frontend build pipeline produces optimized static assets that Frappe serves:

```
1. Developer runs:
   cd frontend && npm run build

2. Vite compiles Vue 3 SPA:
   - Resolves imports, compiles .vue SFCs
   - Applies Tailwind CSS (purges unused classes)
   - Splits output into manual chunks:
     * vue-vendor (vue + vue-router)
     * markdown (marked + highlight.js)
     * icons (lucide-vue-next)
     * echarts (apache echarts)
   - Output goes to: ai_chatbot/public/frontend/

3. Frappe bundles:
   bench build --app ai_chatbot
   - Copies ai_chatbot/public/ into the site's assets directory
   - Registers the /ai-chatbot/ route

4. In production:
   Frappe's nginx config serves /assets/ai_chatbot/frontend/
   as the SPA at /ai-chatbot/
```

Vite configuration highlights (`vite.config.js`):
- `outDir: '../ai_chatbot/public/frontend'` -- builds directly into the Frappe static directory.
- `emptyOutDir: true` -- cleans previous builds.
- `manualChunks` -- splits large dependencies for better caching.
- `fs.allow` -- permits reading `common_site_config.json` for Socket.IO port discovery.

---

## Database Schema

All DocTypes belong to the "Chatbot" module. Frappe manages table creation, migrations, and indexing automatically from the JSON schema definitions.

### Chatbot Settings (Single DocType)

One global record. Stores all configuration for the AI Chatbot instance.

| Field | Type | Description |
|---|---|---|
| `ai_provider` | Select | Active AI provider (OpenAI / Claude / Gemini) |
| `api_key` | Data | API key for the selected provider (stored encrypted) |
| `model` | Data | Model name override (defaults per provider) |
| `temperature` | Float | Response randomness (0.0-1.0, default 0.7) |
| `max_tokens` | Int | Max tokens per response (default 4000) |
| `max_context_messages` | Int | Conversation history limit (default 20) |
| `enable_crm_tools` | Check | Toggle CRM tool category |
| `enable_sales_tools` | Check | Toggle Sales tool category |
| `enable_purchase_tools` | Check | Toggle Purchase tool category |
| `enable_finance_tools` | Check | Toggle Finance tool category |
| `enable_inventory_tools` | Check | Toggle Inventory tool category |
| `enable_hrms_tools` | Check | Toggle HRMS tool category |
| `enable_idp_tools` | Check | Toggle IDP tools |
| `enable_strict_idp_validation` | Check | Strict validation before record creation |
| `auto_create_idp_masters` | Check | Auto-create missing master records |
| `enable_predictive_tools` | Check | Toggle forecasting and anomaly detection |
| `enable_write_operations` | Check | Toggle CRUD operations |
| `enable_agent_orchestration` | Check | Toggle multi-agent pipeline |
| `default_query_limit` | Int | Default row limit for queries |
| `default_top_n_limit` | Int | Default top-N limit |
| `max_query_limit` | Int | Hard cap on query results |
| `ai_persona` | Data | Custom AI persona description |
| `response_language` | Select | Global response language |
| `custom_system_prompt` | Text | Custom system prompt addition |
| `custom_instructions` | Text | Additional behavioral instructions |
| `enable_streaming` | Check | Toggle streaming mode |
| `enable_automation` | Check | Master toggle for scheduled reports |

### Chatbot Conversation

Naming: `CHAT-#####` (auto-incrementing).

| Field | Type | Description |
|---|---|---|
| `title` | Data | Conversation title (auto-generated from first message) |
| `user` | Link (User) | Owning user |
| `ai_provider` | Select | AI provider for this conversation |
| `model` | Data | Model used |
| `status` | Select | Active / Archived |
| `created_at` | Datetime | Creation timestamp |
| `updated_at` | Datetime | Last activity timestamp |
| `message_count` | Int | Total messages in conversation |
| `total_tokens` | Int | Cumulative token usage |
| `session_context` | JSON | Per-conversation session state (include_subsidiaries, target_currency, response_language) |

### Chatbot Message

Naming: `MSG-#####` (auto-incrementing).

| Field | Type | Description |
|---|---|---|
| `conversation` | Link (Chatbot Conversation) | Parent conversation |
| `role` | Select | user / assistant / system / tool |
| `content` | Long Text | Message text content |
| `timestamp` | Datetime | Message timestamp |
| `tokens_used` | Int | Tokens consumed by this response |
| `tool_calls` | JSON | Tool calls made by the AI (function names + arguments) |
| `tool_results` | JSON | Results returned by tool execution |
| `attachments` | JSON | File attachment metadata (file_url, mime_type, base64) |

### Chatbot Token Usage

Naming: auto-increment (integer).

| Field | Type | Description |
|---|---|---|
| `user` | Link (User) | User who made the request |
| `conversation` | Link (Chatbot Conversation) | Related conversation |
| `provider` | Data | AI provider name |
| `model` | Data | Model name |
| `prompt_tokens` | Int | Input tokens |
| `completion_tokens` | Int | Output tokens |
| `total_tokens` | Int | Total tokens (prompt + completion) |
| `estimated_cost` | Currency | Estimated cost in USD |
| `date` | Date | Date of usage |

### Chatbot Scheduled Report

Naming: `CSR-#####` (auto-incrementing).

| Field | Type | Description |
|---|---|---|
| `report_name` | Data | Human-readable report name |
| `prompt` | Text | AI prompt to execute |
| `company` | Link (Company) | Company context for the report |
| `format` | Select | Output format (Email HTML / PDF / Both) |
| `enabled` | Check | Whether the report is active |
| `schedule` | Select | Frequency (Daily / Weekly / Monthly / Custom Cron) |
| `time_of_day` | Time | Execution time (server timezone) |
| `day_of_week` | Select | For weekly schedule |
| `day_of_month` | Int | For monthly schedule (1-28) |
| `cron_expression` | Data | Custom cron expression |
| `recipients` | Table (Chatbot Report Recipient) | Email recipient list |
| `sender` | Link (Email Account) | Sender email account |
| `last_run` | Datetime | Last execution timestamp |
| `last_run_status` | Data | Success / Error |
| `run_count` | Int | Total execution count |
| `last_error` | Text | Last error message |

---

## Configuration Files

### Python Configuration

| File | Purpose |
|---|---|
| `pyproject.toml` | Project metadata, Python >=3.10 requirement, dependencies (`twilio==8.5.0`), optional IDP dependencies (`pypdf`, `openpyxl`, `python-docx`), Ruff linter config (110 char lines, tab indent, double quotes, rules: F, E, W, I, UP, B, RUF) |
| `setup.py` / `setup.cfg` | Legacy package setup for Frappe bench compatibility |
| `.pre-commit-config.yaml` | Pre-commit hooks: trailing whitespace, merge conflict check, AST check, JSON/TOML/YAML validation, ruff import sorting, ruff linting, ruff formatting, prettier (JS/Vue/SCSS), eslint (JS) |

### JavaScript / Frontend Configuration

| File | Purpose |
|---|---|
| `frontend/vite.config.js` | Vite build config: `@` path alias to `src/`, manual chunks (vue-vendor, markdown, icons, echarts), output to `../ai_chatbot/public/frontend`, `fs.allow` for Socket.IO config reading |
| `frontend/tailwind.config.js` | Tailwind CSS: `darkMode: 'class'`, custom primary color palette (sky blue), custom animations (fade-in, slide-up, pulse-slow, recording) |
| `frontend/postcss.config.js` | PostCSS plugins: tailwindcss + autoprefixer |
| `frontend/package.json` | Dependencies: vue 3.4, vue-router 4.2, echarts 6, marked 11, highlight.js 11, lucide-vue-next, socket.io-client 4.8. Dev: vite 5, @vitejs/plugin-vue, tailwindcss 3.4 |

### Editor / Linter Configuration

| File | Purpose |
|---|---|
| `.editorconfig` | Root config: LF line endings, UTF-8 charset, tab indentation for Python/JS/Vue/CSS, space indentation for JSON (1 space), trim trailing whitespace |
| `.eslintrc` | ESLint: `eslint:recommended`, ES2022, source modules, Frappe globals (frappe, cur_frm, __, $, etc.), relaxed rules for indentation/quotes/semicolons |

---

## Request Lifecycle

A typical user message flows through the system as follows:

```
1. User types message in ChatInput.vue
       |
2. ChatAPI.sendMessage() -> POST /api/method/ai_chatbot.api.chat.send_message
       |
3. [stream=true?]
   |-- YES --> streaming.send_message_streaming()
   |              |
   |              +-- Save user message
   |              +-- Enqueue background job (_run_streaming_job)
   |              +-- Return {stream_id} immediately
   |              |
   |              +-- (Background job):
   |                    +-- Build system prompt (prompts.py)
   |                    +-- Optimize history (token_optimizer.py)
   |                    +-- Check should_orchestrate() -> multi-agent or standard
   |                    +-- Stream tokens via frappe.publish_realtime
   |                    +-- Execute tool calls if needed (registry.execute_tool)
   |                    +-- Save assistant message
   |                    +-- Publish ai_chat_stream_end
   |
   |-- NO --> chat.send_message() (synchronous)
                 |
                 +-- Save user message
                 +-- Build system prompt
                 +-- Optimize history
                 +-- Check should_orchestrate()
                 +-- provider.chat_completion() (up to 5 tool rounds)
                 +-- Save assistant message
                 +-- Track token usage
                 +-- Return {message, tokens_used}

4. Frontend receives response:
   - Non-streaming: renders complete message
   - Streaming: appends tokens progressively, renders charts on stream_end

5. ChatMessage.vue renders:
   - Markdown content (via markdown.js)
   - Code blocks with syntax highlighting (highlight.js)
   - ECharts charts (via ChartMessage.vue -> EChartRenderer.vue)
   - BI cards (BiCards.vue) and hierarchical tables (HierarchicalTable.vue)
```

---

*This document reflects the AI Chatbot through Phase 19. For the planned enhancement roadmap, see `docs/ENHANCEMENT_ROADMAP.md`.*
