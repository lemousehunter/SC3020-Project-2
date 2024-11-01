// types.ts
export interface Node {
  id: string;
  type: string;
  table?: string | null;
  cost: number;
}

export interface Edge {
  source: string;
  target: string;
}

export interface NetworkXData {
  nodes: Node[];
  edges: Edge[];
}
