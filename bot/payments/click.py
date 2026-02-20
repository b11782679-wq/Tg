def build_click_pay_url(order_id: int, amount_uzs: int) -> str:
    # Bu yerda Click merchant parametrlari bilan URL yig‘iladi.
    # Hozircha demo:
    return f"https://click.uz/pay?order_id={order_id}&amount={amount_uzs}"
