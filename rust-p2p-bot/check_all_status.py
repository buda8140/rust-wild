"""
Проверка статуса всех площадок и инвентаря.
"""
import json
import asyncio
import sys
import os

# Определяем базовую директорию
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.steam_guard import SteamGuardManager
from src.dmarket_api import DMarketAPI
from src.pulse_api import PulseAPI
from src.lootfarm import LootFarmBot


async def main():
    # Загружаем настройки
    config_path = os.path.join(BASE_DIR, 'config/settings.json')
    with open(config_path, 'r') as f:
        settings = json.load(f)
    
    # Исправляем относительный путь к mafile
    mafile_path = settings['steam']['mafile_path']
    if mafile_path.startswith('..'):
        mafile_path = os.path.normpath(os.path.join(BASE_DIR, mafile_path))
    
    print("=" * 60)
    print("P2P TRADING BOT - ПРОВЕРКА СТАТУСА")
    print("=" * 60)
    
    # 1. Steam Guard
    print("\n📱 STEAM GUARD")
    print("-" * 40)
    guard = SteamGuardManager(mafile_path)
    print(f"Account: {guard.account_name}")
    print(f"SteamID: {guard.steam_id}")
    print(f"2FA Code: {guard.generate_code()}")
    
    # Проверяем подтверждения
    print("\nПроверка подтверждений...")
    confirmations = await guard.fetch_confirmations()
    print(f"Ожидающих подтверждений: {len(confirmations)}")
    for conf in confirmations:
        print(f"  - {conf.headline} ({conf.type_name})")
    
    # 2. DMarket
    print("\n💰 DMARKET")
    print("-" * 40)
    dmarket = DMarketAPI(
        settings['dmarket']['public_key'],
        settings['dmarket']['private_key']
    )
    
    balance = await dmarket.get_balance()
    if balance:
        print(f"Баланс: ${balance['usd']:.2f} USD")
    
    print("\nИнвентарь DMarket:")
    inventory = await dmarket.get_inventory('rust')
    if inventory:
        for item in inventory[:5]:
            print(f"  - {item.title}: ${item.price_usd:.2f}")
    else:
        print("  (пусто)")
    
    # 3. Loot.Farm
    print("\n🌾 LOOT.FARM")
    print("-" * 40)
    lootfarm = LootFarmBot()
    
    prices = await lootfarm.fetch_prices()
    print(f"Предметов в базе: {len(prices)}")
    
    # Показываем несколько доступных предметов
    available = [p for p in prices.values() if p.have > 0 and 0.50 <= p.price_usd <= 3.00]
    print(f"Доступных для обмена ($0.50-$3.00): {len(available)}")
    
    # Проверяем Santa Chest Plate
    santa = prices.get('Santa Chest Plate')
    if santa:
        print(f"\nSanta Chest Plate на Loot.Farm:")
        print(f"  Цена: ${santa.price_usd:.2f}")
        print(f"  У ботов: {santa.have}")
        print(f"  Лимит: {santa.max_count}")
        print(f"  Overstock: {santa.is_overstock}")
    
    # 4. Pulse API - поиск лучшего спреда
    print("\n📊 PULSE API - ЛУЧШИЕ СДЕЛКИ")
    print("-" * 40)
    pulse = PulseAPI(settings['pulse']['api_key'])
    
    best = await pulse.get_best_spread_item(
        min_price=0.50,
        max_price=3.00,
        min_spread_percent=10
    )
    
    if best:
        print(f"\nЛучшая сделка:")
        print(f"  Предмет: {best.item_name}")
        print(f"  Купить на {best.buy_market}: ${best.buy_price:.2f}")
        print(f"  Продать на {best.sell_market}: ${best.sell_price:.2f}")
        print(f"  Спред: +{best.spread_percent:.1f}% (${best.spread_usd:.2f})")
    else:
        print("Выгодных сделок не найдено")
    
    print(f"\nИспользовано токенов Pulse: {pulse.get_tokens_used()}")
    
    # Закрываем сессии
    await guard.close()
    await dmarket.close()
    await lootfarm.close()
    await pulse.close()
    
    print("\n" + "=" * 60)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
