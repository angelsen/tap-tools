# WebServe Vision: YAML-Driven Web Scraping APIs

## Core Philosophy

**Transform website research into production APIs through configuration, not code.**

WebServe takes YAML schemas discovered through WebTap research and automatically generates robust FastAPI endpoints with Playwright-powered scraping, persistent sessions, and intelligent data extraction.

## The Problem We're Solving

After reverse-engineering a website with WebTap, you need to:
1. Write scraping code with Playwright/BeautifulSoup
2. Handle authentication and sessions
3. Build API endpoints
4. Manage retries and rate limiting
5. Transform and validate data

This leads to:
- Repetitive boilerplate code
- Inconsistent error handling
- Session management complexity
- Maintenance burden as sites change

## The Solution: Configuration-Driven APIs

### 1. Research with WebTap
Discover patterns, endpoints, and data structures through CDP inspection.

### 2. Define in YAML
Capture your findings in declarative schemas:
```yaml
service: example_site
endpoints:
  search:
    path: /search
    extract:
      results: {selector: ".result-item"}
```

### 3. Deploy with WebServe
Drop YAML files into `schemas/` and get instant APIs:
```
GET /example_site/search → Fully functional endpoint
```

## Architecture

```
schemas/                     FastAPI App
  finn.no/                       │
    service.yaml  ─────┐         │
    endpoints.yaml ────┼───────▶├── /finn/search
                       │         ├── /finn/property/{id}
  banking.no/          │         │
    service.yaml  ─────┼───────▶├── /banking/accounts
    auth.yaml ─────────┘         └── /banking/transactions
                                         │
                                         ▼
                                  Playwright Browser
                                    (Persistent Sessions)
```

## Key Features

### YAML-Complete Configuration
Everything is defined in YAML:
- Endpoints and parameters
- SSR scraping selectors
- API call orchestration
- Authentication flows
- Data transformations
- Rate limiting rules

### Intelligent Extraction
```yaml
extract:
  price:
    selector: ".price"
    regex: "kr\\s*([\\d\\s]+)"
    transform: parse_currency
    fallback: null
```

### Hybrid Data Sources
Combine SSR scraping with API calls:
```yaml
response:
  type: hybrid
  ssr:
    extract: {title: {selector: "h1"}}
  api_calls:
    - endpoint: /api/details?id={id}
      merge_as: details
```

### Session Management
Persistent browser contexts with auth handling:
```yaml
auth:
  type: manual
  persist: true
  detection:
    logged_in: {selector: ".user-name", exists: true}
```

## Complete Example: FINN.no Pipeline

### Step 1: Research with WebTap
Using WebTap's CDP inspection, we discovered:
- FINN uses SSR for property listings (no JSON API)
- Location system uses hierarchical IDs (1.20016.20318)
- Neighborhood data available via JSON endpoints
- Each property has unique `finnkode` identifier

### Step 2: Define in YAML
Created schemas capturing the patterns:
```yaml
# endpoints.yaml
endpoints:
  search_properties:
    path: /realestate/homes/search.html
    response:
      type: ssr
      extract:
        listings:
          selector: "article"
          fields:
            finnkode: {selector: "a[href]", regex: "finnkode=(\\d+)"}
            price: {selector: ".price", transform: parse_currency}
```

### Step 3: Use WebServe API
Clean JSON responses from messy HTML:

```bash
# Search for properties
GET http://localhost:8000/finn/search?location=trondheim

{
  "total_count": 1847,
  "listings": [
    {
      "finnkode": "396792849",
      "title": "Stor halvpart av tomannsbolig",
      "price": 4290000,
      "location": "Nyveibakken 15B",
      "size": 140
    }
  ]
}

# Get property with neighborhood data (hybrid SSR + API)
GET http://localhost:8000/finn/property/396792849

{
  "title": "VELHOLDT OG STOR HALVPART",
  "price": 4290000,
  "address": "Nyveibakken 15B",
  "bedrooms": 4,
  "transport_geo": [
    {
      "name": "Nyveibakken",
      "type": "bus", 
      "coordinates": [10.370963, 63.424326],
      "walk_time": 135,
      "routes": ["3", "26", "52"]
    }
  ]
}
```

From CDP research to production API with zero code - just YAML configuration.

## Use Cases

### 1. Real Estate Aggregation
Research multiple property sites with WebTap, deploy unified API with WebServe.

### 2. Banking Integration
Manual BankID login, then automated account/transaction fetching.

### 3. E-commerce Monitoring
Track prices across sites without writing scraper code.

### 4. Government Services
Navigate complex public sector sites through configuration.

## Success Metrics

- **Zero code for new sites** - Only YAML needed
- **< 1 hour from research to API** - WebTap to WebServe
- **Automatic resilience** - Built-in retries and fallbacks
- **Session persistence** - Login once, scrape many times

## Development Principles

### DO:
- Keep all logic in YAML when possible
- Make common patterns easy
- Provide escape hatches for complex cases
- Maintain clear separation from WebTap
- Support incremental adoption

### DON'T:
- Require code for basic scraping
- Transform data unnecessarily
- Couple to specific sites
- Hide the browser when debugging

## Future Enhancements

### Phase 1: Core (Current)
- [x] YAML schema parsing
- [ ] FastAPI endpoint generation
- [ ] Playwright browser pool
- [ ] Basic authentication
- [ ] CSS/XPath selectors

### Phase 2: Enhanced
- [ ] JavaScript execution steps
- [ ] Conditional logic in YAML
- [ ] Response caching
- [ ] Webhook notifications
- [ ] Scheduled scraping

### Phase 3: Scale
- [ ] Distributed browser pools
- [ ] Schema versioning
- [ ] A/B testing selectors
- [ ] Auto-healing selectors
- [ ] Visual regression testing

## Integration with WebTap

```
WebTap (Research)            WebServe (Production)
     │                               │
     ├── Discover patterns           ├── Read YAML schemas
     ├── Test selectors              ├── Generate endpoints
     ├── Understand flow             ├── Manage sessions
     └── Export YAML ──────────────▶└── Serve APIs
```

## Why This Matters

WebServe democratizes web scraping by:
1. **Lowering the barrier** - No Playwright knowledge needed
2. **Standardizing patterns** - Consistent API design
3. **Enabling sharing** - YAML schemas as scraping recipes
4. **Reducing maintenance** - Update YAML, not code

The web becomes your API, configured not coded.