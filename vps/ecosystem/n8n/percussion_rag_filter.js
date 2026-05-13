/**
 * Percussion Cluster RAG Filter (n8n Code Node)
 * Prepares the search query for Rhythmic Patterns and Mambo variations.
 */

const input = items[0].json;

const searchQueries = [
  {
    role_id: 'percusión',
    style_tag: 'mambo',
    query_text: "variaciones de mambo para bongo y guira"
  },
  {
    role_id: 'percusión',
    style_tag: 'corte',
    query_text: "cortes rítmicos de bachata tradicional para cierre de sección"
  }
];

return searchQueries.map(q => ({ json: q }));
