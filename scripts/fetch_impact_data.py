#!/usr/bin/env python3
"""Fetch real citation data from OpenAlex for Phyla Technologies researchers.

Usage:
    python3 scripts/fetch_impact_data.py

Reads:  scripts/researchers.json
Writes: data/impact-data.json

To add a new researcher, add their name and ORCID to researchers.json and re-run.
If OpenAlex has conflated their profile with another person, add misattributed
work IDs to exclude_work_ids and re-run.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "researchers.json")
OUTPUT_PATH = os.path.join(PROJECT_DIR, "data", "impact-data.json")

BASE_URL = "https://api.openalex.org"

# Palette for disciplines (cycles if more than available)
DISCIPLINE_COLORS = [
    "#14B8A6", "#0891B2", "#0EA5E9", "#3B82F6", "#8B5CF6",
    "#A78BFA", "#2DD4BF", "#06B6D4", "#60A5FA", "#7C3AED",
    "#34D399", "#F59E0B", "#EC4899", "#EF4444", "#6366F1",
]

# ISO alpha-2 -> approximate centroid lat/lon for map visualization
COUNTRY_COORDS = {
    "US": (39.8, -98.5), "GB": (55.4, -3.4), "DE": (51.2, 10.4),
    "CN": (35.9, 104.2), "FR": (46.2, 2.2), "CA": (56.1, -106.3),
    "JP": (36.2, 138.3), "AU": (-25.3, 133.8), "CH": (46.8, 8.2),
    "NL": (52.1, 5.3), "KR": (35.9, 127.8), "SE": (60.1, 18.6),
    "IT": (41.9, 12.6), "ES": (40.5, -3.7), "BR": (-14.2, -51.9),
    "IN": (20.6, 78.9), "DK": (56.3, 9.5), "BE": (50.5, 4.5),
    "AT": (47.5, 14.6), "FI": (61.9, 25.7), "NO": (60.5, 8.5),
    "SG": (1.4, 103.8), "IL": (31.0, 34.8), "NZ": (-40.9, 174.9),
    "TW": (23.7, 121.0), "ZA": (-30.6, 22.9), "PL": (51.9, 19.1),
    "CZ": (49.8, 15.5), "PT": (39.4, -8.2), "MX": (23.6, -102.6),
    "IE": (53.1, -7.7), "HU": (47.2, 19.5), "RO": (45.9, 24.9),
    "CL": (-35.7, -71.5), "AR": (-38.4, -63.6), "CO": (4.6, -74.1),
    "MY": (4.2, 101.9), "TH": (15.9, 100.9), "PH": (12.9, 121.8),
    "ID": (-0.8, 113.9), "PK": (30.4, 69.3), "SA": (23.9, 45.1),
    "AE": (23.4, 53.8), "EG": (26.8, 30.8), "NG": (9.1, 8.7),
    "KE": (-0.0, 37.9), "GH": (7.9, -1.0), "TR": (39.0, 35.2),
    "GR": (39.1, 21.8), "HR": (45.1, 15.2), "RS": (44.0, 21.0),
    "SK": (48.7, 19.7), "SI": (46.2, 14.8), "LT": (55.2, 23.9),
    "LV": (56.9, 24.1), "EE": (58.6, 25.0), "BG": (42.7, 25.5),
    "UA": (48.4, 31.2), "RU": (61.5, 105.3), "BY": (53.7, 27.9),
    "IR": (32.4, 53.7), "IQ": (33.2, 43.7), "BD": (23.7, 90.4),
    "LK": (7.9, 80.8), "VN": (14.1, 108.3), "MM": (21.9, 95.9),
    "PE": (-9.2, -75.0), "EC": (-1.8, -78.2), "VE": (6.4, -66.6),
    "UY": (-32.5, -55.8), "QA": (25.4, 51.2), "KW": (29.3, 47.5),
    "IS": (64.9, -19.0), "LU": (49.8, 6.1), "CY": (35.1, 33.4),
    "MT": (35.9, 14.4), "TN": (34.0, 9.5), "MA": (31.8, -7.1),
    "ET": (9.1, 40.5), "TZ": (-6.4, 34.9), "UG": (1.4, 32.3),
    "SN": (14.5, -14.5), "CM": (7.4, 12.3), "CI": (7.5, -5.5),
}

# ISO alpha-2 -> country name
COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "DE": "Germany",
    "CN": "China", "FR": "France", "CA": "Canada", "JP": "Japan",
    "AU": "Australia", "CH": "Switzerland", "NL": "Netherlands",
    "KR": "South Korea", "SE": "Sweden", "IT": "Italy", "ES": "Spain",
    "BR": "Brazil", "IN": "India", "DK": "Denmark", "BE": "Belgium",
    "AT": "Austria", "FI": "Finland", "NO": "Norway", "SG": "Singapore",
    "IL": "Israel", "NZ": "New Zealand", "TW": "Taiwan", "ZA": "South Africa",
    "PL": "Poland", "CZ": "Czech Republic", "PT": "Portugal", "MX": "Mexico",
    "IE": "Ireland", "HU": "Hungary", "RO": "Romania", "CL": "Chile",
    "AR": "Argentina", "CO": "Colombia", "MY": "Malaysia", "TH": "Thailand",
    "PH": "Philippines", "ID": "Indonesia", "PK": "Pakistan",
    "SA": "Saudi Arabia", "AE": "United Arab Emirates", "EG": "Egypt",
    "NG": "Nigeria", "KE": "Kenya", "GH": "Ghana", "TR": "Turkey",
    "GR": "Greece", "HR": "Croatia", "RS": "Serbia", "SK": "Slovakia",
    "SI": "Slovenia", "LT": "Lithuania", "LV": "Latvia", "EE": "Estonia",
    "BG": "Bulgaria", "UA": "Ukraine", "RU": "Russia", "BY": "Belarus",
    "IR": "Iran", "IQ": "Iraq", "BD": "Bangladesh", "LK": "Sri Lanka",
    "VN": "Vietnam", "MM": "Myanmar", "PE": "Peru", "EC": "Ecuador",
    "VE": "Venezuela", "UY": "Uruguay", "QA": "Qatar", "KW": "Kuwait",
    "IS": "Iceland", "LU": "Luxembourg", "CY": "Cyprus", "MT": "Malta",
    "TN": "Tunisia", "MA": "Morocco", "ET": "Ethiopia", "TZ": "Tanzania",
    "UG": "Uganda", "SN": "Senegal", "CM": "Cameroon", "CI": "Ivory Coast",
}


def api_get(path, params=None):
    """Make a GET request to OpenAlex API with rate limiting."""
    if params is None:
        params = {}
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "PhylaTech-ImpactScript/1.0 (mailto:{})".format(
        config.get("email", "contact@phylatech.com")))

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(1)
                continue
            raise
    return None


def paginate_works(params):
    """Fetch all works matching params using cursor pagination."""
    all_results = []
    params = dict(params)
    params["cursor"] = "*"
    params["per_page"] = "100"

    while True:
        data = api_get("/works", params)
        if not data or "results" not in data:
            break
        all_results.extend(data["results"])
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor:
            break
        params["cursor"] = next_cursor
        time.sleep(0.1)  # polite rate limiting

    return all_results


def extract_work_id(work):
    """Extract short work ID like W1234567 from full URL."""
    return work["id"].split("/")[-1]


def get_researcher_name_from_work(work, orcid):
    """Get the researcher's display name from a work's authorships."""
    for authorship in work.get("authorships", []):
        author = authorship.get("author", {})
        if author.get("orcid") and orcid in author["orcid"]:
            return author.get("display_name", "")
    return ""


def fetch_works_for_researcher(researcher):
    """Fetch publications for a researcher.

    If include_work_ids is set (non-empty), only those specific works are fetched
    by ID. This is the recommended approach for researchers with conflated OpenAlex
    profiles. Otherwise, falls back to ORCID-based query with optional excludes.
    """
    name = researcher["name"]
    include = researcher.get("include_work_ids", [])
    exclude = set(researcher.get("exclude_work_ids", []))

    if include:
        # Fetch specific works by ID (precise, no conflation)
        print(f"\nFetching {len(include)} verified works for {name}...")
        works = []
        for wid in include:
            data = api_get(f"/works/{wid}", {
                "select": "id,title,doi,publication_year,primary_location,"
                          "cited_by_count,primary_topic,authorships,type",
            })
            if data:
                works.append(data)
                time.sleep(0.1)
            else:
                print(f"  WARNING: Could not fetch {wid}")
        print(f"  Fetched {len(works)} works")
        return works

    # Fallback: ORCID-based query (may include conflated works)
    orcid = researcher["orcid"]
    print(f"\nFetching works for {name} (ORCID: {orcid})...")

    works = paginate_works({
        "filter": f"author.orcid:{orcid}",
        "select": "id,title,doi,publication_year,primary_location,cited_by_count,"
                  "primary_topic,authorships,type",
    })

    filtered = []
    for w in works:
        wid = extract_work_id(w)
        if wid in exclude:
            print(f"  EXCLUDED: {wid} — {w.get('title', '?')}")
            continue
        filtered.append(w)

    print(f"  Found {len(works)} works, kept {len(filtered)} after exclusions")
    return filtered


def fetch_citing_works(work_id):
    """Fetch all works that cite a given work."""
    return paginate_works({
        "filter": f"cites:{work_id}",
        "select": "id,authorships,primary_topic",
    })


def process_citing_works(citing_works):
    """Extract institutions, countries, and fields from citing works."""
    institutions = set()
    country_citations = defaultdict(int)
    country_institutions = defaultdict(set)
    field_counts = defaultdict(int)

    for cw in citing_works:
        # Extract institutions and countries
        seen_countries_this_work = set()
        for authorship in cw.get("authorships", []):
            for inst in authorship.get("institutions", []):
                inst_name = inst.get("display_name")
                cc = inst.get("country_code")
                if inst_name:
                    institutions.add(inst_name)
                if cc and cc not in seen_countries_this_work:
                    seen_countries_this_work.add(cc)
                    country_citations[cc] += 1
                if cc and inst_name:
                    country_institutions[cc].add(inst_name)

        # Extract field
        pt = cw.get("primary_topic")
        if pt:
            field = pt.get("field", {}).get("display_name")
            if field:
                field_counts[field] += 1

    return institutions, country_citations, country_institutions, field_counts


def build_citation_network(publications, max_citing_per_pub=8):
    """Build a citation network with core publications and top citing works."""
    nodes = []
    links = []
    seen_ids = set()

    # Add core publication nodes
    for pub in publications:
        wid = extract_work_id(pub)
        field = ""
        if pub.get("primary_topic"):
            field = pub["primary_topic"].get("field", {}).get("display_name", "")
        nodes.append({
            "id": wid,
            "label": pub.get("title", "Untitled"),
            "field": field,
            "type": "core",
            "citations": pub.get("cited_by_count", 0),
            "year": pub.get("publication_year", 0),
        })
        seen_ids.add(wid)

    # For each core pub, fetch a sample of citing works for the network
    for pub in publications:
        wid = extract_work_id(pub)
        if pub.get("cited_by_count", 0) == 0:
            continue

        print(f"  Fetching citing works for network: {pub.get('title', '?')[:60]}...")
        citing = paginate_works({
            "filter": f"cites:{wid}",
            "select": "id,title,primary_topic,cited_by_count,publication_year",
            "sort": "cited_by_count:desc",
            "per_page": str(max_citing_per_pub),
        })
        # Only take top N
        citing = citing[:max_citing_per_pub]
        time.sleep(0.15)

        for cw in citing:
            cid = extract_work_id(cw)
            if cid not in seen_ids:
                field = ""
                if cw.get("primary_topic"):
                    field = cw["primary_topic"].get("field", {}).get("display_name", "")
                nodes.append({
                    "id": cid,
                    "label": cw.get("title", "Untitled"),
                    "field": field,
                    "type": "citing",
                    "citations": cw.get("cited_by_count", 0),
                    "year": cw.get("publication_year", 0),
                })
                seen_ids.add(cid)
            links.append({
                "source": wid,
                "target": cid,
                "strength": 0.5,
            })

    return {"nodes": nodes, "links": links}


def main():
    global config

    # Load config
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    researchers = config["researchers"]

    # Step 1: Fetch all publications, deduplicate across researchers
    all_works = {}  # work_id -> work data
    work_authors = defaultdict(list)  # work_id -> [researcher names]

    for researcher in researchers:
        works = fetch_works_for_researcher(researcher)
        for w in works:
            wid = extract_work_id(w)
            if wid not in all_works:
                all_works[wid] = w
            work_authors[wid].append(researcher["name"])

    publications = list(all_works.values())
    publications.sort(key=lambda w: w.get("cited_by_count", 0), reverse=True)
    print(f"\nTotal unique publications: {len(publications)}")

    # Step 2: Fetch citing works for geographic/institutional/discipline data
    print("\nFetching citing works for aggregate metrics...")
    all_institutions = set()
    total_country_citations = defaultdict(int)
    total_country_institutions = defaultdict(set)
    total_field_counts = defaultdict(int)

    for i, pub in enumerate(publications):
        wid = extract_work_id(pub)
        cited_by = pub.get("cited_by_count", 0)
        if cited_by == 0:
            continue

        title_short = pub.get("title", "?")[:55]
        print(f"  [{i+1}/{len(publications)}] {title_short}... ({cited_by} citations)")

        citing = fetch_citing_works(wid)
        insts, cc, ci, fc = process_citing_works(citing)
        all_institutions.update(insts)
        for k, v in cc.items():
            total_country_citations[k] += v
        for k, v in ci.items():
            total_country_institutions[k].update(v)
        for k, v in fc.items():
            total_field_counts[k] += v
        time.sleep(0.15)

    # Step 3: Build citation network
    print("\nBuilding citation network...")
    network = build_citation_network(publications)

    # Step 4: Assemble output
    total_citations = sum(w.get("cited_by_count", 0) for w in publications)
    unique_countries = set(k for k in total_country_citations if k in COUNTRY_COORDS)
    unique_fields = set(total_field_counts.keys())

    # Geographic data
    geographic = []
    for cc in sorted(total_country_citations, key=total_country_citations.get, reverse=True):
        if cc not in COUNTRY_COORDS:
            continue
        lat, lon = COUNTRY_COORDS[cc]
        geographic.append({
            "country": COUNTRY_NAMES.get(cc, cc),
            "country_code": cc,
            "lat": lat,
            "lon": lon,
            "citations": total_country_citations[cc],
            "institutions": len(total_country_institutions.get(cc, set())),
        })

    # Discipline data
    disciplines = []
    sorted_fields = sorted(total_field_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (field, count) in enumerate(sorted_fields):
        disciplines.append({
            "name": field,
            "count": count,
            "color": DISCIPLINE_COLORS[i % len(DISCIPLINE_COLORS)],
        })

    # Publication list
    pub_list = []
    for pub in publications:
        wid = extract_work_id(pub)
        journal = ""
        loc = pub.get("primary_location")
        if loc and loc.get("source"):
            journal = loc["source"].get("display_name", "")
        field = ""
        if pub.get("primary_topic"):
            field = pub["primary_topic"].get("field", {}).get("display_name", "")

        pub_list.append({
            "id": wid,
            "title": pub.get("title", "Untitled"),
            "journal": journal,
            "year": pub.get("publication_year"),
            "cited_by_count": pub.get("cited_by_count", 0),
            "field": field,
            "authors": work_authors.get(wid, []),
            "doi": pub.get("doi", ""),
            "type": "core",
        })

    # Collect all unique fields for the network legend
    all_fields = set()
    for node in network["nodes"]:
        if node.get("field"):
            all_fields.add(node["field"])
    field_colors = {}
    for i, f in enumerate(sorted(all_fields)):
        field_colors[f] = DISCIPLINE_COLORS[i % len(DISCIPLINE_COLORS)]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_citations": total_citations,
            "countries_reached": len(unique_countries),
            "citing_institutions": len(all_institutions),
            "disciplines_impacted": len(unique_fields),
            "total_publications": len(publications),
        },
        "publications": pub_list,
        "geographic": geographic,
        "disciplines": disciplines,
        "citation_network": network,
        "field_colors": field_colors,
    }

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Output written to: {OUTPUT_PATH}")
    print(f"  Publications:      {len(publications)}")
    print(f"  Total citations:   {total_citations}")
    print(f"  Countries reached: {len(unique_countries)}")
    print(f"  Institutions:      {len(all_institutions)}")
    print(f"  Disciplines:       {len(unique_fields)}")
    print(f"  Network nodes:     {len(network['nodes'])}")
    print(f"  Network links:     {len(network['links'])}")
    print(f"{'='*60}")

    # Print all work IDs for review (helps identify conflated works)
    print("\nAll publications (review for conflated works):")
    print("Add misattributed IDs to exclude_work_ids in researchers.json\n")
    for pub in pub_list:
        authors_str = ", ".join(pub["authors"])
        print(f"  {pub['id']:15s}  {pub['year']}  {pub['cited_by_count']:5d} cit  [{authors_str}]  {pub['title'][:70]}")


if __name__ == "__main__":
    main()
