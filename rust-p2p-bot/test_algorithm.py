"""
Тест нового алгоритма поиска спреда
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from src.pulse_api import PulseAPI
from loguru import logger

async def test():
    print("=" * 60)
    print("ТЕСТ АЛГОРИТМА ПОИСКА СПРЕДА")
    print("=" * 60)
    
    # Загрузка настроек
    with open('config/settings.json', 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    pulse = PulseAPI(settings['pulse']['api_key'])
    
    try:
        # Все комбинации
        combinations = [
            ('TradeItTrade', 'Dmarket'),
            ('TradeItTrade', 'LootFarm'),
            ('Dmarket', 'TradeItTrade'),
            ('Dmarket', 'LootFarm'),
            ('LootFarm', 'TradeItTrade'),
            ('LootFarm', 'Dmarket'),
        ]
        
        best_spread = 0
        best_deal = None
        
        for source, target in combinations:
            print(f"\n🔍 Проверяем: {source} -> {target}")
            
            results = await pulse.compare_tables(
                first_market=source,
                second_market=target,
                min_price=0.50,
                max_price=3.00,
                take=10,
                exclude_overstock=True
            )
            
            print(f"   Найдено предметов: {len(results)}")
            
            for result in results[:3]:  # Показываем топ-3
                if result.spread_percent > best_spread:
                    best_spread = result.spread_percent
                    best_deal = result
                
                print(f"   • {result.item_name}")
                print(f"     ${result.first_market.price_usd:.2f} -> ${result.second_market.price_usd:.2f}")
                print(f"     Спред: +{result.spread_percent:.1f}%")
        
        print("\n" + "=" * 60)
        if best_deal:
            print("🏆 ЛУЧШИЙ СПРЕД:")
            print(f"   Предмет: {best_deal.item_name}")
            print(f"   Купить: ${best_deal.first_market.price_usd:.2f}")
            print(f"   Продать: ${best_deal.second_market.price_usd:.2f}")
            print(f"   Спред: +{best_deal.spread_percent:.1f}%")
            print(f"   Прибыль: ${best_deal.spread_usd:.2f}")
        else:
            print("❌ Выгодных спредов не найдено")
        print("=" * 60)
        
        print(f"\n📊 Использовано токенов: {pulse.get_tokens_used()}")
        
    finally:
        await pulse.close()

if __name__ == '__main__':
    asyncio.run(test())
