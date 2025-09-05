# FINN.no Schema

Norwegian marketplace for real estate, cars, jobs, and general classifieds.

## Research Notes

Discovered using WebTap CDP inspection on 2025-09-02.

### Architecture
- **SSR-heavy**: Property listings and details are server-side rendered
- **Location system**: Hierarchical IDs (1.20016.20318 = Norway.Trøndelag.Trondheim)
- **Unique IDs**: Each listing has a `finnkode` identifier
- **Hybrid data**: SSR for content, JSON APIs for geographic/neighborhood data

### Key Endpoints

#### Search Flow
1. `/realestate/homes/xhr?term={city}` - Get location suggestions
2. `/realestate/homes/search.html?location={location_id}` - Get listings (SSR)

#### Property Details  
- `/realestate/homes/ad.html?finnkode={id}` - Full property page (SSR)
- `/realestate/widget-api/neighborhood-api-alt.json?finnkode={id}` - Area amenities
- `/realestate/widget-api/neighborhood-api-geo.json?finnkode={id}` - GPS coordinates and transport

#### Area Profiles
- `/areaprofile/{finnkode}/transport` - Public transport details
- `/areaprofile/{finnkode}/familie` - Schools and kindergartens
- `/areaprofile/{finnkode}/handel` - Shopping locations

### Data Extraction Patterns

#### Listings from Search Page
- Container: `article` elements
- Finnkode: Extract from `a[href]` with regex `finnkode=(\d+)`
- ~50 listings per page embedded in HTML

#### Property Details
- Title: `<title>` tag
- Price: Look for `h2` containing "kr"
- Location: `<address>` element
- Data embedded in Remix context (window.__remixContext)

#### Neighborhood Data
- Transport stops with walking times
- Schools and kindergartens
- Shopping locations
- Safety ratings
- All POIs include GPS coordinates in geo endpoint

### Authentication
None required for public listings.

## Files

- `service.yaml` - Core service configuration
- `endpoints.yaml` - Endpoint definitions and extraction rules
- `transforms.yaml` - Data transformation functions

## Usage

```python
# Generated endpoints:
GET /finn/search?location=trondheim
GET /finn/property/{finnkode}
GET /finn/property/{finnkode}/neighborhood
```

## Notes

- Rate limiting recommended (2 req/s)
- Large HTML responses (400KB+ for property pages)
- Remix framework with hydration
- Norwegian language content (UTF-8)