/**
 * MusicGAU Group Splitter (n8n Code Node)
 * This node prepares the payloads for parallel cluster processing.
 */

const input = items[0].json;
const clusters = input.clusters;

// This node should output 3 separate items to trigger parallel branches
// but in n8n, usually we branch after this node.
// We will structure the output so the next node can split by cluster.

return [
  { json: { cluster_id: 'percussion', config: input.config, data: clusters.percussion, structure: input.structure, session_id: input.session_id } },
  { json: { cluster_id: 'harmony', config: input.config, data: clusters.harmony, structure: input.structure, session_id: input.session_id } },
  { json: { cluster_id: 'vocals', config: input.config, data: clusters.vocals, structure: input.structure, session_id: input.session_id } }
];
