# Org context — Summit Gear AG (synthetic org)

Written by the Admin. Facts about this org that field metadata does not show: codes, scales, systems, teams and conventions. Synthetic: invented for the Day 6 experiment, matching the synthetic training set. The partial version (glossary only) is org_context_synthetic_glossary.md.

## Codes and grades

- **Customer and contact grades A–D**: value band from the last 12 months' net revenue and the engagement score, recalculated every quarter. A = top 10% of accounts, B = next 20%, C = next 40%, D = the rest and new customers. A is best.
- **Priority tiers 1–3** on accounts: Tier 1 = strategic accounts with a named account manager, Tier 2 = managed by the inside sales team, Tier 3 = webshop only.
- **Operations queues Alpha, Beta, Gamma, Delta**: work queues of the operations team. Alpha = order exceptions (stock, pricing, address), Beta = returns and repairs, Gamma = gear loans and rentals, Delta = data quality fixes.
- **Case types A–D**: Type A = product defect, Type B = delivery or logistics problem, Type C = order or invoice question, Type D = product advice or usage question.
- **Support levels L1, L2, L3**: L1 = first-line customer service, L2 = product specialists, L3 = engineering at the supplier. Specialist = a named expert outside the levels (e.g. avalanche safety equipment).
- **Support tiers Basic, Standard, Premium, Enterprise** (set per account, can be overridden per contact). Resolution targets in business hours (Monday–Friday, 08:00–18:00 Zurich time): Basic 48, Standard 24, Premium 8, Enterprise 4. First response target: 4 business hours for every tier.
- **Discount tiers Standard, Silver, Gold, Platinum**: 0%, 5%, 10%, 15% off list price. Discount rates are stored as percentage numbers: 15 means 15%.
- **Sponsorship levels Bronze, Silver, Gold, Athlete Partner**: Bronze = product discount, Silver = discount and logo on our website, Gold = co-branded gear, Athlete Partner = individual athletes with a contract.
- **Data residency regions EU, CH, US, APAC**: the data centre region where the customer's personal data must be stored.

## Scores and scales

- **Engagement score**: 0–100, calculated every night by the marketing automation platform from email clicks, webshop visits and event attendance in the last 12 months. Higher = more engaged. Bands: 70 and above high, 30–69 medium, below 30 low.
- **Churn risk score**: 0–100, calculated monthly by the finance analytics model from order frequency and open complaints. Higher = more likely to stop buying.
- **Strategic value score**: 1–5, set by the sales leadership in the yearly account planning. 5 = most strategic.
- **CSAT (customer satisfaction)**: 1–5 per case, from the survey sent when a case closes; 1–10 for the yearly account survey.
- **NPS (Net Promoter Score)** segments: Promoter 9–10, Passive 7–8, Detractor 0–6, from the quarterly survey.
- **MEDDIC score**: 0–6, one point per MEDDIC element confirmed (Metrics, Economic buyer, Decision criteria, Decision process, Identify pain, Champion).

## Abbreviations

ACV = annual contract value · ARR = annual recurring revenue · TCV = total contract value · CLV = customer lifetime value · RFM = recency, frequency, monetary value · EBR = executive business review (yearly, with Tier 1 accounts) · QBR = quarterly business review (internal sales forecast meeting) · ICP = ideal customer profile (guiding companies and mountain schools with 10+ guides) · TTR = time to resolution · DNC = do not call · IFMGA = International Federation of Mountain Guides Associations · VIES = VAT Information Exchange System of the EU · SLA = service level agreement

## Systems

- **ERP**: orders, invoices, stock and agreed customer prices. Customer-specific prices are price agreements in the ERP, referenced as PA-YYYY-NNNN. Salesforce Quotes are not used.
- **Webshop**: B2C and B2B online orders; the e-commerce integration writes confirmed orders and purchase dates to Salesforce.
- **Marketing automation platform**: newsletters, engagement score, consent records. Event invitations and attendance are Salesforce Campaigns; attendees are Campaign Members.
- **Survey platform**: sends CSAT and NPS surveys and writes the answers back to Salesforce.
- **Customer portal** (Salesforce Experience Cloud since the 2023 platform migration): customers open cases, submit certifications and see orders.
- **Jira**: product defects are tracked in the Jira project PQ (product quality); a defect reference looks like PQ-1234.
- **Migrations**: 2021, accounts and contacts moved from the old on-premise CRM ("SummitBase"); 2022, opportunity history moved; 2023, the old helpdesk tool ("Kestrel Desk") and the old customer portal were replaced by Salesforce Service Cloud and Experience Cloud. Legacy codes and IDs from these systems are kept read-only for lookups in the archive; nothing new is written to them.

## Teams

- **Account managers**: own Tier 1 and Tier 2 accounts; verify certifications and run fitting calls with guides and athletes.
- **Inside sales**: Tier 2 accounts, inbound leads, pilots (equipment lent to a prospect for 4–6 weeks before a volume order).
- **Deal desk**: approves non-standard discounts and pricing; assesses deal risk.
- **Customer service** (L1) and **product specialists** (L2): work cases. **Support operations** maintains queues and routing.
- **Operations team**: order exceptions, returns, repairs, gear loans; works from the Alpha–Delta queues.
- **Loyalty team**: loyalty points and the ambassador programme (customers who promote our gear on social media and get early access to new products).
- **Legal and compliance**: consent, data residency, health data. Health disclosures for guided expeditions (medical conditions a participant declares) are not yet approved for storage in Salesforce.

## Conventions

- Case channel: the standard Case Origin field holds the channel the case arrived through. Custom channel fields add detail that Origin does not have (e.g. which partner submitted it).
- Opportunity source: the standard Lead Source field is filled at lead conversion; it is the source of record.
- Consent: the standard Email Opt Out and Do Not Call fields are the source of record for email and phone consent; the marketing automation platform syncs them.
- SLA: Entitlements and Milestones are not used. SLA targets come from the account's support tier; deadlines are calculated by a flow when the case is created.
- Internal tags: short keywords that account managers add to group contacts for list views and campaigns, e.g. "trade-fair-2025", "beta-tester". No fixed list.
- Amounts are in CHF unless the field name says otherwise. Measurements are metric (cm, kg); shoe sizes are EU sizes.
