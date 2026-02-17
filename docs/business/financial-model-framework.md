# ShieldOps Financial Model Framework

## Revenue Model

### Assumptions
| Parameter | Value | Notes |
|-----------|-------|-------|
| Starter MRR | $2,000 | 10 hosts, 100 actions |
| Professional MRR | $8,000 | 50 hosts, 1,000 actions |
| Enterprise MRR | $25,000+ | Unlimited, custom |
| Customer Mix | 30% Starter, 50% Pro, 20% Enterprise | |
| Blended MRR | ~$8,800 | Weighted average |
| Monthly Churn | 2% (Starter), 0.5% (Pro), 0.3% (Enterprise) | |
| Expansion Rate | 5% MoM | Hosts/environments growth |
| POC Conversion | 40% | POC to paid |
| Sales Cycle | 45 days (Starter), 90 days (Pro), 180 days (Enterprise) | |

### Revenue Projections
| Month | Customers | MRR | ARR |
|-------|-----------|-----|-----|
| 6 | 3 (design partners) | $0 | $0 |
| 9 | 8 | $42K | $500K |
| 12 | 15 | $95K | $1.1M |
| 15 | 28 | $180K | $2.2M |
| 18 | 42 | $280K | $3.4M |

## Cost Structure

### Headcount (Largest Cost)
| Role | Count (M12) | Count (M18) | Avg Loaded Cost |
|------|-------------|-------------|-----------------|
| Engineering | 6 | 12 | $180K/year |
| Sales | 2 | 5 | $200K/year (base + OTE) |
| Customer Success | 1 | 3 | $130K/year |
| Marketing | 0 | 2 | $160K/year |
| Operations | 1 | 2 | $120K/year |
| **Total** | **10** | **24** | |
| **Annual Cost** | **$1.7M** | **$4.1M** | |

### Infrastructure Costs
| Component | Monthly Cost | % of Revenue |
|-----------|-------------|--------------|
| Cloud compute (K8s, agents) | $15K-$50K | 15-20% |
| LLM API costs (Anthropic/OpenAI) | $5K-$20K | 5-10% |
| Database + Redis + Kafka | $3K-$10K | 3-5% |
| Monitoring (LangSmith, Datadog) | $2K-$5K | 2-3% |
| **Total** | **$25K-$85K** | **25-30%** |

### Target: 70%+ Gross Margin
- Revenue - Infrastructure = Gross Profit
- At $280K MRR: ~$85K infra = 70% gross margin

### Other Costs
| Category | Monthly | Annual |
|----------|---------|--------|
| Office/co-working | $3K | $36K |
| Legal/accounting | $5K | $60K |
| Insurance (cyber + D&O) | $2K | $24K |
| Tools/software | $3K | $36K |
| Travel/conferences | $5K | $60K |
| **Total** | **$18K** | **$216K** |

## Funding & Runway

### Pre-Seed ($500K-1M)
- Runway: 6-9 months (2-3 founders + contractors)
- Burn rate: $60K-$100K/month
- Milestone: 3 design partners, MVP deployed

### Seed ($3-5M)
- Runway: 18-24 months
- Burn rate: $150K-$250K/month (scaling to 10 people)
- Milestone: $500K ARR, 15 customers, Series A ready

### Series A ($10-15M)
- Runway: 24-30 months
- Burn rate: $400K-$600K/month (scaling to 25 people)
- Milestone: $5M ARR, 100+ customers, path to profitability

## Unit Economics Targets

| Metric | Target | How to Calculate |
|--------|--------|-----------------|
| CAC | < $50K | Total S&M spend / new customers |
| LTV | > $150K | Average MRR x gross margin x avg lifetime (months) |
| LTV:CAC | > 3:1 | LTV / CAC |
| CAC Payback | < 12 months | CAC / (MRR x gross margin) |
| NRR | > 110% | (Start MRR + expansion - contraction - churn) / Start MRR |
| Gross Margin | > 70% | (Revenue - COGS) / Revenue |

## Key Financial Milestones
1. **Month 6:** First revenue (design partner converts to paid)
2. **Month 12:** $500K ARR ($42K MRR)
3. **Month 15:** Burn rate covered by revenue (at scale)
4. **Month 18:** $2.5M+ ARR, Series A fundraise
5. **Month 30:** Cash flow positive (target)
