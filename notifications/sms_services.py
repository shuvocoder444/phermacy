import logging
import requests
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class BangladeshSMSGateway:
    """
    Unified SMS Adapter for Bangladesh SMS providers (Greenweb SMS, BulkSMSBD).
    Supports English and Bangla Unicode SMS.
    """

    @classmethod
    def send_sms(
        cls,
        phone_number: str,
        message: str,
        sender_id: Optional[str] = None,
        provider: str = "greenweb"
    ) -> Dict[str, Any]:
        """
        Dispatches SMS to recipient. Standardizes Bangladesh 880 phone format.
        """
        # Clean and format phone number (convert 017xxx to 88017xxx)
        cleaned_phone = phone_number.strip().replace("-", "").replace(" ", "")
        if cleaned_phone.startswith("+88"):
            cleaned_phone = cleaned_phone[1:]
        elif cleaned_phone.startswith("01"):
            cleaned_phone = f"88{cleaned_phone}"

        api_key = getattr(settings, "SMS_API_KEY", "mock_key")
        sender_id = sender_id or getattr(settings, "SMS_SENDER_ID", "PHARMA")

        if provider == "greenweb":
            url = "http://api.greenweb.com.bd/api.php"
            params = {
                "token": api_key,
                "to": cleaned_phone,
                "message": message,
            }
        else:  # bulksmsbd
            url = "http://bulksmsbd.net/api/smsapi"
            params = {
                "api_key": api_key,
                "type": "unicode",
                "number": cleaned_phone,
                "senderid": sender_id,
                "message": message,
            }

        try:
            # If in debug mode or mock key, log without external call
            if settings.DEBUG or api_key == "mock_key":
                logger.info(f"[MOCK SMS] To: {cleaned_phone} | Sender: {sender_id} | Body: {message}")
                return {"status": "SUCCESS", "mock": True, "phone": cleaned_phone}

            response = requests.post(url, data=params, timeout=10)
            logger.info(f"SMS Response: {response.text}")
            return {"status": "SUCCESS", "response": response.text}
        except Exception as e:
            logger.error(f"Failed to send SMS to {cleaned_phone}: {str(e)}")
            return {"status": "ERROR", "error": str(e)}

    @classmethod
    def send_invoice_sms(cls, customer_phone: str, invoice_number: str, total_payable: str, due_amount: str, pharmacy_name: str) -> None:
        """
        Sends invoice purchase summary and due alert in Bangla/English.
        """
        if not customer_phone:
            return

        msg = (
            f"ধন্যবাদ! {pharmacy_name}-এ আপনার কেনাকাটা সম্পন্ন হয়েছে। "
            f"ইনভয়েস: {invoice_number}, মোট: ৳{total_payable}।"
        )
        if float(due_amount) > 0:
            msg += f" বকেয়া (Due): ৳{due_amount}।"
            
        cls.send_sms(phone_number=customer_phone, message=msg)

    @classmethod
    def send_due_reminder_sms(cls, customer_phone: str, customer_name: str, due_amount: str, pharmacy_name: str) -> None:
        """
        Sends gentle reminder for outstanding Baki.
        """
        msg = (
            f"শ্রদ্ধেয় {customer_name}, {pharmacy_name}-এ আপনার বকেয়া বিল ৳{due_amount} পরিশোধ করার জন্য বিনীত অনুরোধ করা হচ্ছে। "
            f"ধন্যবাদ।"
        )
        cls.send_sms(phone_number=customer_phone, message=msg)

