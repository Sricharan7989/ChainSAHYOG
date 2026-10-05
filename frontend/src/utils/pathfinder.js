import { addrKey } from './address';
/**
 * Pathfinder and graph traversal utilities for highlighting primary money flows.
 */

export function findPath(edges, startAddress, targetAddress) {
  if (!edges || !startAddress || !targetAddress) return [];
  if (addrKey(startAddress) === addrKey(targetAddress)) return [];

  const start = addrKey(startAddress);
  const target = addrKey(targetAddress);

  // Build adjacency map: node -> [{ edge, nextNode }]
  const adj = new Map();
  for (const edge of edges) {
    const src = addrKey(edge.source);
    const dst = addrKey(edge.target);
    if (!src || !dst) continue;

    if (!adj.has(src)) adj.set(src, []);
    adj.get(src).push({ edge, nextNode: dst });
  }

  // BFS to find shortest path
  const queue = [[start]];
  const visited = new Set([start]);

  while (queue.length > 0) {
    const path = queue.shift();
    const current = path[path.length - 1];

    if (current === target) {
      // Reconstruct edges for this path
      const resultEdges = [];
      for (let i = 0; i < path.length - 1; i++) {
        const u = path[i];
        const v = path[i + 1];
        const candidates = (adj.get(u) || []).filter((item) => item.nextNode === v);
        if (candidates.length > 0) {
          resultEdges.push(candidates[0].edge);
        }
      }
      return resultEdges;
    }

    const neighbors = adj.get(current) || [];
    for (const { nextNode } of neighbors) {
      if (!visited.has(nextNode)) {
        visited.add(nextNode);
        queue.push([...path, nextNode]);
      }
    }
  }

  return [];
}

export function extractPathNodes(pathEdges, startAddress) {
  if (!pathEdges || pathEdges.length === 0) return startAddress ? [startAddress] : [];
  const nodes = [pathEdges[0].source];
  for (const edge of pathEdges) {
    nodes.push(edge.target);
  }
  return nodes;
}
