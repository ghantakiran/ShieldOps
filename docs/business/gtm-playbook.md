# ShieldOps Go-To-Market Playbook

## Target Customer Profile

### Ideal Customer Profile (ICP)
- **Company Size:** 500-5,000 employees (mid-market)
- **Industry:** FinTech, HealthTech, SaaS, E-commerce
- **Tech Stack:** Kubernetes, AWS/GCP/Azure, microservices (>20 services)
- **Pain Signals:**
  - SRE team of 3-10 engineers handling >50 alerts/day
  - MTTR > 1 hour for P1 incidents
  - Recent major outages (check status pages)
  - Hiring freeze or "do more with less" mandate
  - PCI-DSS, HIPAA, or SOC 2 compliance requirements
- **Budget:** VP Engineering discretionary budget ($50K-$200K/year)

### Decision Makers
| Role | Pain | Message |
|------|------|---------|
| VP Engineering | Team burnout, MTTR too high, can't hire fast enough | "Reduce MTTR 50%+ while your team focuses on building" |
| CISO / Security Lead | Compliance gaps, slow CVE patching | "Continuous compliance, automated patching, full audit trail" |
| SRE Team Lead | Alert fatigue, on-call burnout, manual toil | "Your AI teammate handles the 2am pages" |
| CTO | Innovation velocity, infrastructure reliability | "Turn infrastructure from bottleneck to competitive advantage" |

## Sales Process

### Stage 1: Discovery (Week 1-2)
- **Source:** Network referrals, conference leads, inbound (content/SEO)
- **Qualification:** BANT (Budget, Authority, Need, Timeline)
- **Discovery Call:** 30 min — understand their stack, pain points, metrics
- **Demo:** 45 min — live agent running in simulated environment
- **Output:** Technical feasibility assessment, champion identified

### Stage 2: POC (Week 3-6)
- **Paid POC:** $5K for 30 days (credited if they convert)
- **Setup:** Deploy agents in their staging/dev environment
- **Success Metrics:** Pre-defined KPIs (MTTR reduction, auto-resolution rate)
- **Cadence:** Weekly check-in calls, Slack channel for real-time support
- **Output:** POC results report with quantified ROI

### Stage 3: Negotiation (Week 7-10)
- **Procurement Blockers:**
  - Security review → Provide SOC 2 report, pen test results
  - Legal → Standard MSA, DPA ready
  - Budget → ROI calculator showing payback < 6 months
- **Contract:** Annual commitment with monthly billing
- **Discount:** 15% for annual prepay

### Stage 4: Onboarding (Week 11-14)
- **Dedicated CSM** for Professional/Enterprise tiers
- **Shadow mode:** 2 weeks of read-only agent operation
- **Gradual rollout:** Dev → Staging → Production (one environment at a time)
- **Training:** 2-hour workshop for SRE team on dashboard and controls

## Marketing Channels

### Content Marketing (Primary)
- Weekly blog posts: "SRE Best Practices", "AI in DevOps", "Kubernetes Troubleshooting"
- SEO targets: "autonomous SRE", "AI incident response", "automated remediation"
- Monthly newsletter to SRE/DevOps audience

### Open Source Strategy
- Release "ShieldOps Agent Toolkit" — simplified investigation agent
- GitHub presence builds developer trust and community
- Funnel: Open source user → SaaS trial → Paid customer

### Events & Speaking
- **Tier 1:** KubeCon, SREcon, AWS re:Invent (speaking slots)
- **Tier 2:** DevOpsDays, local meetups (networking)
- **Webinars:** Monthly "Agent Office Hours" — live Q&A with prospects

### Partnerships
- **Cloud MSPs:** Co-sell with managed service providers
- **Consulting firms:** Deloitte, Accenture (enterprise intros)
- **Observability vendors:** Datadog, Splunk marketplace integrations
- **Cloud marketplaces:** AWS, GCP, Azure marketplace listings

## Pricing

| Tier | Monthly | Hosts | Actions | Support |
|------|---------|-------|---------|---------|
| Starter | $2,000 | 10 | 100/month | Community |
| Professional | $8,000 | 50 | 1,000/month | Email + Slack |
| Enterprise | Custom ($25K+) | Unlimited | Unlimited | Dedicated CSM |

**Expansion Levers:**
- More hosts/clusters managed
- More environments (add GCP, add on-prem)
- Security compliance packs (PCI-DSS, HIPAA, SOC 2)
- Premium playbooks and custom agent development

## Metrics to Track

| Metric | Target (Month 12) | Target (Month 18) |
|--------|-------------------|-------------------|
| ARR | $500K | $2.5M |
| Customers | 15 | 40+ |
| NRR | >100% | >110% |
| CAC Payback | <12 months | <10 months |
| Logo Churn | <5% | <5% |
| Gross Margin | >70% | >75% |
