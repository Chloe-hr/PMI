"""
Stage 3.7 Cambridge models. One class serves both arms, so the control is matched by construction:

    CambridgeSAGE(use_graph=True)    GraphSAGE: encoder -> L x [SAGE(pred->succ) + SAGE(succ->pred), residual,
                                     LayerNorm] -> head
    CambridgeSAGE(use_graph=False)   identical modules and parameter count; the edge set is emptied, so each
                                     SAGEConv reduces to its root linear map + bias (no neighbour information)

Output: log1p(reported elapsed calendar days) per node.
"""
from __future__ import annotations

import torch
from torch import nn
from torch_geometric.nn import SAGEConv


class CambridgeSAGE(nn.Module):
    def __init__(self, n_in: int, hidden: int = 64, layers: int = 2, dropout: float = 0.2, use_graph: bool = True):
        super().__init__()
        self.use_graph = use_graph
        self.enc = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Dropout(dropout))
        self.fwd = nn.ModuleList(SAGEConv(hidden, hidden, aggr="mean") for _ in range(layers))
        self.bwd = nn.ModuleList(SAGEConv(hidden, hidden, aggr="mean") for _ in range(layers))
        self.norm = nn.ModuleList(nn.LayerNorm(hidden) for _ in range(layers))
        self.drop = nn.Dropout(dropout)
        self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        if not self.use_graph:
            edge_index = edge_index.new_zeros((2, 0))
        rev = edge_index.flip(0)
        h = self.enc(x)
        for f, b, n in zip(self.fwd, self.bwd, self.norm):
            h = n(h + self.drop(torch.relu(f(h, edge_index) + b(h, rev))))
        return self.head(h).squeeze(-1)
