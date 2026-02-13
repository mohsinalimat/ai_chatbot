# CLAUDE.md — AI Chatbot for Frappe/ERPNext

## Project Overview

AI Chatbot is a Frappe framework app that provides a modern chat interface with OpenAI and Claude integration and ERPNext business intelligence tools. Built with a Python backend (Frappe) and Vue 3 frontend (Vite + Tailwind CSS).

## Key Commands

```bash
# Frontend
cd frontend && npm install        # Install frontend dependencies
cd frontend && npm run dev        # Dev server at http://localhost:8080
cd frontend && npm run build      # Build to ai_chatbot/public/frontend

# Backend
bench start                       # Start Frappe dev server
bench --site <site> run-tests ai_chatbot  # Run backend tests

# Linting (via pre-commit)
pre-commit run --all-files        # Run all linters
ruff check .                      # Python lint only
ruff format .                     # Python format only
```

## Architecture

```
ai_chatbot/           # Python package (backend)
├── api/chat.py       # Chat API endpoints (@frappe.whitelist)
├── chatbot/doctype/  # Frappe DocTypes (settings, conversation, message)
├── tools/            # ERPNext business tools (base, crm, selling, buying, stock, account, hrms)
├── utils/ai_providers.py  # OpenAI & Claude API integration
└── public/frontend/  # Built frontend assets (generated)

frontend/             # Vue 3 SPA
├── src/components/   # Sidebar, ChatHeader, ChatMessage, ChatInput, TypingIndicator
├── src/pages/        # ChatView (main interface)
├── src/utils/api.js  # API client (ChatAPI singleton with CSRF)
└── vite.config.js    # Build config with manual chunks
```

## Code Conventions

- **Python:** Tabs for indentation, 110 char line length, double quotes, Python 3.14+, type hints
- **Linter:** Ruff with rules F, E, W, I, UP, B, RUF
- **JavaScript/Vue:** Vue 3 Composition API (`<script setup>`), Tailwind CSS for styling
- **JS Lint:** ESLint (recommended) + Prettier
- **Editor:** Tabs, LF line endings, UTF-8 (see .editorconfig)
- **API pattern:** `@frappe.whitelist()` decorators, frappe ORM for DB access
- **Error handling:** try/except with `frappe.log_error()`
- **Frontend state:** `ref()` and `computed()` reactivity, async/await for API calls

## AI Providers

OpenAI (GPT-4o, GPT-4-Turbo, GPT-3.5-Turbo) and Anthropic Claude (Opus 4.5, Sonnet 4.5, Haiku 4.5). Provider configuration is in Chatbot Settings DocType. API keys are stored encrypted via Frappe's Password field type.

## Testing

Backend tests use Frappe's test framework, colocated with DocTypes. Frontend tests are not yet implemented.

## Dependencies

- **Python:** frappe, twilio==8.5.0, requests, openai/anthropic (runtime)
- **Frontend:** vue 3, vue-router, marked, highlight.js, lucide-vue-next, tailwindcss, echarts (Apache ECharts for all chart/visualization rendering)

## Multi-Company & Multi-Currency Rules

- Every tool querying transactional data MUST accept a `company` parameter, defaulting to `frappe.defaults.get_user_default("Company")`
- Monetary aggregations MUST use `base_*` fields (`base_grand_total`, `base_paid_amount`) for company-currency amounts
- Tool responses MUST include `company` and `currency` fields
- Use `frappe.qb` (Query Builder) or `frappe.get_all` — never raw SQL with string interpolation
- RAG vector store collections are namespaced per company for data isolation

## Enhancement Roadmap (Planned Phases)

See `docs/ENHANCEMENT_ROADMAP.md` for the full phase-wise plan.

1. **Foundation** — core framework, data layer, multi-company/currency, security fixes *(done)*
2. **Streaming (Frappe Realtime)** — token-by-token streaming via `frappe.publish_realtime` (Socket.IO/WebSocket)
3. **Data operations (CRUD)** — create/update/delete ERPNext records via chat
4. **Finance tools** — budget, ratios, profitability, receivables/payables, cash flow + ECharts
5. **HRMS & CRM** — complete HRMS tools, expanded CRM analytics
6. **Agentic RAG** — ChromaDB vector store + multi-agent orchestration + memory system (combined)
7. **IDP** — document extraction (LLM Vision), validation, ERPNext record creation
8. **Predictive Analytics** — forecasting, anomaly detection (statistical first, ML later)
9. **Automation** — alerts, scheduled reports, WhatsApp/Slack notifications

Charts use Apache ECharts (npm: echarts). Backend returns `echart_option` objects, frontend renders with ECharts.
