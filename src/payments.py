import aiohttp
import logging
import time
import random
from src.config import KLIKQRIS_API_KEY, KLIKQRIS_MERCHANT_ID

logger = logging.getLogger(__name__)

async def create_qris_transaction(amount, description):
    url = "https://klikqris.com/api/qris/create"
    
    desc_lower = str(description).lower()
    if "userbot" in desc_lower:
        prefix = "USERBOT"
    elif "forward" in desc_lower or "fwd" in desc_lower:
        prefix = "FORWARD"
    else:
        prefix = "REGULAR"
        
    order_id = f"{prefix}-{int(time.time())}{random.randint(100, 999)}"
    
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
    
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                logger.info(f"KlikQRIS Create Response: {result}")
                
                is_success = (
                    result.get("status") is True or 
                    result.get("status") == "true" or 
                    result.get("success") is True or 
                    result.get("success") == "true" or 
                    result.get("code") == 200 or 
                    result.get("message") == "Success"
                )
                
                if is_success:
                    data = result.get("data")
                    if not isinstance(data, dict):
                        data = result
                        
                    # Dapatkan order_id / transaction_id dari data atau root
                    trx_id = data.get("order_id") or data.get("transaction_id") or data.get("reference_id") or result.get("transaction_id") or order_id
                    pay_url = data.get("redirect_url") or data.get("payment_url") or data.get("url") or result.get("payment_url")
                    qris_url = data.get("qris_url") or data.get("qr_url") or result.get("qris_url")
                    
                    # Konversi string total_amount ke integer/float untuk kompatibilitas
                    try:
                        total_amt = int(float(data.get("total_amount", amount)))
                    except Exception:
                        total_amt = amount
                        
                    return {
                        "transaction_id": trx_id,
                        "payment_url": pay_url,
                        "total_amount": total_amt,
                        "expired_at": data.get("expired_at"),
                        "qris_url": qris_url
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
    
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                is_success = (
                    result.get("status") is True or 
                    result.get("status") == "true" or 
                    result.get("success") is True or 
                    result.get("success") == "true" or 
                    result.get("code") == 200 or
                    result.get("message") == "Success"
                )
                if is_success:
                    data = result.get("data")
                    if not isinstance(data, dict):
                        data = result
                    # Ubah status SUCCESS/PENDING menjadi lowercase untuk kompatibilitas bot
                    api_status = str(data.get("status") or data.get("transaction_status") or "pending").lower()
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

