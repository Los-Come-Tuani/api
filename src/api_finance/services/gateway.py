from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from api_core.config import CONFIG

if TYPE_CHECKING:
    from api_finance.models import Payment

########################################################################################
# La pasarela es intercambiable: hoy la "manual" (el turista recibe instrucciones y el
# equipo confirma); una real (BAC, PayPal...) implementa lo mismo y suma su webhook.
########################################################################################


@dataclass(frozen=True, slots=True)
class Intent:
    # lo que se le muestra al turista para pagar
    instructions: str
    reference: str = ""


class PaymentGateway(Protocol):
    name: str

    def create_intent(self, payment: Payment) -> Intent: ...


class ManualGateway:
    name: str = "manual"

    def create_intent(self, payment: Payment) -> Intent:  # ruff: ignore[no-self-use, unused-method-argument]
        return Intent(instructions=CONFIG.PAYMENT_INSTRUCTIONS)


def get_gateway() -> PaymentGateway:
    return ManualGateway()
