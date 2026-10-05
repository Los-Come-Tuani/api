from datetime import datetime

from api_core.schemas.base import DTO

########################################################################################


class AccountClosingGet(DTO):
    # cuándo se destruyen los datos si no se reactiva antes
    effective_at: datetime
