"""
Duration models: graph (GNN) and the no-graph control (MLP) with identical inputs and heads.

DurationGNN
    input MLP -> L x [ SAGEConv over predecessor links  +  SAGEConv over successor links  + skip ]
    -> head -> log(actual / planned) per activity
Messages are kept separate by direction, so "what comes before me" and "what waits on me" are
learned as different relations (a minimal relational GNN).

NodeMLP
    the same encoder and head with no message passing. If the GNN cannot beat this,
    the graph structure is not adding information.
"""
from __future__ import annotations

import torch
from torch import nn
from torch_geometric.nn import SAGEConv


class NodeMLP(nn.Module):
    def __init__(self, n_in: int, hidden: int = 64, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Dropout(dropout),
                                 nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, data):
        return self.net(data.x).squeeze(-1)


class DurationGNN(nn.Module):
    def __init__(self, n_in: int, hidden: int = 64, layers: int = 3, dropout: float = 0.1):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU())
        self.fwd = nn.ModuleList(SAGEConv(hidden, hidden) for _ in range(layers))
        self.bwd = nn.ModuleList(SAGEConv(hidden, hidden) for _ in range(layers))
        self.norm = nn.ModuleList(nn.LayerNorm(hidden) for _ in range(layers))
        self.drop = nn.Dropout(dropout)
        self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, data):
        h = self.enc(data.x)
        fwd = data.edge_index[:, data.edge_attr[:, 0] > 0]   # predecessor -> successor
        bwd = data.edge_index[:, data.edge_attr[:, 1] > 0]   # successor -> predecessor
        for f, b, n in zip(self.fwd, self.bwd, self.norm):
            h = n(h + self.drop(torch.relu(f(h, fwd) + b(h, bwd))))
        return self.head(h).squeeze(-1)


def make(kind: str, n_in: int, **kw) -> nn.Module:
    return {"gnn": DurationGNN, "mlp": NodeMLP}[kind](n_in, **kw)
