"""SMS provider abstraction; fake implementation logs OTP in dev/test."""

import logging

logger = logging.getLogger(__name__)


class FakeSmsProvider:
    def send(self, phone: str, text: str) -> None:
        logger.info("fake SMS to %s: %s", phone, text)


_default = FakeSmsProvider()


def send_otp_sms(phone: str, code: str) -> None:
    _default.send(phone, f"您的验证码是 {code}，5 分钟内有效。")
