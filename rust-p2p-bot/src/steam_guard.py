"""
Steam Guard модуль для автоподтверждения трейдов.
Использует токены из SDA maFile для авторизации.
Поддерживает: генерацию 2FA кодов, подтверждение трейдов, принятие трейд-офферов.
"""

import json
import struct
import hmac
import hashlib
import time
import asyncio
import re
import aiohttp
from base64 import b64decode, b64encode
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger


@dataclass
class Confirmation:
    """Структура подтверждения трейда"""
    id: str
    nonce: str
    creator_id: str
    conf_type: int
    type_name: str
    headline: str
    summary: List[str]
    icon: str


class SteamGuardManager:
    """
    Управление Steam Guard для автоподтверждения трейдов.
    Использует токены из SDA maFile.
    """
    
    STEAM_GUARD_CHARSET = '23456789BCDFGHJKMNPQRTVWXY'
    
    def __init__(self, sda_mafile_path: str):
        """
        Инициализация из SDA maFile (с токенами).
        
        Args:
            sda_mafile_path: Путь к SDA maFile
        """
        self.mafile_path = sda_mafile_path
        self._load_mafile()
        self.steam_time_offset: Optional[int] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_id: Optional[str] = None
        
    def _load_mafile(self):
        """Загрузка данных из SDA maFile"""
        with open(self.mafile_path, 'r') as f:
            data = json.load(f)
            
        self.shared_secret = b64decode(data['shared_secret'])
        self.identity_secret = b64decode(data['identity_secret'])
        self.device_id = data['device_id']
        self.account_name = data.get('account_name', '')
        
        # Токены из Session
        session = data.get('Session', {})
        self.steam_id = str(session.get('SteamID', data.get('steam_id', '')))
        self.access_token = session.get('AccessToken', '')
        self.refresh_token = session.get('RefreshToken', '')
        
        self.mafile_data = data
        
        logger.info(f"Loaded SDA maFile for: {self.account_name}")
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        """Закрытие сессии"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_cookies(self) -> Dict[str, str]:
        """Получение cookies для авторизации"""
        return {
            'steamLoginSecure': f"{self.steam_id}%7C%7C{self.access_token}",
            'mobileClient': 'android'
        }

    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def get_steam_time(self) -> int:
        """Получение времени сервера Steam"""
        if self.steam_time_offset is None:
            try:
                session = await self._get_session()
                async with session.post(
                    'https://api.steampowered.com/ITwoFactorService/QueryTime/v1/',
                    data={},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    server_time = int(data.get('response', {}).get('server_time', time.time()))
                    self.steam_time_offset = server_time - int(time.time())
            except Exception as e:
                logger.warning(f"Failed to get Steam time: {e}")
                self.steam_time_offset = 0
                
        return int(time.time()) + self.steam_time_offset
    
    def generate_code(self, timestamp: Optional[int] = None) -> str:
        """Генерация 5-значного кода Steam Guard"""
        if timestamp is None:
            timestamp = int(time.time())
            
        time_chunk = timestamp // 30
        msg = struct.pack('>Q', time_chunk)
        hmac_hash = hmac.new(self.shared_secret, msg, hashlib.sha1).digest()
        
        offset = hmac_hash[19] & 0x0F
        code_int = struct.unpack('>I', hmac_hash[offset:offset+4])[0] & 0x7FFFFFFF
        
        code = ''
        for _ in range(5):
            code_int, idx = divmod(code_int, len(self.STEAM_GUARD_CHARSET))
            code += self.STEAM_GUARD_CHARSET[idx]
            
        return code
    
    def generate_confirmation_key(self, tag: str, timestamp: int) -> str:
        """Генерация ключа подтверждения"""
        data = struct.pack('>Q', timestamp) + tag.encode('ascii')
        hmac_hash = hmac.new(self.identity_secret, data, hashlib.sha1).digest()
        return b64encode(hmac_hash).decode('ascii')

    async def refresh_access_token(self) -> bool:
        """Обновление access token через refresh token"""
        try:
            session = await self._get_session()
            async with session.post(
                'https://api.steampowered.com/IAuthenticationService/GenerateAccessTokenForApp/v1/',
                data={'refresh_token': self.refresh_token, 'steamid': self.steam_id},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                
            new_token = data.get('response', {}).get('access_token')
            if new_token:
                self.access_token = new_token
                
                # Сохраняем в maFile
                self.mafile_data['Session']['AccessToken'] = new_token
                with open(self.mafile_path, 'w') as f:
                    json.dump(self.mafile_data, f)
                    
                logger.info("Access token refreshed successfully")
                return True
            else:
                logger.error(f"Failed to refresh token: {data}")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    async def _ensure_session_id(self):
        """Получение session ID для Steam"""
        if self._session_id:
            return self._session_id
            
        session = await self._get_session()
        async with session.get(
            'https://steamcommunity.com/',
            headers=self._get_headers(),
            cookies=self._get_cookies(),
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            # Ищем sessionid в cookies ответа
            for cookie in resp.cookies.values():
                if cookie.key == 'sessionid':
                    self._session_id = cookie.value
                    return self._session_id
        
        # Генерируем если не нашли
        import secrets
        self._session_id = secrets.token_hex(12)
        return self._session_id

    async def accept_trade_offer(self, trade_offer_id: str) -> Optional[str]:
        """
        Принятие трейд-оффера по ID.
        
        Args:
            trade_offer_id: ID трейд-оффера (из URL)
            
        Returns:
            Trade ID если успешно, None если ошибка
        """
        try:
            session = await self._get_session()
            session_id = await self._ensure_session_id()
            
            # Открываем страницу трейда чтобы получить partner ID
            trade_url = f"https://steamcommunity.com/tradeoffer/{trade_offer_id}/"
            
            async with session.get(
                trade_url,
                headers=self._get_headers(),
                cookies=self._get_cookies(),
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                html = await resp.text()
                
            # Ищем partner ID
            partner_match = re.search(r'g_ulTradePartnerSteamID\s*=\s*[\'"]?(\d+)[\'"]?', html)
            partner_id = partner_match.group(1) if partner_match else ''
            
            # Принимаем трейд
            accept_url = f"https://steamcommunity.com/tradeoffer/{trade_offer_id}/accept"
            
            accept_data = {
                'sessionid': session_id,
                'serverid': '1',
                'tradeofferid': trade_offer_id,
                'partner': partner_id,
                'captcha': ''
            }
            
            headers = {
                **self._get_headers(),
                'Referer': trade_url,
                'Origin': 'https://steamcommunity.com',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            cookies = {
                **self._get_cookies(),
                'sessionid': session_id
            }
            
            async with session.post(
                accept_url,
                data=accept_data,
                headers=headers,
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                result = await resp.json()
                
            if result.get('tradeid'):
                logger.info(f"✓ Trade accepted! ID: {result['tradeid']}")
                return result['tradeid']
            elif result.get('needs_mobile_confirmation'):
                logger.info(f"Trade {trade_offer_id} needs mobile confirmation")
                # Автоматически подтверждаем
                await asyncio.sleep(2)
                await self.accept_all_confirmations()
                return "pending_confirmation"
            elif result.get('strError'):
                logger.error(f"Trade error: {result['strError']}")
                return None
            else:
                logger.warning(f"Unknown response: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error accepting trade: {e}")
            return None

    async def fetch_confirmations(self) -> List[Confirmation]:
        """Получение списка ожидающих подтверждений"""
        timestamp = await self.get_steam_time()
        conf_key = self.generate_confirmation_key('conf', timestamp)
        
        params = {
            'p': self.device_id,
            'a': self.steam_id,
            'k': conf_key,
            't': timestamp,
            'm': 'react',
            'tag': 'conf'
        }
        
        try:
            session = await self._get_session()
            url = 'https://steamcommunity.com/mobileconf/getlist'
            
            async with session.get(
                url, 
                params=params, 
                headers=self._get_headers(), 
                cookies=self._get_cookies(),
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                
            if data.get('needauth'):
                logger.warning("Token expired, refreshing...")
                if await self.refresh_access_token():
                    return await self.fetch_confirmations()
                return []
                
            if not data.get('success'):
                logger.warning(f"Failed to fetch confirmations: {data}")
                return []
                
            confirmations = []
            for conf in data.get('conf', []):
                confirmations.append(Confirmation(
                    id=str(conf.get('id', '')),
                    nonce=str(conf.get('nonce', '')),
                    creator_id=str(conf.get('creator_id', '')),
                    conf_type=conf.get('type', 0),
                    type_name=conf.get('type_name', ''),
                    headline=conf.get('headline', ''),
                    summary=conf.get('summary', []),
                    icon=conf.get('icon', '')
                ))
                
            logger.info(f"Found {len(confirmations)} pending confirmations")
            return confirmations
                
        except Exception as e:
            logger.error(f"Error fetching confirmations: {e}")
            return []
    
    async def accept_confirmation(self, confirmation: Confirmation) -> bool:
        """Подтверждение трейда"""
        return await self._send_confirmation_action(confirmation, 'allow')
    
    async def deny_confirmation(self, confirmation: Confirmation) -> bool:
        """Отклонение трейда"""
        return await self._send_confirmation_action(confirmation, 'cancel')

    async def _send_confirmation_action(self, confirmation: Confirmation, action: str) -> bool:
        """Отправка действия подтверждения"""
        timestamp = await self.get_steam_time()
        conf_key = self.generate_confirmation_key(action, timestamp)
        
        params = {
            'op': action,
            'p': self.device_id,
            'a': self.steam_id,
            'k': conf_key,
            't': timestamp,
            'm': 'react',
            'tag': action,
            'cid': confirmation.id,
            'ck': confirmation.nonce
        }
        
        try:
            session = await self._get_session()
            url = 'https://steamcommunity.com/mobileconf/ajaxop'
            
            async with session.get(
                url, 
                params=params, 
                headers=self._get_headers(), 
                cookies=self._get_cookies(),
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                
            success = data.get('success', False)
            if success:
                logger.info(f"✓ {action.upper()}ED: {confirmation.headline}")
            else:
                logger.warning(f"✗ Failed to {action}: {data}")
                
            return success
                
        except Exception as e:
            logger.error(f"Error sending confirmation action: {e}")
            return False
    
    async def accept_all_confirmations(self) -> int:
        """Подтверждение всех ожидающих трейдов"""
        confirmations = await self.fetch_confirmations()
        accepted = 0
        
        for conf in confirmations:
            if await self.accept_confirmation(conf):
                accepted += 1
            await asyncio.sleep(0.5)
            
        logger.info(f"Accepted {accepted}/{len(confirmations)} confirmations")
        return accepted
    
    async def monitor_confirmations(self, interval: int = 5, callback=None):
        """Фоновый мониторинг и автоподтверждение трейдов"""
        logger.info(f"Starting confirmation monitor (interval: {interval}s)")
        
        while True:
            try:
                confirmations = await self.fetch_confirmations()
                
                for conf in confirmations:
                    success = await self.accept_confirmation(conf)
                    if success and callback:
                        await callback(conf)
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error in confirmation monitor: {e}")
                
            await asyncio.sleep(interval)


# Тестирование
async def test_steam_guard():
    """Тест Steam Guard с SDA токенами"""
    guard = SteamGuardManager('../SDA.1.0.15/maFiles/76561199113719186.maFile')
    
    print(f"Account: {guard.account_name}")
    print(f"SteamID: {guard.steam_id}")
    print(f"2FA Code: {guard.generate_code()}")
    
    print("\nFetching confirmations...")
    confirmations = await guard.fetch_confirmations()
    print(f"Found {len(confirmations)} confirmations")
    
    for conf in confirmations:
        print(f"  - {conf.headline} ({conf.type_name})")
    
    await guard.close()


if __name__ == '__main__':
    asyncio.run(test_steam_guard())
