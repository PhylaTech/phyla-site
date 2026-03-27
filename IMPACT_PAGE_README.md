# Impact & Influence Page

## Overview

The Impact & Influence page (`impact.html`) is an interactive visualization showcasing Phyla Technologies' research footprint across academia and industry. It demonstrates measurable impact through citation networks, geographic reach, and disciplinary influence.

## Features

### 1. Research Footprint Metrics
- **Total Citations**: Aggregate citation count across all publications
- **H-Index**: Research impact metric
- **Citing Institutions**: Number of unique institutions citing our work
- **Countries**: Geographic distribution of citations
- **Research Fields**: Number of distinct fields impacted

### 2. Interactive Citation Network
- **Force Layout**: Default view showing natural clustering of citations
- **Radial Layout**: Concentric circles showing publication hierarchy
- **Cluster View**: Grouped by publication type
- **Features**:
  - Drag-and-drop nodes
  - Zoom and pan
  - Hover tooltips with citation details
  - Color-coded by research field

### 3. Geographic & Institutional Reach
- World map visualization showing citation locations
- Interactive markers sized by citation count
- Connection lines showing research network
- Hover tooltips with institution details

### 4. Disciplinary Influence
- Animated bar charts showing citation distribution across fields
- Color-coded by research domain:
  - Bioinformatics (Teal)
  - Metabolomics (Sky Blue)
  - Machine Learning (Blue)
  - Drug Discovery (Violet)
  - Proteomics (Pink)
  - Cheminformatics (Amber)

### 5. Key Collaborators & Downstream Impact
- Grid of collaborator cards
- Shows academic labs, industry teams, and consortia
- Displays collaborative paper counts

## Technology Stack

- **D3.js v7**: Interactive data visualizations
- **Vanilla JavaScript**: No framework dependencies
- **CSS3**: Modern animations and transitions
- **Responsive Design**: Mobile-friendly layouts

## Data Sources

Currently using sample data for demonstration. In production, this should be integrated with:

### OpenAlex API Integration
OpenAlex provides open citation data that can be queried via their REST API:

```javascript
// Example API call to fetch author works
const authorId = 'A1234567890'; // Replace with actual author ID
const response = await fetch(`https://api.openalex.org/authors/${authorId}/works`);
const data = await response.json();
```

### Recommended Implementation Steps:

1. **Identify Author IDs**: Find OpenAlex IDs for team members
   - Search: `https://api.openalex.org/authors?search=Ian+Miller`
   
2. **Fetch Publications**: Get all works by author
   - Endpoint: `https://api.openalex.org/works?filter=author.id:${authorId}`
   
3. **Get Citation Data**: Extract citing works
   - Each work includes `cited_by_count` and `cited_by_api_url`
   
4. **Extract Metadata**:
   - Citing institutions: `work.authorships[].institutions`
   - Research fields: `work.concepts` (topics/fields)
   - Geographic data: `institution.geo` (lat/lon)
   
5. **Build Citation Network**:
   - Nodes: Publications + Citing works
   - Links: Citation relationships
   - Attributes: Field, institution, citation count

### Example Data Structure:

```javascript
{
  nodes: [
    {
      id: 'W1234567890',
      name: 'Publication Title',
      type: 'publication',
      citations: 150,
      field: 'bioinformatics',
      year: 2023
    },
    {
      id: 'W0987654321',
      name: 'Citing Work',
      type: 'citing',
      citations: 25,
      field: 'metabolomics',
      institution: 'Harvard Medical School',
      lat: 42.3352,
      lon: -71.1035
    }
  ],
  links: [
    { source: 'W1234567890', target: 'W0987654321' }
  ]
}
```

## Customization

### Adding New Fields
Edit the `fieldColors` object in the JavaScript section:

```javascript
const fieldColors = {
  newField: '#HEX_COLOR',
  // ...
};
```

### Adjusting Visualization Parameters
- **Force strength**: Modify `d3.forceManyBody().strength(-300)`
- **Link distance**: Modify `d3.forceLink().distance(100)`
- **Node sizes**: Adjust radius calculations in node creation

### Styling
All colors use CSS custom properties defined in `:root`:
- Modify color scheme by updating `--teal-*`, `--blue-*`, etc.
- Adjust animations by modifying `@keyframes` rules

## Performance Considerations

- Current implementation handles ~20 nodes efficiently
- For larger datasets (100+ nodes):
  - Implement pagination or filtering
  - Use canvas rendering instead of SVG
  - Add progressive loading
  - Implement data aggregation

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Requires JavaScript enabled
- Responsive design for mobile devices
- Graceful degradation for older browsers

## Future Enhancements

1. **Real-time Data**: Connect to OpenAlex API for live data
2. **Time Series**: Show citation growth over time
3. **Search & Filter**: Allow users to filter by field, year, or institution
4. **Export**: Enable data export (CSV, JSON)
5. **Comparison**: Compare impact across team members
6. **Topic Modeling**: Integrate topic analysis from Paperpile library
7. **Industry vs Academia**: Separate visualizations for different sectors
8. **Collaboration Network**: Show co-authorship patterns

## Maintenance

- Update citation data quarterly
- Verify OpenAlex API endpoints remain stable
- Monitor D3.js version updates
- Test visualizations across browsers
- Optimize performance as dataset grows

## References

- [OpenAlex Documentation](https://docs.openalex.org/)
- [D3.js Documentation](https://d3js.org/)
- [Force-Directed Graphs](https://observablehq.com/@d3/force-directed-graph)
- [Geographic Projections](https://github.com/d3/d3-geo)
