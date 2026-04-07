"""ScenarioRegistry Protocol — Domain-layer contract for pack persistence.

Rationale (phase0_result §6.3 / §7.2 5.4):
    "Does the pack exist?" is part of the Scenario Pack domain invariant set,
    so the Registry contract — including the error channel — lives in the
    Domain layer. Infrastructure implementations (filesystem, HTTP, etc.) must
    implement this Protocol and raise Domain-layer errors (not Infra-layer
    ``RegistryError``) for caller-visible failures.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from gridflow.domain.scenario.scenario_pack import PackStatus, ScenarioPack


@runtime_checkable
class ScenarioRegistry(Protocol):
    """Contract for registering and retrieving Scenario Packs.

    Error contract:
        * :meth:`get` raises ``PackNotFoundError`` (Domain) when ``pack_id`` is
          absent.
        * :meth:`register` raises ``PackValidationError`` (Domain) on invariant
          violations.
        * Concrete implementations may additionally raise Infra-layer
          ``RegistryError`` for IO / backend failures; callers that wish to
          remain layer-pure should catch ``GridflowError`` and inspect the
          error code.
    """

    def register(self, pack: ScenarioPack) -> ScenarioPack:
        """Persist ``pack`` and return the stored instance.

        Implementations must validate the pack before persistence and set the
        status to :attr:`PackStatus.REGISTERED` on success.
        """
        ...

    def get(self, pack_id: str) -> ScenarioPack:
        """Look up a registered pack by ID.

        Raises:
            PackNotFoundError: If ``pack_id`` is not registered.
        """
        ...

    def list_all(self) -> tuple[ScenarioPack, ...]:
        """Return all registered packs, in deterministic order (by ``pack_id``)."""
        ...

    def update_status(self, pack_id: str, new_status: PackStatus) -> ScenarioPack:
        """Transition the stored pack's lifecycle status.

        Returns:
            The updated (re-fetched) ``ScenarioPack`` instance.

        Raises:
            PackNotFoundError: If ``pack_id`` is not registered.
        """
        ...

    def delete(self, pack_id: str) -> None:
        """Remove a pack from the registry.

        Raises:
            PackNotFoundError: If ``pack_id`` is not registered.
        """
        ...
