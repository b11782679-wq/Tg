def build_payme_pay_url(order_id: int, amount_uzs: int) -> str:
    # Payme uchun ham haqiqiy merchant URL yoki invoice yaratish kerak bo‘ladi.
    return f"https://payme.uz/pay?order_id={order_id}&amount={amount_uzs}"
