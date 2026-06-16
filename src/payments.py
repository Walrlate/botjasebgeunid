import aiohttp
import logging
import time
import random
from src.config import KLIKQRIS_API_KEY, KLIKQRIS_MERCHANT_ID

logger = logging.getLogger(__name__)

async def create_qris_transaction(amount, description):
    url = "https://klikqris.com/api/qris/create"
    order_id = f"INV-{int(time.time())}{random.randint(100, 999)}"
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": KLIKQRIS_API_KEY,
        "id_merchant": str(KLIKQRIS_MERCHANT_ID)
    }
    
    payload = {
        "order_id": order_id,
        "id_merchant": str(KLIKQRIS_MERCHANT_ID),
        "amount": int(amount),
        "keterangan": description
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                logger.info(f"KlikQRIS Create Response: {result}")
                if result.get("status") is True:
                    data = result.get("data", {})
                    # Konversi string total_amount ke integer/float untuk kompatibilitas
                    try:
                        total_amt = int(float(data.get("total_amount", amount)))
                    except Exception:
                        total_amt = amount
                        
                    return {
                        "transaction_id": data.get("order_id"),
                        "payment_url": data.get("redirect_url"),
                        "total_amount": total_amt,
                        "expired_at": data.get("expired_at"),
                        "qris_url": data.get("qris_url")
                    }
                else:
                    logger.error(f"KlikQRIS Create Error: {result.get('message')}")
                    return None
        except Exception as e:
            logger.error(f"Payment Request Exception: {e}")
            return None

async def check_transaction_status(trx_id):
    # Endpoint Check Status: /qris/status/{order_id}
    url = f"https://klikqris.com/api/qris/status/{trx_id}"
    
    headers = {
        "x-api-key": KLIKQRIS_API_KEY,
        "id_merchant": str(KLIKQRIS_MERCHANT_ID)
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                if result.get("status") is True:
                    data = result.get("data", {})
                    # Ubah status SUCCESS/PENDING menjadi lowercase untuk kompatibilitas bot
                    api_status = str(data.get("status", "pending")).lower()
                    return {
                        "success": True,
                        "data": {
                            "status": api_status
                        }
                    }
                else:
                    logger.error(f"KlikQRIS Status Error: {result.get('message')}")
                    return {"success": False, "message": result.get("message")}
        except Exception as e:
            logger.error(f"Check Status Exception: {e}")
            return None

