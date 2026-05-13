/**
 * Harmony Cluster RAG Filter (n8n Code Node)
 * Prepares the search query for the Requinto's specialized techniques.
 */

const input = items[0].json;

// Define the search requirements for the Requinto
// We want to find patterns tagged with 'picaos' and 'requinto'
const searchQueries = [
  {
    role_id: 'requinto',
    style_tag: 'picaos',
    query_text: "picaos rápidos de bachata sobre acordes de " + input.structure[0].chords.join(', ')
  },
  {
    role_id: 'bajo',
    style_tag: 'tumbao',
    query_text: "tumbao de bajo tradicional 128bpm"
  }
];

// Map this to a Supabase node call
return searchQueries.map(q => ({ json: q }));
