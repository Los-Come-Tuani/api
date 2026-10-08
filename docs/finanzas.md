---
icon: lucide/wallet
---

# Cobros, comisiones, retiros y estados de cuenta

Cómo entra y sale el dinero: el cobro de cada reserva, la comisión de K'Plan, el saldo y los
retiros del guía y lo que se cobra cada mes a los comercios. Es la fase F8 de la
[hoja de ruta](hoja-de-ruta.md) y sigue el modelo de dominio de
[finanzas](modelo-dominio/modulos/finanzas.md).

## Lo que se decidió

- **Pasarela intercambiable.** Hoy la única es `manual`: la reserva abre su cobro, el
  turista ve las instrucciones (`PAYMENT_INSTRUCTIONS`) y el equipo con `billing.manage`
  confirma el pago cuando lo comprueba. La pasarela real se conecta cuando haya contrato
  sin tocar el resto (`PAYMENT_GATEWAY`, `api_finance/services/gateway.py`).
- **Comisión del 15 %** sobre cada reserva cerrada, configurable con `billing.manage`. Se
  copia la tasa del momento en la comisión: cambiarla no toca lo ya cerrado.
- **Solo córdobas**, en montos enteros.
- **Retiros del guía a mano**: pide retirar su saldo a su cuenta (guardada cifrada,
  [D-09](modelo-dominio/decisiones.md#d-09)); el equipo deposita y lo marca pagado. Una
  cuenta nueva surte efecto 24 horas después ([D-10](modelo-dominio/decisiones.md#d-10)).
- **Estados de cuenta mensuales** para los comercios: la insignia del lugar y una tarifa
  por cupón validado. El equipo los cobra fuera de línea y los marca pagados.

## Tarifas (`billing.view` y los comercios ven, `billing.manage` cambia)

| Ruta           | Qué hace                                                              |
| -------------- | --------------------------------------------------------------------- |
| `GET pricing/` | Las tarifas: `[{ code, label, value, unit, updated_at }]`. También para el comercio: es lo que paga cada mes |
| `PUT pricing/` | `{ commission_rate?, badge_monthly?, coupon_fee? }`: solo cambia las que llegan |

| `code`             | Qué es                                     | `unit`    | Inicial |
| ------------------ | ------------------------------------------ | --------- | ------- |
| `comision_reserva` | Lo que K'Plan se queda de cada reserva     | `percent` | 15      |
| `insignia_mensual` | Lo que paga un comercio por la insignia de su lugar, por mes | `nio` | 300 |
| `cupon_validado`   | Lo que paga un comercio por cada cupón que valida | `nio` | 10 |

## El cobro de una reserva

Al nacer una reserva con monto (al reservar una salida o al aceptar una postulación) se abre
su pago. La reserva lo refleja en `payment_status` y, mientras el pago está pendiente, trae
`payment_instructions` (vacío en los demás casos):

| `payment_status` de la reserva | Qué pasa                                                   |
| ------------------------------ | ---------------------------------------------------------- |
| `sin_cobro`                    | Reserva gratis (monto 0)                                     |
| `pendiente`                    | Esperando el pago del turista                               |
| `pagado`                       | El equipo lo confirmó                                       |
| `por_reembolsar`               | Se canceló una reserva pagada: falta devolver el dinero      |
| `reembolsado`                  | Se devolvió                                                 |
| `anulado`                      | Se canceló antes de pagar                                   |

Cuando el guía termina el recorrido (`POST booking/{id}/finish/`) y el pago está confirmado
(o la reserva es gratis), la reserva **se cierra** (`closed`): se guarda la comisión y el
resto entra al saldo del guía. Si el pago llega después de terminar, se cierra al
confirmarlo. Pasa una sola vez por reserva.

### Lo que ve el equipo

| Ruta                          | Permiso          | Qué hace                                                   |
| ----------------------------- | ---------------- | ---------------------------------------------------------- |
| `GET payment/`                | `billing.view`   | Los pagos, del más viejo. Paginado. Filtro `status` (`pending`, `confirmed`, `refund_due`, `refunded`, `void`) |
| `POST payment/{id}/confirm/`  | `billing.manage` | `{ reference? }` (el número de la transferencia): lo da por pagado y avisa al turista |
| `POST payment/{id}/refund/`   | `billing.manage` | `{ reference? }`: un pago `refund_due` ya devuelto; avisa al turista |

Un pago: `{ id, booking_id, amount, gateway, status, reference, instructions, tourist_name,
guide_name, created_at, confirmed_at, refunded_at }`. Confirmar un pago que no está
pendiente, o reembolsar uno que no está por reembolsar, responde `409`.

## El saldo y los retiros del guía (sesión de la app)

| Ruta                     | Qué hace                                                              |
| ------------------------ | --------------------------------------------------------------------- |
| `GET balance/mine/`      | `{ balance, pending_withdrawals, movements }`: lo que puede retirar, lo que pidió y no se le ha pagado, y sus últimos 30 movimientos |
| `GET bank-account/mine/` | `{ active, pending }`: la cuenta que vale hoy y un cambio que espera sus 24 horas |
| `POST bank-account/mine/`| `{ bank, holder, account_type, number }` (`201`): la primera vale de una vez; un cambio, en 24 horas |
| `GET withdrawal/mine/`   | Sus retiros, del más nuevo                                             |
| `POST withdrawal/`       | `{ amount }` (`201`): aparta ese monto del saldo                       |

Solo un guía aprobado (`403`). Una cuenta: `{ id, bank, holder, account_type, last4,
effective_at }`; `account_type` es `ahorro` o `corriente` y el número completo nunca vuelve
al guía. Un movimiento: `{ amount, kind, booking_id, withdrawal_id, recorded_at }` con `kind`
`servicio` (lo que le dejó una reserva), `retiro` (negativo) o `devolucion_retiro` (un retiro
rechazado que vuelve). Pedir un retiro sin cuenta activa o por más del saldo responde `400`.

### Lo que hace el equipo

| Ruta                                | Permiso          | Qué hace                                       |
| ----------------------------------- | ---------------- | ---------------------------------------------- |
| `GET guide-withdrawal/`             | `billing.view`   | Los retiros, del más viejo. Filtro `status` (`pending`, `paid`, `rejected`) |
| `POST guide-withdrawal/{id}/pay/`   | `billing.manage` | `{ reference? }`: lo depositó; avisa al guía    |
| `POST guide-withdrawal/{id}/reject/`| `billing.manage` | `{ note }` (obligatorio): no se pagó; el monto vuelve al saldo y se avisa al guía |

Cada retiro trae además `guide_name` y `account_number`: el número completo, descifrado,
solo para quien tiene `billing.manage` (los demás lo ven nulo). Un retiro ya resuelto
responde `409`.

## Estados de cuenta de los comercios

| Ruta                              | Permiso                                    | Qué hace              |
| --------------------------------- | ------------------------------------------ | --------------------- |
| `GET billing/statement/`          | El comercio (los suyos) o `billing.view` (todos) | Del mes más reciente. Filtros `status` (`pending`, `paid`, `void`) y `business_id` |
| `POST billing/statement/{id}/pay/`| `billing.manage`                           | `{ reference? }`: lo cobró fuera de línea |

```json
{
  "id": "…", "business_id": "…", "business_name": "Café La Merced",
  "period": "2026-09-01", "total": 320, "status": "pending",
  "lines": [
    { "concept": "insignia_mensual", "description": "Insignia de Café La Merced",
      "quantity": 1, "unit_price": 300, "amount": 300 },
    { "concept": "cupon_validado", "description": "Cupones validados",
      "quantity": 2, "unit_price": 10, "amount": 20 }
  ],
  "issued_at": "…", "paid_at": null, "reference": ""
}
```

Los emite `issuestatements` (por defecto, el mes anterior; `--period AAAA-MM` para otro):
uno por comercio verificado que tenga algo que cobrar ese mes, con las tarifas del día en que
se emite. Volver a correrlo no duplica.

## Al desplegar

- Migración nueva `apifinance.0001` (siembra las tres tarifas).
- `PAYMENT_GATEWAY` (`manual`) y `PAYMENT_INSTRUCTIONS` (el texto que ve el turista: cuenta
  o número al que paga). Ver `.env.example`.
- Programar `issuestatements` el día 1 de cada mes.
- `rotatetotpkeys` también vuelve a cifrar los números de cuenta.

## Lo que queda para después

- La pasarela real (cobro con tarjeta y su webhook) cuando haya contrato.
- Que el pago pendiente venza solo y libere el cupo.
- El cobro a los comercios en línea y los recibos fiscales.
- Moneda distinta del córdoba.

## Dónde se aparta del modelo

- No hay `intento_pago` ni `webhook`: con la pasarela manual el pago tiene un solo intento.
- El saldo del guía es un libro de movimientos (`movimiento_saldo`) con la suma protegida
  para que nunca quede negativa; no hay tabla `saldo`.
- Los estados de cuenta solo cobran la insignia y los cupones; la suscripción del comercio
  queda para cuando se decida su precio.
