/**
 * Vocals Cluster RAG Filter (n8n Code Node)
 * Prepares the search query for Vocal Harmonization and Whisper Techniques.
 */

const input = items[0].json;

const searchQueries = [
  {
    role_id: 'whisper_vocals',
    style_tag: 'textura',
    query_text: "técnica de voces susurradas en bachata tradicional, refuerzo emocional"
  },
  {
    role_id: 'duos',
    style_tag: 'armonizacion',
    query_text: "intervalos de tercera y sexta para dueto de bachata"
  }
];

return searchQueries.map(q => ({ json: q }));
