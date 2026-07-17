"""LSTM point-forecaster with a city embedding broadcast into every timestep.

No BatchNorm anywhere: MC-Dropout inference keeps the whole model in
`.train()` mode, which would corrupt BatchNorm's live batch statistics.
"""
import torch
import torch.nn as nn


class SolarLSTM(nn.Module):
    def __init__(self, num_numeric_features: int, n_cities: int, config):
        super().__init__()
        self.city_embedding = nn.Embedding(n_cities, config.city_embedding_dim)

        lstm_hidden = config.hidden_sizes[0]
        num_lstm_layers = len(config.hidden_sizes)
        self.lstm = nn.LSTM(
            input_size=num_numeric_features + config.city_embedding_dim,
            hidden_size=lstm_hidden,
            num_layers=num_lstm_layers,
            batch_first=True,
            dropout=config.dropout_rate if num_lstm_layers > 1 else 0.0,
        )
        self.head_dropout = nn.Dropout(config.dropout_rate)

        head_layers = []
        in_dim = lstm_hidden
        for hidden_dim in config.hidden_sizes[1:]:
            head_layers += [nn.Linear(in_dim, hidden_dim), nn.ReLU(), nn.Dropout(config.dropout_rate)]
            in_dim = hidden_dim
        head_layers.append(nn.Linear(in_dim, config.horizon_hours))
        self.head = nn.Sequential(*head_layers)

    def forward(self, x: torch.Tensor, city_id: torch.Tensor) -> torch.Tensor:
        # x: (batch, lookback, num_numeric_features); city_id: (batch,)
        city_emb = self.city_embedding(city_id).unsqueeze(1).expand(-1, x.size(1), -1)
        lstm_input = torch.cat([x, city_emb], dim=-1)
        lstm_out, _ = self.lstm(lstm_input)
        last_hidden = self.head_dropout(lstm_out[:, -1, :])
        return self.head(last_hidden)
