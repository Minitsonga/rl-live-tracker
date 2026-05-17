"""Texte d'exemple pour DefaultStatsAPI.ini (aucun accès au dossier du jeu)."""
from __future__ import annotations

# Chemin relatif documenté pour l'utilisateur — l'app ne le résout pas sur le disque.
STATS_API_INI_RELATIVE = "TAGame/Config/DefaultStatsAPI.ini"


def example_stats_api_ini(port: int = 49123, packet_send_rate: int = 2) -> str:
    return (
        "[StatsAPI]\n"
        f"PacketSendRate={packet_send_rate}\n"
        f"Port={int(port)}\n"
    )
