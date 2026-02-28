"""Porta: repositório de consultas e débitos."""

from abc import ABC, abstractmethod
from typing import Any


class ConsultaRepositoryPort(ABC):
    """Interface para persistência de consultas e débitos."""

    @abstractmethod
    def salvar_consulta_com_debitos(
        self,
        data: dict,
        ano: int,
        mes: int,
        matricula: str,
        sequencial: str,
        zona_ligacao: int = 1,
    ) -> Any:
        """Salva uma consulta com seus débitos (filtro ano/mês)."""
        ...

    @abstractmethod
    def salvar_por_referencia(
        self,
        data: dict,
        matricula: str,
        sequencial: str,
        zona_ligacao: int = 1,
    ) -> list:
        """Salva débitos agrupados por referencia (MM/YYYY). Retorna lista de consultas."""
        ...

    @abstractmethod
    def buscar_ultima_consulta(self, ano: int, mes: int) -> dict | None:
        """Busca a última consulta salva para ano/mês. Retorna None se não houver."""
        ...
