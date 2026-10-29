# WealthDesk — populated portfolio demo

## Start the latest version

Extract the ZIP and open its `portfolio-dashboard` folder.

**Windows:** double-click `START_WEALTHDESK.bat`.

**Any platform:**

```bash
python launch.py
```

The launcher opens the dashboard on a free port beginning at **8082**, avoiding an older app still running on 8080. Keep its terminal open. Python 3.10+ is sufficient; no packages need installing.

For an explicit port, use `python app.py --port 8082` and open http://127.0.0.1:8082.

## Included fictional profiles

| Demo person | Role | Available content |
|---|---|---|
| Anita Mehta | Business owner | Mehta Manufacturing; three personal and three business portfolios; family recipients, proposal and sale opportunity |
| James Carter | Business owner | Riverbend Foods; personal/business holdings and acquisition signals |
| Maya Rao | Business owner | Oak & Thread Retail; personal/business holdings and tax/retirement signals |
| Sarah Williams | Wealth advisor | All three authorized clients, investment proposals, professional directory, alerts and client inbox |
| Priya Shah | CA | Authorized account views and tax/quality-of-earnings alerts |
| David Chen | Broker | Business portfolios and deal/valuation alerts |
| Michael Reed | Commercial RM | Business liquidity/assets and commercial transition alerts |

Choose people from the workspace dropdown. All included people, companies, balances, holdings, offers and activity are **fictional demo data**, labeled in the header. No real accounts or model performance are represented.

## Multiple portfolios

Click **+ Create portfolio** in the overview or an account screen. Enter a unique name, choose Personal or Business, and optionally enter opening cash. Each named portfolio has its own cash ledger, holdings, proposals, transactions and chat context.

Anita starts with:

- Personal: Everyday personal; Retirement & long-term wealth; Children’s education.
- Business: Business operations; Expansion & growth; Business treasury reserve.

Use **Open portfolio** on a card or the named-portfolio dropdown to switch. Overview totals aggregate all portfolios of each type; the advisor's client book does the same for each authorized owner. Personal/business access permissions apply to all portfolios of that type in the selected household.

Family transfers let the owner choose the personal source portfolio. Investment forms let the owner/advisor choose a specific portfolio. The sale form lets the owner choose the business portfolio and the personal destination for net proceeds. A completed closing is credited once per business portfolio; another business portfolio can have its own closing.

## Ready-to-demonstrate actions

- Owner: inspect populated portfolios, add another portfolio, record an investment, transfer to a spouse/child, or review the advisor's $25,000 sample proposal.
- Business sale: inspect the fictional 70% offer, record a closing into a selected personal portfolio, then record or approve a reinvestment.
- Wealth advisor: switch clients, propose investments, view professional contacts and respond to the example meeting request.
- CA, broker or commercial RM: inspect authorized business/client information and source-trigger alerts relevant to that role.
- **AI chat:** click the floating button at the bottom-right of any client page, then choose a named portfolio. The pop-up stays available while you navigate; there is no separate chat page in the sidebar. Account summaries use that portfolio's recorded values. Live AI needs the operator's OPENAI_API_KEY and OPENAI_MODEL; no credentials or fabricated LLM response are included.
- **Wealth Advisor:** message or request a preferred meeting time about a selected portfolio. The advisor receives an in-app notification and can reply.

## Persistence and existing data

Data is saved in `portfolio.sqlite3`. The demo seed is idempotent: restarting does not reset balances, duplicate the sample clients, or remove portfolios you created. Existing default personal/business records are retained and upgraded to named portfolios.

To start a separate empty database without adding demo records, set `PORTFOLIO_DEMO=0` and `PORTFOLIO_DB` to a new database path before launching. Disabling seeding does not delete demo records already present in an existing database. Do not delete a database containing records you want to keep.

## Local prototype boundaries

The role selector is for a one-computer walkthrough, not production authentication. Transfers, investments, proposals and closings update this local ledger; they do not execute banking transactions, securities trades, emails or calendar bookings. Holdings use recorded values, not live prices. Selling a business interest does not automatically liquidate/revalue individual corporate assets, and account totals are not a consolidated business-ownership valuation.

All source-document A/B/C/D triggers remain available. Alerts flag a possible transition requiring confirmation and go only to assigned active stakeholders with the needed account scope. Chat has no transaction tools; with a configured external AI service, the client confirms sharing selected-account context. AI requests use store:false, subject to the provider's retention/usage terms.

## Verification

```bash
python -m unittest discover -s tests -v
node --check web/app.js
```

Tests cover the existing portfolio flow plus multiple named portfolios, separate balances, selected-source family transfers, selected-destination sale proceeds, scoped chat/advisor access, duplicate-name checks and idempotent demo seeding. Temporary test fixtures are isolated from the saved demonstration accounts. Live AI calls are mocked in tests because no credentials were supplied.

Browser checks confirmed populated owner/advisor screens and creation of an additional personal and business portfolio with separate balances.

## Interface update

The client sidebar uses text-only navigation and labels the advisor page Wealth Advisor. AI chat is a compact floating pop-up available on every client page. It preserves per-portfolio history and unsent drafts, follows the selected personal/business portfolio when navigating, and includes a shortcut to Wealth Advisor. The dashboard uses white cards, a soft gray canvas, blue accents and light overlays.

Browser checks verified opening the pop-up, receiving an account-summary response within it, navigating to a business portfolio while it stays open, and opening the Wealth Advisor page from the pop-up. No live external AI request was made.
